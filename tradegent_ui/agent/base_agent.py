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
        For tradegent_analyze, runs the tradegent CLI and returns results.
        """
        import asyncio
        import json
        from pathlib import Path

        if mapping.mcp_tool == "tradegent_analyze":
            ticker = params.get("ticker", "").upper()
            analysis_type = params.get("type", "stock")

            if not ticker:
                return MCPResponse(success=False, error="Ticker is required")

            # Run tradegent CLI
            tradegent_dir = Path("/opt/data/tradegent_swarm/tradegent")
            cmd = [
                "python", "tradegent.py", "analyze", ticker,
                "--type", analysis_type
            ]

            log.info(
                "subprocess.starting",
                tool=mapping.mcp_tool,
                ticker=ticker,
                analysis_type=analysis_type,
            )

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(tradegent_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**dict(__import__("os").environ), "PYTHONUNBUFFERED": "1"},
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=600  # 10 minute timeout
                )

                stdout_text = stdout.decode() if stdout else ""
                stderr_text = stderr.decode() if stderr else ""

                if process.returncode != 0:
                    log.error(
                        "subprocess.failed",
                        ticker=ticker,
                        returncode=process.returncode,
                        stderr=stderr_text[:500],
                    )
                    return MCPResponse(
                        success=False,
                        error=f"Analysis failed: {stderr_text[:200]}",
                    )

                # Parse output for result info
                result = {
                    "status": "completed",
                    "ticker": ticker,
                    "analysis_type": analysis_type,
                    "output": stdout_text[-2000:] if len(stdout_text) > 2000 else stdout_text,
                }

                # Combine stdout and stderr for parsing (some output may go to stderr)
                combined_output = stdout_text + "\n" + stderr_text

                # Try to extract key metrics from output
                import re
                import glob as glob_module

                # Extract file path from output
                file_path = None
                if match := re.search(r"File:\s*(.+\.yaml)", combined_output):
                    file_path = match.group(1).strip()
                elif match := re.search(r"(tradegent_knowledge/knowledge/[^\s]+\.yaml)", combined_output):
                    file_path = match.group(1).strip()
                elif match := re.search(r"(/[^\s]+\.yaml)", combined_output):
                    file_path = match.group(1).strip()

                # Fallback: find most recent YAML file for this ticker
                if not file_path:
                    knowledge_dirs = [
                        f"/opt/data/tradegent_swarm/tradegent_knowledge/knowledge/analysis/{analysis_type}",
                        "/opt/data/tradegent_swarm/tradegent_knowledge/knowledge/analysis/stock",
                        "/opt/data/tradegent_swarm/tradegent_knowledge/knowledge/analysis/earnings",
                    ]
                    for kdir in knowledge_dirs:
                        pattern = f"{kdir}/{ticker}_*.yaml"
                        files = sorted(glob_module.glob(pattern), key=lambda x: Path(x).stat().st_mtime, reverse=True)
                        if files:
                            # Check if file was created in the last 15 minutes
                            import time
                            if time.time() - Path(files[0]).stat().st_mtime < 900:
                                file_path = files[0]
                                log.info("subprocess.file_found_by_search", file_path=file_path, ticker=ticker)
                                break

                if file_path:
                    result["file_path"] = file_path

                if match := re.search(r"Gate:\s*(\w+)", combined_output):
                    result["gate_result"] = match.group(1).strip()
                if match := re.search(r"Rec:\s*(\w+)", combined_output):
                    result["recommendation"] = match.group(1).strip()
                if match := re.search(r"\((\d+)%\)", combined_output):
                    result["confidence"] = int(match.group(1))

                log.info(
                    "subprocess.completed",
                    ticker=ticker,
                    file_path=result.get("file_path"),
                    gate_result=result.get("gate_result"),
                    recommendation=result.get("recommendation"),
                )

                # Auto-ingest to knowledge base (RAG + Graph + DB)
                if result.get("file_path"):
                    await self._auto_ingest(result["file_path"], ticker)
                else:
                    log.warning("subprocess.no_file_path", ticker=ticker, output_snippet=combined_output[:500])

                return MCPResponse(success=True, result=result)

            except asyncio.TimeoutError:
                log.error("subprocess.timeout", ticker=ticker)
                return MCPResponse(
                    success=False,
                    error=f"Analysis timeout for {ticker} (5 min limit)",
                )
            except Exception as e:
                log.error("subprocess.error", ticker=ticker, error=str(e))
                return MCPResponse(success=False, error=str(e))

        # Default: placeholder for other subprocess tools
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

    async def _auto_ingest(self, file_path: str, ticker: str) -> None:
        """Auto-ingest analysis file to knowledge base (RAG + Graph + DB).

        Calls tradegent/scripts/ingest.py to handle:
        - RAG embedding (pgvector)
        - Graph extraction (Neo4j)
        - Database storage (PostgreSQL kb_* tables)
        """
        import asyncio
        from pathlib import Path

        knowledge_base = Path("/opt/data/tradegent_swarm/tradegent_knowledge/knowledge")
        tradegent_dir = Path("/opt/data/tradegent_swarm/tradegent")

        # Resolve the file path
        file_path_obj = Path(file_path)

        # Handle relative paths from tradegent directory
        if not file_path_obj.is_absolute():
            # Check if it's relative to tradegent dir (e.g., ../tradegent_knowledge/...)
            if file_path.startswith(".."):
                file_path_obj = (tradegent_dir / file_path).resolve()
            elif file_path.startswith("tradegent_knowledge"):
                file_path_obj = Path("/opt/data/tradegent_swarm") / file_path
            else:
                # Check common locations
                candidates = [
                    knowledge_base / "analysis" / "stock" / file_path_obj.name,
                    knowledge_base / "analysis" / "earnings" / file_path_obj.name,
                    tradegent_dir / "analyses" / file_path_obj.name,
                ]
                for candidate in candidates:
                    if candidate.exists():
                        file_path_obj = candidate
                        break

        # Verify file exists
        if not file_path_obj.exists():
            log.warning("ingest.file_not_found", file_path=str(file_path_obj), original_path=file_path, ticker=ticker)
            return

        log.info("ingest.file_resolved", original=file_path, resolved=str(file_path_obj), ticker=ticker)

        # Run ingest.py
        cmd = ["python", "scripts/ingest.py", str(file_path_obj)]

        log.info("ingest.starting", file_path=str(file_path_obj), ticker=ticker)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(tradegent_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(__import__("os").environ), "PYTHONUNBUFFERED": "1"},
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120  # 2 minute timeout for ingest
            )

            stdout_text = stdout.decode() if stdout else ""
            stderr_text = stderr.decode() if stderr else ""

            if process.returncode == 0:
                log.info("ingest.completed", ticker=ticker, output=stdout_text[:200])
            else:
                log.warning(
                    "ingest.partial_failure",
                    ticker=ticker,
                    returncode=process.returncode,
                    stderr=stderr_text[:200],
                )

        except asyncio.TimeoutError:
            log.error("ingest.timeout", ticker=ticker)
        except Exception as e:
            log.error("ingest.error", ticker=ticker, error=str(e))

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
