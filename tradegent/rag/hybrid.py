"""Combined vector + graph context builder."""

import logging

from .models import HybridContext, SearchResult
from .search import get_learnings_for_topic, get_similar_analyses, semantic_search

log = logging.getLogger(__name__)


def get_hybrid_context(
    ticker: str,
    query: str,
    analysis_type: str | None = None,
    exclude_doc_id: str | None = None,
) -> HybridContext:
    """
    Combine vector search + graph context for Claude.

    Steps:
    1. Vector search: past analyses for this ticker
    2. Vector search: similar analyses for peer tickers (from graph)
    3. Vector search: relevant learnings and biases
    4. Graph search: structural context (peers, competitors, risks, strategies)
    5. Format into context block

    Args:
        ticker: Ticker symbol
        query: Search query
        analysis_type: Optional analysis type filter
        exclude_doc_id: Document ID to exclude (prevents self-retrieval)

    Returns:
        HybridContext with combined results
    """
    ticker = ticker.upper()

    # Vector search results
    vector_results = []

    # Track excluded doc_id to prevent self-retrieval
    excluded_ids = {exclude_doc_id} if exclude_doc_id else set()

    # 1. Past analyses for this ticker
    ticker_results = get_similar_analyses(ticker, analysis_type, top_k=3)
    for r in ticker_results:
        if r.doc_id not in excluded_ids:
            vector_results.append(r)

    # 2. Query-based search
    query_results = semantic_search(
        query=query,
        ticker=ticker,
        top_k=3,
    )
    # Dedupe against ticker results and excluded docs
    seen_ids = {r.doc_id for r in vector_results} | excluded_ids
    for r in query_results:
        if r.doc_id not in seen_ids:
            vector_results.append(r)
            seen_ids.add(r.doc_id)

    # 3. Relevant learnings
    learning_results = get_learnings_for_topic(query, top_k=2)
    for r in learning_results:
        if r.doc_id not in seen_ids:
            vector_results.append(r)
            seen_ids.add(r.doc_id)

    # 4. Graph context (import here to avoid circular dependency)
    graph_context = {}
    try:
        try:
            from trader.graph.layer import TradingGraph
        except ImportError:
            from graph.layer import TradingGraph
        with TradingGraph() as graph:
            if graph.health_check():
                graph_context = graph.get_ticker_context(ticker)
    except Exception as e:
        log.warning(f"Graph context unavailable: {e}")

    # 5. Format combined context
    formatted = format_context(vector_results, graph_context, ticker)

    return HybridContext(
        ticker=ticker,
        vector_results=vector_results,
        graph_context=graph_context,
        formatted=formatted,
    )


def build_analysis_context(ticker: str, analysis_type: str) -> str:
    """
    Build pre-analysis context for Claude skills.

    Includes:
    - Past analyses for this ticker (top 3)
    - Similar analyses for peer tickers (top 2)
    - Relevant learnings (top 3)
    - Graph structural context

    Args:
        ticker: Ticker symbol
        analysis_type: Type of analysis being performed

    Returns:
        Formatted context string
    """
    context = get_hybrid_context(
        ticker=ticker,
        query=f"{analysis_type} for {ticker}",
        analysis_type=analysis_type,
    )
    return context.formatted


