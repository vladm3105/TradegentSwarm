"""MCP server providing RAG tools for Claude skills."""

import asyncio
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback to tradegent/.env
    trader_env = Path(__file__).parent.parent / ".env"
    if trader_env.exists():
        load_dotenv(trader_env)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

log = logging.getLogger(__name__)

# Create MCP server
server = Server("trading-rag")


# Tool definitions
TOOLS = [
    Tool(
        name="rag_embed",
        description="Embed a YAML document for semantic search",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to YAML file"},
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Re-embed even if unchanged"
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="rag_embed_text",
        description="Embed raw text for semantic search",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to embed"},
                "doc_id": {"type": "string", "description": "Document identifier"},
                "doc_type": {"type": "string", "description": "Document type"},
                "ticker": {"type": "string", "description": "Optional ticker symbol"},
            },
            "required": ["text", "doc_id", "doc_type"],
        },
    ),
    Tool(
        name="rag_search",
        description="Semantic search across embedded documents",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "ticker": {"type": "string", "description": "Filter by ticker"},
                "doc_type": {"type": "string", "description": "Filter by document type"},
                "section": {"type": "string", "description": "Filter by section"},
                "top_k": {"type": "integer", "default": 5, "description": "Max results"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="rag_similar",
        description="Find similar past analyses for a ticker",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol"},
                "analysis_type": {"type": "string", "description": "Optional analysis type"},
                "top_k": {"type": "integer", "default": 3, "description": "Max results"},
            },
            "required": ["ticker"],
        },
    ),
    Tool(
        name="rag_hybrid_context",
        description="Get combined vector + graph context for analysis",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol"},
                "query": {"type": "string", "description": "Search query"},
                "analysis_type": {"type": "string", "description": "Optional analysis type"},
            },
            "required": ["ticker", "query"],
        },
    ),
    Tool(
        name="rag_status",
        description="Get RAG statistics (document/chunk counts)",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = await _execute_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _execute_tool(name: str, args: dict) -> dict:
    """Execute a tool and return result."""
    from .embed import embed_document, embed_text
    from .search import semantic_search, get_similar_analyses, get_rag_stats
    from .hybrid import get_hybrid_context
    from .exceptions import RAGUnavailableError, EmbedError

    if name == "rag_embed":
        result = embed_document(
            file_path=args["file_path"],
            force=args.get("force", False),
        )
        return result.to_dict()

    elif name == "rag_embed_text":
        result = embed_text(
            text=args["text"],
            doc_id=args["doc_id"],
            doc_type=args["doc_type"],
            ticker=args.get("ticker"),
        )
        return result.to_dict()

    elif name == "rag_search":
        results = semantic_search(
            query=args["query"],
            ticker=args.get("ticker"),
            doc_type=args.get("doc_type"),
            section=args.get("section"),
            top_k=args.get("top_k", 5),
        )
        return {"results": [r.to_dict() for r in results]}

    elif name == "rag_similar":
        results = get_similar_analyses(
            ticker=args["ticker"],
            analysis_type=args.get("analysis_type"),
            top_k=args.get("top_k", 3),
        )
        return {"results": [r.to_dict() for r in results]}

    elif name == "rag_hybrid_context":
        result = get_hybrid_context(
            ticker=args["ticker"],
            query=args["query"],
            analysis_type=args.get("analysis_type"),
        )
        return result.to_dict()

    elif name == "rag_status":
        stats = get_rag_stats()
        return stats.to_dict()

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
