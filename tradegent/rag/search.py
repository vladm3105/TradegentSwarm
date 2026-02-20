"""Semantic search with optional metadata filters."""

import logging
from datetime import date
from typing import Any

import psycopg

from .models import SearchResult, RAGStats
from .embedding_client import get_embedding, get_embed_dimensions
from .schema import get_database_url
from .exceptions import RAGUnavailableError

log = logging.getLogger(__name__)


def semantic_search(
    query: str,
    ticker: str | None = None,
    doc_type: str | None = None,
    section: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    top_k: int = 5,
    min_similarity: float = 0.3,
) -> list[SearchResult]:
    """
    Semantic search across embedded documents.

    Similarity interpretation:
    - > 0.8: Near-identical content (dedup candidate)
    - 0.6 - 0.8: Highly relevant (primary context)
    - 0.4 - 0.6: Somewhat relevant (supporting context)
    - 0.3 - 0.4: Loosely related (include if few results)
    - < 0.3: Irrelevant (exclude)

    Args:
        query: Search query text
        ticker: Filter by ticker symbol
        doc_type: Filter by document type
        section: Filter by section label
        date_from: Filter by date (inclusive)
        date_to: Filter by date (inclusive)
        top_k: Maximum results to return
        min_similarity: Minimum similarity threshold

    Returns:
        List of SearchResult objects
    """
    # Get query embedding
    try:
        query_embedding = get_embedding(query)
    except Exception as e:
        raise RAGUnavailableError(f"Failed to embed query: {e}")

    # Build query with filters
    sql, params = _build_search_query(
        query_embedding, ticker, doc_type, section, date_from, date_to, top_k
    )

    try:
        with psycopg.connect(get_database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        raise RAGUnavailableError(f"Search query failed: {e}")

    # Convert to SearchResult objects
    results = []
    for row in rows:
        similarity = 1 - row[8]  # Convert distance to similarity
        if similarity < min_similarity:
            continue

        results.append(SearchResult(
            doc_id=row[0],
            file_path=row[1],
            doc_type=row[2],
            ticker=row[3],
            doc_date=row[4],
            section_label=row[5],
            content=row[6],
            similarity=similarity,
        ))

    return results


def hybrid_search(
    query: str,
    ticker: str | None = None,
    doc_type: str | None = None,
    section: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    top_k: int = 5,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    min_score: float = 0.01,
) -> list[SearchResult]:
    """
    Hybrid BM25 + Vector search using Reciprocal Rank Fusion (RRF).

    Combines semantic similarity (vector) with exact term matching (BM25).
    Useful for queries with specific terms like ticker symbols or metric names.

    RRF Formula: score = w_vec / (k + rank_vec) + w_bm25 / (k + rank_bm25)
    where k = 60 (standard RRF constant)

    Args:
        query: Search query text
        ticker: Filter by ticker symbol
        doc_type: Filter by document type
        section: Filter by section label
        date_from: Filter by date (inclusive)
        date_to: Filter by date (inclusive)
        top_k: Maximum results to return
        vector_weight: Weight for vector similarity (default 0.7)
        bm25_weight: Weight for BM25 text match (default 0.3)
        min_score: Minimum hybrid score threshold

    Returns:
        List of SearchResult objects sorted by hybrid score
    """
    # Get query embedding for vector search
    try:
        query_embedding = get_embedding(query)
    except Exception as e:
        raise RAGUnavailableError(f"Failed to embed query: {e}")

    # Build and execute hybrid query
    sql, params = _build_hybrid_query(
        query=query,
        embedding=query_embedding,
        ticker=ticker,
        doc_type=doc_type,
        section=section,
        date_from=date_from,
        date_to=date_to,
        top_k=top_k,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
    )

    try:
        with psycopg.connect(get_database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        log.warning(f"Hybrid search failed, falling back to vector: {e}")
        # Fallback to pure vector search if hybrid fails (e.g., missing tsv column)
        return semantic_search(
            query=query,
            ticker=ticker,
            doc_type=doc_type,
            section=section,
            date_from=date_from,
            date_to=date_to,
            top_k=top_k,
        )

    # Convert to SearchResult objects
    results = []
    for row in rows:
        hybrid_score = row[8]
        if hybrid_score < min_score:
            continue

        results.append(SearchResult(
            doc_id=row[0],
            file_path=row[1],
            doc_type=row[2],
            ticker=row[3],
            doc_date=row[4],
            section_label=row[5],
            content=row[6],
            similarity=hybrid_score,  # Using hybrid score as similarity
        ))

    return results


def _build_hybrid_query(
    query: str,
    embedding: list[float],
    ticker: str | None,
    doc_type: str | None,
    section: str | None,
    date_from: date | None,
    date_to: date | None,
    top_k: int,
    vector_weight: float,
    bm25_weight: float,
) -> tuple[str, list]:
    """
    Build hybrid search SQL using RRF (Reciprocal Rank Fusion).

    Uses CTEs to:
    1. Get top 50 vector similarity results
    2. Get top 50 BM25 full-text results
    3. Combine with RRF scoring
    """
    # Build filter clause (reused in both CTEs)
    filter_clause = ""
    filter_params = []

    if ticker:
        filter_clause += " AND c.ticker = %s"
        filter_params.append(ticker.upper())

    if doc_type:
        filter_clause += " AND c.doc_type = %s"
        filter_params.append(doc_type)

    if section:
        filter_clause += " AND c.section_label ILIKE %s"
        filter_params.append(f"%{section}%")

    if date_from:
        filter_clause += " AND c.doc_date >= %s"
        filter_params.append(date_from)

    if date_to:
        filter_clause += " AND c.doc_date <= %s"
        filter_params.append(date_to)

    embed_dims = get_embed_dimensions()
    sql = f"""
    WITH vector_results AS (
        SELECT c.id, d.doc_id, d.file_path, c.doc_type, c.ticker, c.doc_date,
               c.section_label, c.content, c.content_tokens,
               ROW_NUMBER() OVER (ORDER BY c.embedding <=> %s::vector({embed_dims})) as v_rank
        FROM nexus.rag_chunks c
        JOIN nexus.rag_documents d ON c.doc_id = d.id
        WHERE 1=1 {filter_clause}
        LIMIT 50
    ),
    bm25_results AS (
        SELECT c.id, d.doc_id, d.file_path, c.doc_type, c.ticker, c.doc_date,
               c.section_label, c.content, c.content_tokens,
               ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.content_tsv, plainto_tsquery('english', %s)) DESC) as b_rank
        FROM nexus.rag_chunks c
        JOIN nexus.rag_documents d ON c.doc_id = d.id
        WHERE c.content_tsv @@ plainto_tsquery('english', %s)
        {filter_clause}
        LIMIT 50
    )
    SELECT
        COALESCE(v.doc_id, b.doc_id) as doc_id,
        COALESCE(v.file_path, b.file_path) as file_path,
        COALESCE(v.doc_type, b.doc_type) as doc_type,
        COALESCE(v.ticker, b.ticker) as ticker,
        COALESCE(v.doc_date, b.doc_date) as doc_date,
        COALESCE(v.section_label, b.section_label) as section_label,
        COALESCE(v.content, b.content) as content,
        COALESCE(v.content_tokens, b.content_tokens) as content_tokens,
        (
            %s / (60.0 + COALESCE(v.v_rank, 1000)) +
            %s / (60.0 + COALESCE(b.b_rank, 1000))
        ) as hybrid_score
    FROM vector_results v
    FULL OUTER JOIN bm25_results b ON v.id = b.id
    ORDER BY hybrid_score DESC
    LIMIT %s
    """

    # Build params: embedding, filter_params (for vector), query, query, filter_params (for bm25), weights, top_k
    # Format embedding as PostgreSQL vector string (no spaces)
    emb_str = '[' + ','.join(str(x) for x in embedding) + ']'
    params = [emb_str] + filter_params + [query, query] + filter_params + [vector_weight, bm25_weight, top_k]

    return sql, params


def get_similar_analyses(
    ticker: str,
    analysis_type: str | None = None,
    top_k: int = 3,
) -> list[SearchResult]:
    """
    Find similar past analyses for a ticker.

    Args:
        ticker: Ticker symbol
        analysis_type: Optional document type filter
        top_k: Maximum results

    Returns:
        List of SearchResult objects
    """
    # Create a query based on ticker
    query = f"Trading analysis for {ticker}"
    if analysis_type:
        query += f" {analysis_type.replace('-', ' ')}"

    return semantic_search(
        query=query,
        ticker=ticker,
        doc_type=analysis_type,
        top_k=top_k,
    )


def get_learnings_for_topic(topic: str, top_k: int = 5) -> list[SearchResult]:
    """
    Find learnings related to a topic.

    Args:
        topic: Topic to search for
        top_k: Maximum results

    Returns:
        List of SearchResult objects
    """
    return semantic_search(
        query=f"Trading lessons and learnings about {topic}",
        doc_type="learning",
        top_k=top_k,
    )


def get_rag_stats() -> RAGStats:
    """Get RAG system statistics."""
    try:
        with psycopg.connect(get_database_url()) as conn:
            with conn.cursor() as cur:
                # Document count
                cur.execute("SELECT COUNT(*) FROM nexus.rag_documents")
                doc_count = cur.fetchone()[0]

                # Chunk count
                cur.execute("SELECT COUNT(*) FROM nexus.rag_chunks")
                chunk_count = cur.fetchone()[0]

                # Doc types
                cur.execute("""
                    SELECT doc_type, COUNT(*)
                    FROM nexus.rag_documents
                    GROUP BY doc_type
                """)
                doc_types = {row[0]: row[1] for row in cur.fetchall()}

                # Unique tickers
                cur.execute("""
                    SELECT DISTINCT ticker
                    FROM nexus.rag_documents
                    WHERE ticker IS NOT NULL
                    ORDER BY ticker
                """)
                tickers = [row[0] for row in cur.fetchall()]

                # Last embed
                cur.execute("SELECT MAX(updated_at) FROM nexus.rag_documents")
                last_embed = cur.fetchone()[0]

                # Get model info
                cur.execute("""
                    SELECT embed_model, embed_version
                    FROM nexus.rag_documents
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
                embed_model = row[0] if row else "unknown"
                embed_version = row[1] if row else "unknown"

        return RAGStats(
            document_count=doc_count,
            chunk_count=chunk_count,
            embed_model=embed_model,
            embed_version=embed_version,
            doc_types=doc_types,
            tickers=tickers,
            last_embed=last_embed,
        )

    except Exception as e:
        raise RAGUnavailableError(f"Failed to get stats: {e}")


def list_documents(
    ticker: str | None = None,
    doc_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List embedded documents with optional filters."""
    sql = """
        SELECT doc_id, file_path, doc_type, ticker, doc_date, chunk_count, updated_at
        FROM nexus.rag_documents
        WHERE 1=1
    """
    params = []

    if ticker:
        sql += " AND ticker = %s"
        params.append(ticker.upper())

    if doc_type:
        sql += " AND doc_type = %s"
        params.append(doc_type)

    sql += " ORDER BY updated_at DESC LIMIT %s"
    params.append(limit)

    try:
        with psycopg.connect(get_database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        raise RAGUnavailableError(f"List query failed: {e}")

    return [
        {
            "doc_id": row[0],
            "file_path": row[1],
            "doc_type": row[2],
            "ticker": row[3],
            "doc_date": row[4].isoformat() if row[4] else None,
            "chunk_count": row[5],
            "updated_at": row[6].isoformat() if row[6] else None,
        }
        for row in rows
    ]


def get_document_chunks(doc_id: str) -> list[dict]:
    """Get all chunks for a document."""
    try:
        with psycopg.connect(get_database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.section_path, c.section_label, c.chunk_index,
                           c.content, c.content_tokens
                    FROM nexus.rag_chunks c
                    JOIN nexus.rag_documents d ON c.doc_id = d.id
                    WHERE d.doc_id = %s
                    ORDER BY c.section_path, c.chunk_index
                """, (doc_id,))
                rows = cur.fetchall()
    except Exception as e:
        raise RAGUnavailableError(f"Query failed: {e}")

    return [
        {
            "section_path": row[0],
            "section_label": row[1],
            "chunk_index": row[2],
            "content": row[3],
            "content_tokens": row[4],
        }
        for row in rows
    ]


def _build_search_query(
    embedding: list[float],
    ticker: str | None,
    doc_type: str | None,
    section: str | None,
    date_from: date | None,
    date_to: date | None,
    top_k: int,
) -> tuple[str, list]:
    """Build SQL query with appropriate filters."""
    embed_dims = get_embed_dimensions()
    sql = f"""
        SELECT d.doc_id, d.file_path, d.doc_type, c.ticker, c.doc_date,
               c.section_label, c.content, c.content_tokens,
               c.embedding <=> %s::vector({embed_dims}) AS distance
        FROM nexus.rag_chunks c
        JOIN nexus.rag_documents d ON c.doc_id = d.id
        WHERE 1=1
    """
    # Format embedding as PostgreSQL vector string (no spaces)
    emb_str = '[' + ','.join(str(x) for x in embedding) + ']'
    params = [emb_str]

    if ticker:
        sql += " AND c.ticker = %s"
        params.append(ticker.upper())

    if doc_type:
        sql += " AND c.doc_type = %s"
        params.append(doc_type)

    if section:
        sql += " AND c.section_label ILIKE %s"
        params.append(f"%{section}%")

    if date_from:
        sql += " AND c.doc_date >= %s"
        params.append(date_from)

    if date_to:
        sql += " AND c.doc_date <= %s"
        params.append(date_to)

    sql += " ORDER BY distance LIMIT %s"
    params.append(top_k)

    return sql, params