def format_context(
    vector_results: list[SearchResult],
    graph_context: dict,
    ticker: str,
) -> str:
    """Format hybrid context as markdown for Claude."""
    sections = []

    # Header
    sections.append(f"## Context for {ticker}\n")

    # Graph context
    if graph_context:
        graph_sections = []

        # Check for empty graph status
        if graph_context.get("_status") == "empty":
            sections.append("### Knowledge Graph\n")
            sections.append("*Graph context unavailable - no data indexed yet.*")
            sections.append(f"*Tip: {graph_context.get('_message', 'Run graph extraction on analysis documents')}*")
            sections.append("")
        else:
            # Peers
            peers = graph_context.get("peers", [])
            if peers:
                peer_list = ", ".join([p.get("peer", "") for p in peers[:5]])
                graph_sections.append(f"**Sector Peers**: {peer_list}")

            # Competitors
            competitors = graph_context.get("competitors", [])
            if competitors:
                comp_list = ", ".join([c.get("competitor", "") for c in competitors[:5]])
                graph_sections.append(f"**Competitors**: {comp_list}")

            # Risks
            risks = graph_context.get("risks", [])
            if risks:
                risk_list = ", ".join([r.get("risk", "") for r in risks[:5]])
                graph_sections.append(f"**Known Risks**: {risk_list}")

            # Supply chain
            supply = graph_context.get("supply_chain", {})
            if supply.get("suppliers"):
                graph_sections.append(f"**Suppliers**: {', '.join(supply['suppliers'][:5])}")
            if supply.get("customers"):
                graph_sections.append(f"**Customers**: {', '.join(supply['customers'][:5])}")

            if graph_sections:
                sections.append("### Knowledge Graph\n")
                sections.append("\n".join(graph_sections))
                sections.append("")
            elif graph_context.get("symbol"):
                # Graph has data but nothing for this specific ticker
                sections.append("### Knowledge Graph\n")
                sections.append(f"*No relationships found for {ticker} in the knowledge graph.*")
                sections.append("")

    # Vector search results
    if vector_results:
        sections.append("### Past Analyses\n")

        for result in vector_results[:5]:
            sections.append(f"**{result.doc_id}** ({result.doc_type})")
            sections.append(f"*Section: {result.section_label}*")
            sections.append(f"Similarity: {result.similarity:.2f}")
            # Truncate content
            content = result.content[:500]
            if len(result.content) > 500:
                content += "..."
            sections.append(f"```\n{content}\n```")
            sections.append("")

    return "\n".join(sections)


def get_bias_warnings(ticker: str) -> list[dict]:
    """
    Get bias warnings for a ticker based on past trades.

    Args:
        ticker: Ticker symbol

    Returns:
        List of bias warnings with context
    """
    warnings = []

    try:
        try:
            from trader.graph.layer import TradingGraph
        except ImportError:
            from graph.layer import TradingGraph
        with TradingGraph() as graph:
            # Skip queries on empty graph to avoid label warnings
            if graph.health_check() and graph.is_populated():
                # Get biases detected in trades for this ticker
                bias_history = graph.run_cypher(
                    """
                    MATCH (b:Bias)-[:DETECTED_IN]->(t:Trade)-[:TRADED]->(tk:Ticker {symbol: $symbol})
                    RETURN b.name AS bias, t.outcome AS outcome, count(*) AS occurrences
                    ORDER BY occurrences DESC
                """,
                    {"symbol": ticker.upper()},
                )

                for row in bias_history:
                    warnings.append(
                        {
                            "bias": row["bias"],
                            "occurrences": row["occurrences"],
                            "last_outcome": row["outcome"],
                        }
                    )

    except Exception as e:
        log.warning(f"Could not get bias warnings: {e}")

    return warnings


def get_strategy_recommendations(ticker: str) -> list[dict]:
    """
    Get strategy recommendations for a ticker based on historical performance.

    Args:
        ticker: Ticker symbol

    Returns:
        List of strategy recommendations
    """
    recommendations = []

    try:
        try:
            from trader.graph.layer import TradingGraph
        except ImportError:
            from graph.layer import TradingGraph
        with TradingGraph() as graph:
            # Skip queries on empty graph to avoid label warnings
            if graph.health_check() and graph.is_populated():
                strategies = graph.run_cypher(
                    """
                    MATCH (s:Strategy)-[r:WORKS_FOR]->(tk:Ticker {symbol: $symbol})
                    WHERE r.sample_size >= 3
                    RETURN s.name AS strategy, r.win_rate AS win_rate, r.sample_size AS trades
                    ORDER BY r.win_rate DESC
                """,
                    {"symbol": ticker.upper()},
                )

                for row in strategies:
                    recommendations.append(
                        {
                            "strategy": row["strategy"],
                            "win_rate": row["win_rate"],
                            "trades": row["trades"],
                        }
                    )

    except Exception as e:
        log.warning(f"Could not get strategy recommendations: {e}")

    return recommendations
