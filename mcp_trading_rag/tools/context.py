"""RAG context tools."""

import sys
from pathlib import Path

# Add trader package to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trader"))

from rag.hybrid import (
    get_hybrid_context,
    build_analysis_context,
    get_bias_warnings,
    get_strategy_recommendations,
)


def rag_hybrid_context(
    ticker: str,
    query: str,
    analysis_type: str | None = None,
) -> dict:
    """
    Get combined vector + graph context for analysis.

    Args:
        ticker: Ticker symbol
        query: Search query
        analysis_type: Optional analysis type

    Returns:
        Hybrid context with formatted output
    """
    result = get_hybrid_context(
        ticker=ticker,
        query=query,
        analysis_type=analysis_type,
    )
    return result.to_dict()


def rag_analysis_context(ticker: str, analysis_type: str) -> dict:
    """
    Build pre-analysis context for Claude skills.

    Args:
        ticker: Ticker symbol
        analysis_type: Type of analysis being performed

    Returns:
        Formatted context string
    """
    context = build_analysis_context(ticker=ticker, analysis_type=analysis_type)
    return {"ticker": ticker, "analysis_type": analysis_type, "context": context}


def rag_bias_warnings(ticker: str) -> dict:
    """
    Get bias warnings for a ticker based on past trades.

    Args:
        ticker: Ticker symbol

    Returns:
        List of bias warnings
    """
    warnings = get_bias_warnings(ticker)
    return {"ticker": ticker, "warnings": warnings}


def rag_strategy_recommendations(ticker: str) -> dict:
    """
    Get strategy recommendations for a ticker.

    Args:
        ticker: Ticker symbol

    Returns:
        Strategy recommendations with performance data
    """
    recommendations = get_strategy_recommendations(ticker)
    return {"ticker": ticker, "recommendations": recommendations}
