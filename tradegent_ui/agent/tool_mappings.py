"""Tool to MCP server mappings."""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class MCPServer(Enum):
    """Available MCP servers."""

    IB_MCP = "ib-mcp"
    TRADING_RAG = "trading-rag"
    TRADING_GRAPH = "trading-graph"
    SUBPROCESS = "subprocess"  # For Claude Code CLI
    DATABASE = "database"  # Direct DB operations


@dataclass
class ToolMapping:
    """Mapping from agent tool to MCP implementation."""

    server: MCPServer
    mcp_tool: str  # Actual MCP tool name
    description: str
    params_map: dict[str, str]  # Agent param -> MCP param
    requires_ticker: bool = False


# AnalysisAgent tools
ANALYSIS_TOOLS: dict[str, ToolMapping] = {
    "run_analysis": ToolMapping(
        server=MCPServer.SUBPROCESS,
        mcp_tool="tradegent_analyze",
        description="Run full stock/earnings analysis via Claude Code CLI",
        params_map={
            "ticker": "ticker",
            "analysis_type": "type",
            "query": "query",
            "session_id": "session_id",
        },
        requires_ticker=True,
    ),
    "get_analysis": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_search",
        description="Retrieve past analysis from RAG",
        params_map={"ticker": "ticker", "query": "query"},
        requires_ticker=True,
    ),
    "validate_analysis": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_search",
        description="Search for validation status",
        params_map={"ticker": "ticker"},
        requires_ticker=True,
    ),
    "compare_analyses": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_similar",
        description="Find similar analyses for comparison",
        params_map={"ticker": "ticker", "analysis_type": "analysis_type"},
        requires_ticker=True,
    ),
    "get_forecast_status": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="query",
        description="Check forecast validity from database",
        params_map={"ticker": "ticker"},
        requires_ticker=True,
    ),
    "list_recent_analyses": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_search",
        description="List recent analyses",
        params_map={"query": "query", "top_k": "top_k"},
    ),
    "get_analysis_lineage": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="query",
        description="Get analysis validation chain",
        params_map={"ticker": "ticker"},
        requires_ticker=True,
    ),
    "invalidate_analysis": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="update",
        description="Mark analysis as invalidated",
        params_map={"ticker": "ticker", "reason": "reason"},
        requires_ticker=True,
    ),
}

# TradeAgent tools
TRADE_TOOLS: dict[str, ToolMapping] = {
    "journal_entry": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="insert",
        description="Log trade entry to database",
        params_map={
            "ticker": "ticker",
            "direction": "direction",
            "entry_price": "entry_price",
            "size": "size",
            "stop_loss": "stop_loss",
            "target": "target",
        },
        requires_ticker=True,
    ),
    "journal_exit": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="update",
        description="Log trade exit to database",
        params_map={
            "ticker": "ticker",
            "exit_price": "exit_price",
            "exit_reason": "reason",
        },
        requires_ticker=True,
    ),
    "execute_order": ToolMapping(
        server=MCPServer.IB_MCP,
        mcp_tool="place_order",
        description="Place order via IB Gateway",
        params_map={
            "ticker": "symbol",
            "action": "action",
            "quantity": "quantity",
            "order_type": "order_type",
            "limit_price": "limit_price",
        },
        requires_ticker=True,
    ),
    "get_trade": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="query",
        description="Get trade details from database",
        params_map={"ticker": "ticker", "trade_id": "trade_id"},
    ),
    "review_trade": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_search",
        description="Search for trade review",
        params_map={"ticker": "ticker", "query": "query"},
        requires_ticker=True,
    ),
    "analyze_fill": ToolMapping(
        server=MCPServer.IB_MCP,
        mcp_tool="get_executions",
        description="Get fill details from IB",
        params_map={"ticker": "symbol"},
        requires_ticker=True,
    ),
}

