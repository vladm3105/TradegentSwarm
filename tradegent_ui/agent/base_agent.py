"""Base agent class with MCP integration."""
import time
import structlog
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .mcp_client import MCPClientPool, get_mcp_pool, MCPResponse
from .tool_mappings import (
    ToolMapping,
    MCPServer,
    get_tool_mapping,
    get_agent_tools,
    map_params,
)
from .llm_client import LLMClient, get_llm_client
from .context_manager import ConversationContext

log = structlog.get_logger(__name__)


@dataclass
class AgentResponse:
    """Response from agent processing."""

    success: bool
    a2ui: dict | None = None
    text: str = ""
    tool_results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseAgent(ABC):
    """Base class for specialist agents.

    Provides:
    - MCP client integration
    - Tool execution via mappings
    - LLM-based A2UI generation
    - Error handling
    """

    def __init__(self, agent_type: str):
        """Initialize agent.

        Args:
            agent_type: Agent type (analysis, trade, portfolio, research)
        """
        self.agent_type = agent_type
        self.tools = get_agent_tools(agent_type)
        self._mcp_pool: MCPClientPool | None = None
        self._llm_client: LLMClient | None = None

    async def initialize(self):
        """Initialize agent resources."""
        self._mcp_pool = await get_mcp_pool()
        self._llm_client = get_llm_client()

    @property
    def mcp(self) -> MCPClientPool:
        """Get MCP client pool."""
        if not self._mcp_pool:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        return self._mcp_pool

    @property
    def llm(self) -> LLMClient:
        """Get LLM client."""
        if not self._llm_client:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        return self._llm_client

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> MCPResponse:
        """Execute a tool via MCP.

        Args:
            tool_name: Tool name
            params: Tool parameters

        Returns:
            MCPResponse with result or error
        """
        start_time = time.perf_counter()

        mapping = get_tool_mapping(self.agent_type, tool_name)
        if not mapping:
            log.warning(
                "tool.unknown",
                agent=self.agent_type,
                tool=tool_name,
            )
            return MCPResponse(success=False, error=f"Unknown tool: {tool_name}")

        # Map parameters
        mcp_params = map_params(mapping, params)
        ticker = params.get("ticker") or params.get("symbol")

        log.info(
            "tool.executing",
            agent=self.agent_type,
            tool=tool_name,
            mcp_tool=mapping.mcp_tool,
            server=mapping.server.value,
            ticker=ticker,
            param_count=len(mcp_params),
        )

        try:
            if mapping.server == MCPServer.IB_MCP:
                result = await self.mcp.call_ib_mcp(mapping.mcp_tool, mcp_params)

            elif mapping.server == MCPServer.TRADING_RAG:
                result = await self.mcp.call_rag(mapping.mcp_tool, mcp_params)

            elif mapping.server == MCPServer.TRADING_GRAPH:
                result = await self.mcp.call_graph(mapping.mcp_tool, mcp_params)

            elif mapping.server == MCPServer.SUBPROCESS:
                result = await self._execute_subprocess(mapping, mcp_params)

            elif mapping.server == MCPServer.DATABASE:
                result = await self._execute_database(mapping, mcp_params)

            else:
                log.error("tool.unknown_server", server=mapping.server.value)
                return MCPResponse(success=False, error=f"Unknown server: {mapping.server}")

            duration_ms = (time.perf_counter() - start_time) * 1000
            result_size = len(str(result.result)) if result.result else 0

            log.info(
                "tool.completed",
                agent=self.agent_type,
                tool=tool_name,
                server=mapping.server.value,
                ticker=ticker,
                success=result.success,
                result_size=result_size,
                duration_ms=round(duration_ms, 2),
            )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "tool.failed",
                agent=self.agent_type,
                tool=tool_name,
                server=mapping.server.value,
                ticker=ticker,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            return MCPResponse(success=False, error=str(e))

    async def _execute_subprocess(self, mapping: ToolMapping, params: dict) -> MCPResponse:
        """Execute a subprocess command (e.g., Claude Code CLI).

        This is for long-running operations like full analysis.
        Returns immediately with a task ID for polling.
        """
        # For now, return a placeholder
        # In production, this would spawn a subprocess and return task_id
        return MCPResponse(
            success=True,
            result={
                "status": "queued",
                "message": f"Subprocess {mapping.mcp_tool} queued with params: {params}",
                "task_id": "task-placeholder",
            },
        )

    async def _execute_database(self, mapping: ToolMapping, params: dict) -> MCPResponse:
        """Execute a database operation.

        Uses the tradegent db_layer for queries.
        """
        # For now, return a placeholder
        # In production, this would query the database
        return MCPResponse(
            success=True,
            result={
                "status": "success",
                "message": f"Database {mapping.mcp_tool} executed with params: {params}",
            },
        )

    @abstractmethod
    async def process(
        self,
        query: str,
        tickers: list[str],
        context: ConversationContext,
    ) -> AgentResponse:
        """Process a user query.

        Args:
            query: User query
            tickers: Extracted tickers
            context: Conversation context

        Returns:
            AgentResponse with A2UI components
        """
        pass

    async def generate_response(
        self,
        query: str,
        tool_results: dict[str, Any],
        context: ConversationContext,
    ) -> dict:
        """Generate A2UI response from tool results.

        Args:
            query: User query
            tool_results: Results from tool executions
            context: Conversation context

        Returns:
            A2UI response dict
        """
        start_time = time.perf_counter()

        results_list = [
            {"tool": name, "result": result}
            for name, result in tool_results.items()
        ]

        log.info(
            "a2ui.generating",
            agent=self.agent_type,
            tool_count=len(results_list),
            query_length=len(query),
        )

        try:
            response = await self.llm.generate_a2ui(
                agent_type=self.agent_type,
                tool_results=results_list,
                user_query=query,
                context_summary=context.get_context_summary(),
                conversation_history=context.get_recent_messages(3),
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            component_types = [c.get("type") for c in response.get("components", [])]

            log.info(
                "a2ui.generated",
                agent=self.agent_type,
                component_count=len(response.get("components", [])),
                component_types=component_types,
                text_length=len(response.get("text", "")),
                duration_ms=round(duration_ms, 2),
            )

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "a2ui.failed",
                agent=self.agent_type,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            raise

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

    def get_tool_descriptions(self) -> dict[str, str]:
        """Get descriptions of available tools.

        Returns:
            Dict of tool name to description
        """
        return {name: mapping.description for name, mapping in self.tools.items()}
