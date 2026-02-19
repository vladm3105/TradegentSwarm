"""RAG search tools."""

import sys
from datetime import date
from pathlib import Path

# Add trader package to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trader"))

from rag.search import (
    semantic_search,
    get_similar_analyses,
    get_learnings_for_topic,
    get_rag_stats,
    list_documents,
)


def rag_search(
    query: str,
    ticker: str | None = None,
    doc_type: str | None = None,
    section: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    top_k: int = 5,
    min_similarity: float = 0.3,
) -> dict:
    """
    Semantic search across embedded documents.

    Args:
        query: Search query
        ticker: Filter by ticker
        doc_type: Filter by document type
        section: Filter by section
        date_from: Date range start
        date_to: Date range end
        top_k: Maximum results
        min_similarity: Minimum similarity threshold

    Returns:
        Search results
    """
    results = semantic_search(
        query=query,
        ticker=ticker,
        doc_type=doc_type,
        section=section,
        date_from=date_from,
        date_to=date_to,
        top_k=top_k,
        min_similarity=min_similarity,
    )
    return {"results": [r.to_dict() for r in results]}


def rag_similar(
    ticker: str,
    analysis_type: str | None = None,
    top_k: int = 3,
) -> dict:
    """
    Find similar past analyses for a ticker.

    Args:
        ticker: Ticker symbol
        analysis_type: Optional analysis type filter
        top_k: Maximum results

    Returns:
        Similar analyses
    """
    results = get_similar_analyses(
        ticker=ticker,
        analysis_type=analysis_type,
        top_k=top_k,
    )
    return {"results": [r.to_dict() for r in results]}


def rag_learnings(topic: str, top_k: int = 5) -> dict:
    """
    Find learnings related to a topic.

    Args:
        topic: Topic to search for
        top_k: Maximum results

    Returns:
        Related learnings
    """
    results = get_learnings_for_topic(topic=topic, top_k=top_k)
    return {"results": [r.to_dict() for r in results]}


def rag_status() -> dict:
    """
    Get RAG statistics.

    Returns:
        Document and chunk counts
    """
    stats = get_rag_stats()
    return stats.to_dict()


def rag_list(
    ticker: str | None = None,
    doc_type: str | None = None,
    limit: int = 50,
) -> dict:
    """
    List embedded documents.

    Args:
        ticker: Filter by ticker
        doc_type: Filter by document type
        limit: Maximum results

    Returns:
        Document list
    """
    documents = list_documents(ticker=ticker, doc_type=doc_type, limit=limit)
    return {"documents": documents}
