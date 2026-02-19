"""Graph query tools."""

import sys
from pathlib import Path

# Add trader package to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trader"))

from graph.layer import TradingGraph


def graph_search(ticker: str, depth: int = 2) -> dict:
    """
    Find all nodes connected to a ticker within N hops.

    Args:
        ticker: Ticker symbol
        depth: Maximum hops

    Returns:
        Related nodes
    """
    with TradingGraph() as graph:
        results = graph.find_related(ticker.upper(), depth=depth)
        return {"results": results}


def graph_peers(ticker: str) -> dict:
    """
    Get sector peers and competitors for a ticker.

    Args:
        ticker: Ticker symbol

    Returns:
        Peers and competitors
    """
    with TradingGraph() as graph:
        peers = graph.get_sector_peers(ticker.upper())
        competitors = graph.get_competitors(ticker.upper())
        return {"peers": peers, "competitors": competitors}


def graph_risks(ticker: str) -> dict:
    """
    Get known risks for a ticker.

    Args:
        ticker: Ticker symbol

    Returns:
        Risk list
    """
    with TradingGraph() as graph:
        return {"risks": graph.get_risks(ticker.upper())}


def graph_biases(bias_name: str | None = None) -> dict:
    """
    Get bias history across trades.

    Args:
        bias_name: Optional filter by bias name

    Returns:
        Bias history
    """
    with TradingGraph() as graph:
        return {"biases": graph.get_bias_history(bias_name)}


def graph_context(ticker: str) -> dict:
    """
    Get comprehensive context for a ticker.

    Args:
        ticker: Ticker symbol

    Returns:
        Full context (peers, risks, strategies, biases)
    """
    with TradingGraph() as graph:
        return graph.get_ticker_context(ticker.upper())


def graph_query(cypher: str, params: dict | None = None) -> dict:
    """
    Execute raw Cypher query.

    Args:
        cypher: Cypher query string
        params: Query parameters

    Returns:
        Query results
    """
    with TradingGraph() as graph:
        results = graph.run_cypher(cypher, params or {})
        return {"results": results}