# PortfolioAgent tools
PORTFOLIO_TOOLS: dict[str, ToolMapping] = {
    "get_positions": ToolMapping(
        server=MCPServer.IB_MCP,
        mcp_tool="get_positions",
        description="Get current portfolio positions",
        params_map={},
    ),
    "get_pnl": ToolMapping(
        server=MCPServer.IB_MCP,
        mcp_tool="get_pnl",
        description="Get P&L summary",
        params_map={},
    ),
    "get_account_summary": ToolMapping(
        server=MCPServer.IB_MCP,
        mcp_tool="get_account_summary",
        description="Get account balances and metrics",
        params_map={},
    ),
    "get_watchlist": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="query",
        description="Get active watchlist entries",
        params_map={"status": "status"},
    ),
    "add_to_watchlist": ToolMapping(
        server=MCPServer.DATABASE,
        mcp_tool="insert",
        description="Add entry to watchlist",
        params_map={
            "ticker": "ticker",
            "trigger_type": "trigger_type",
            "trigger_value": "trigger_value",
            "priority": "priority",
            "expires": "expires",
        },
        requires_ticker=True,
    ),
    "get_open_orders": ToolMapping(
        server=MCPServer.IB_MCP,
        mcp_tool="get_open_orders",
        description="Get pending orders",
        params_map={},
    ),
    "cancel_order": ToolMapping(
        server=MCPServer.IB_MCP,
        mcp_tool="cancel_order",
        description="Cancel an open order",
        params_map={"order_id": "order_id"},
    ),
}

# ResearchAgent tools
RESEARCH_TOOLS: dict[str, ToolMapping] = {
    "rag_search": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_search",
        description="Semantic search across documents",
        params_map={"query": "query", "ticker": "ticker", "top_k": "top_k"},
    ),
    "rag_similar": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_similar",
        description="Find similar past analyses",
        params_map={"ticker": "ticker", "analysis_type": "analysis_type", "top_k": "top_k"},
        requires_ticker=True,
    ),
    "graph_context": ToolMapping(
        server=MCPServer.TRADING_GRAPH,
        mcp_tool="graph_context",
        description="Get comprehensive ticker context",
        params_map={"ticker": "ticker"},
        requires_ticker=True,
    ),
    "graph_peers": ToolMapping(
        server=MCPServer.TRADING_GRAPH,
        mcp_tool="graph_peers",
        description="Get sector peers and competitors",
        params_map={"ticker": "ticker"},
        requires_ticker=True,
    ),
    "web_search": ToolMapping(
        server=MCPServer.SUBPROCESS,
        mcp_tool="brave_web_search",
        description="Web search for news and catalysts",
        params_map={"query": "query"},
    ),
    "get_ticker_profile": ToolMapping(
        server=MCPServer.TRADING_RAG,
        mcp_tool="rag_search",
        description="Get ticker profile from knowledge base",
        params_map={"ticker": "ticker", "query": "ticker profile"},
        requires_ticker=True,
    ),
}

# All tools by agent type
AGENT_TOOLS = {
    "analysis": ANALYSIS_TOOLS,
    "trade": TRADE_TOOLS,
    "portfolio": PORTFOLIO_TOOLS,
    "research": RESEARCH_TOOLS,
}


def get_tool_mapping(agent_type: str, tool_name: str) -> ToolMapping | None:
    """Get tool mapping for an agent tool.

    Args:
        agent_type: Agent type (analysis, trade, portfolio, research)
        tool_name: Tool name

    Returns:
        ToolMapping if found, None otherwise
    """
    tools = AGENT_TOOLS.get(agent_type, {})
    return tools.get(tool_name)


def get_agent_tools(agent_type: str) -> dict[str, ToolMapping]:
    """Get all tools for an agent type.

    Args:
        agent_type: Agent type

    Returns:
        Dict of tool name to mapping
    """
    return AGENT_TOOLS.get(agent_type, {})


def map_params(mapping: ToolMapping, params: dict[str, Any]) -> dict[str, Any]:
    """Map agent parameters to MCP parameters.

    Args:
        mapping: Tool mapping
        params: Agent parameters

    Returns:
        MCP parameters
    """
    mcp_params = {}
    for agent_param, mcp_param in mapping.params_map.items():
        if agent_param in params:
            mcp_params[mcp_param] = params[agent_param]
    return mcp_params
