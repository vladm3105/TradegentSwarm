"""Graph API endpoints for knowledge graph visualization."""

import structlog
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from ..auth import get_current_user, UserClaims
from agent.mcp_client import get_mcp_pool

router = APIRouter(prefix="/api/graph", tags=["graph"])
log = structlog.get_logger()


# Response Models
class GraphStatsResponse(BaseModel):
    """Graph statistics."""
    node_count: int
    edge_count: int
    node_types: dict[str, int]
    last_extraction: Optional[str] = None


class GraphContextResponse(BaseModel):
    """Ticker context from graph."""
    ticker: str
    peers: list[dict]
    competitors: list[dict]
    risks: list[dict]
    patterns: list[dict]
    signals: list[dict]
    biases: list[dict]
    strategies: list[dict]


class GraphSearchResponse(BaseModel):
    """Graph search results for visualization."""
    ticker: str
    nodes: list[dict]
    links: list[dict]
    depth: int


# Endpoints
@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats(
    user: UserClaims = Depends(get_current_user),
) -> GraphStatsResponse:
    """Get graph statistics (node/edge counts, types)."""
    try:
        pool = await get_mcp_pool()
        result = await pool.call_graph("graph_status", {})

        if not result.success:
            log.error("graph.stats.failed", error=result.error)
            raise HTTPException(status_code=502, detail=f"Graph service error: {result.error}")

        stats = result.result
        return GraphStatsResponse(
            node_count=stats.get("total_nodes", 0),
            edge_count=stats.get("total_edges", 0),
            node_types=stats.get("node_counts", {}),
            last_extraction=stats.get("last_extraction"),
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("graph.stats.exception", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/{ticker}", response_model=GraphContextResponse)
async def get_graph_context(
    ticker: str,
    user: UserClaims = Depends(get_current_user),
) -> GraphContextResponse:
    """Get comprehensive graph context for a ticker."""
    try:
        pool = await get_mcp_pool()
        result = await pool.call_graph("graph_context", {"ticker": ticker.upper()})

        if not result.success:
            log.error("graph.context.failed", ticker=ticker, error=result.error)
            raise HTTPException(status_code=502, detail=f"Graph service error: {result.error}")

        ctx = result.result
        return GraphContextResponse(
            ticker=ticker.upper(),
            peers=ctx.get("peers", []),
            competitors=ctx.get("competitors", []),
            risks=ctx.get("risks", []),
            patterns=ctx.get("patterns", []),
            signals=ctx.get("signals", []),
            biases=ctx.get("biases", []),
            strategies=ctx.get("strategies", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("graph.context.exception", ticker=ticker, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/{ticker}", response_model=GraphSearchResponse)
async def search_graph(
    ticker: str,
    depth: int = Query(2, ge=1, le=3, description="Max hops from ticker (1-3)"),
    user: UserClaims = Depends(get_current_user),
) -> GraphSearchResponse:
    """Search graph for nodes connected to ticker within N hops.

    Returns nodes and links formatted for force-graph visualization.
    Uses Cypher query to get actual relationship types.
    Limited to depth 3 and max 200 nodes for performance.
    """
    try:
        pool = await get_mcp_pool()
        ticker_upper = ticker.upper()

        # Use graph_search_full for all depths - returns proper nodes AND relationships
        result = await pool.call_graph("graph_search_full", {
            "ticker": ticker_upper,
            "depth": depth,
        })

        if not result.success:
            log.warning("graph.search.full_failed", ticker=ticker, error=result.error)
            # Fallback to old graph_search (nodes only with RELATED_TO links)
            fallback_result = await pool.call_graph("graph_search", {
                "ticker": ticker_upper,
                "depth": depth,
            })
            if not fallback_result.success:
                log.error("graph.search.failed", ticker=ticker, error=fallback_result.error)
                raise HTTPException(status_code=502, detail=f"Graph service error: {fallback_result.error}")

            # Process graph_search results (nodes only, create RELATED_TO links)
            fallback_data = fallback_result.result
            raw_nodes = fallback_data.get("results", [])
            center_id = f"Ticker:{ticker_upper}"
            nodes = [{"id": center_id, "label": ticker_upper, "type": "Ticker"}]
            links = []
            seen_ids = {center_id}

            for item in raw_nodes:
                labels = item.get("labels", [])
                props = item.get("props", {})
                node_type = labels[0] if labels else "Unknown"

                if "symbol" in props:
                    node_id = f"Ticker:{props['symbol']}"
                    node_label = props["symbol"]
                elif "name" in props:
                    name = props["name"]
                    if node_type == "Document" and "/" in name:
                        name = name.split("/")[-1].replace(".yaml", "")
                    node_id = f"{node_type}:{name}"
                    node_label = name
                else:
                    continue

                if node_id not in seen_ids:
                    nodes.append({"id": node_id, "label": node_label, "type": node_type, "properties": props})
                    seen_ids.add(node_id)
                    links.append({"source": center_id, "target": node_id, "type": "RELATED_TO"})

            return GraphSearchResponse(ticker=ticker_upper, nodes=nodes, links=links, depth=depth)

        # Process graph_search_full results (has proper nodes and edges)
        graph_data = result.result
        nodes = graph_data.get("nodes", [])
        links = graph_data.get("edges", [])

        # Ensure center ticker node exists
        center_id = f"Ticker:{ticker_upper}"
        if not any(n.get("id") == center_id for n in nodes):
            nodes.insert(0, {"id": center_id, "label": ticker_upper, "type": "Ticker"})

        # Limit to 200 nodes for performance
        if len(nodes) > 200:
            log.warning("graph.search.truncated", ticker=ticker, original=len(nodes))
            nodes = nodes[:200]
            node_ids = {n.get("id") for n in nodes}
            links = [l for l in links if l.get("source") in node_ids and l.get("target") in node_ids]

        log.info("graph.search.complete", ticker=ticker, nodes=len(nodes), links=len(links), depth=depth)

        return GraphSearchResponse(ticker=ticker_upper, nodes=nodes, links=links, depth=depth)

    except HTTPException:
        raise
    except Exception as e:
        log.error("graph.search.exception", ticker=ticker, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
