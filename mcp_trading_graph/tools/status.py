"""Graph status tools."""

import sys
from pathlib import Path

# Add trader package to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trader"))

from graph.layer import TradingGraph


def graph_status() -> dict:
    """
    Get graph statistics.

    Returns:
        Node/edge counts by type
    """
    with TradingGraph() as graph:
        stats = graph.get_stats()
        return stats.to_dict()


def graph_health() -> dict:
    """
    Health check for graph service.

    Returns:
        Health status
    """
    try:
        with TradingGraph() as graph:
            if graph.health_check():
                return {"status": "healthy", "neo4j": "connected"}
            return {"status": "unhealthy", "neo4j": "disconnected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
