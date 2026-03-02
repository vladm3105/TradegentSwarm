"""
Tradegent Knowledge Base Dashboard
==================================
Multi-layer dashboard for PostgreSQL, Neo4j, and RAG data.

Run: cd tradegent && streamlit run dashboard/app.py
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_layer import NexusDB


def query_df(db: NexusDB, sql: str) -> pd.DataFrame:
    """Execute SQL and return as DataFrame (handles psycopg3 dict rows)."""
    rows = db.conn.execute(sql).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


st.set_page_config(
    page_title="Tradegent Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize DB connection
@st.cache_resource
def get_db():
    db = NexusDB()
    db.connect()
    return db

db = get_db()

# Sidebar navigation
st.sidebar.title("📈 Tradegent")
page = st.sidebar.radio(
    "Navigate",
    ["Overview", "Analyses", "Trades", "Knowledge Graph", "RAG Explorer", "Calibration"]
)

# =============================================================================
# PAGE: Overview
# =============================================================================
if page == "Overview":
    st.title("Trading Dashboard Overview")

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        result = db.conn.execute("""
            SELECT COUNT(*) as cnt FROM nexus.stocks WHERE is_enabled = true
        """).fetchone()
        st.metric("Active Stocks", result['cnt'] if result else 0)

    with col2:
        result = db.conn.execute("""
            SELECT COUNT(*) as cnt FROM nexus.analysis_results
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        """).fetchone()
        st.metric("Analyses (7d)", result['cnt'] if result else 0)

    with col3:
        result = db.conn.execute("""
            SELECT COUNT(*) as cnt FROM nexus.trades WHERE status = 'open'
        """).fetchone()
        st.metric("Open Trades", result['cnt'] if result else 0)

    with col4:
        result = db.conn.execute("""
            SELECT COUNT(*) as cnt FROM nexus.watchlist WHERE status = 'active'
        """).fetchone()
        st.metric("Watchlist", result['cnt'] if result else 0)

    st.divider()

    # Recent analyses
    st.subheader("Recent Analyses")
    analyses_df = query_df(db, """
        SELECT ticker, analysis_type, recommendation, confidence,
               expected_value_pct, gate_passed, created_at
        FROM nexus.analysis_results
        ORDER BY created_at DESC
        LIMIT 10
    """)

    if not analyses_df.empty:
        st.dataframe(
            analyses_df,
            column_config={
                "ticker": "Ticker",
                "analysis_type": "Type",
                "recommendation": st.column_config.TextColumn("Rec"),
                "confidence": st.column_config.ProgressColumn("Conf %", min_value=0, max_value=100),
                "expected_value_pct": st.column_config.NumberColumn("EV %", format="%.1f"),
                "gate_passed": st.column_config.CheckboxColumn("Gate"),
                "created_at": st.column_config.DatetimeColumn("Date", format="MMM DD HH:mm")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No analyses yet")

    # Service status
    st.subheader("Service Status")
    status = db.conn.execute("""
        SELECT state, last_heartbeat, cumulative_ticks,
               cumulative_analyses, cumulative_executions
        FROM nexus.service_status
        LIMIT 1
    """).fetchone()

    if status:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("State", status['state'])
        hb = status['last_heartbeat']
        col2.metric("Last Heartbeat", hb.strftime("%H:%M:%S") if hb else "N/A")
        col3.metric("Total Analyses", status['cumulative_analyses'])
        col4.metric("Total Executions", status['cumulative_executions'])

# =============================================================================
# PAGE: Analyses
# =============================================================================
elif page == "Analyses":
    st.title("Analysis History")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker_filter = st.text_input("Ticker", "").upper()
    with col2:
        type_filter = st.selectbox("Type", ["All", "earnings", "stock"])
    with col3:
        days = st.slider("Days", 1, 90, 30)

    # Build query
    query_sql = """
        SELECT ticker, analysis_type, recommendation, confidence,
               expected_value_pct, entry_price, stop_price, target_price,
               gate_passed, created_at
        FROM nexus.analysis_results
        WHERE created_at >= CURRENT_DATE - INTERVAL '%s days'
    """ % days

    if ticker_filter:
        query_sql += f" AND ticker = '{ticker_filter}'"
    if type_filter != "All":
        query_sql += f" AND analysis_type = '{type_filter}'"

    query_sql += " ORDER BY created_at DESC"

    df = query_df(db, query_sql)

    # Summary stats
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Analyses", len(df))
        col2.metric("Avg Confidence", f"{df['confidence'].mean():.0f}%")
        col3.metric("Gate Pass Rate", f"{df['gate_passed'].mean()*100:.0f}%")

        st.dataframe(df, use_container_width=True, hide_index=True)

        # Recommendation distribution
        st.subheader("Recommendation Distribution")
        rec_counts = df['recommendation'].value_counts()
        st.bar_chart(rec_counts)
    else:
        st.info("No analyses found for filters")

# =============================================================================
# PAGE: Trades
# =============================================================================
elif page == "Trades":
    st.title("Trade Journal")

    tab1, tab2 = st.tabs(["Open Positions", "Closed Trades"])

    with tab1:
        open_trades = query_df(db, """
            SELECT ticker, entry_date, entry_price, position_size, trade_type,
                   source_analysis
            FROM nexus.trades
            WHERE status = 'open'
            ORDER BY entry_date DESC
        """)

        if not open_trades.empty:
            st.dataframe(open_trades, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions")

    with tab2:
        closed_trades = query_df(db, """
            SELECT ticker, entry_date, entry_price, exit_date, exit_price,
                   pnl_dollars, pnl_percent, exit_reason
            FROM nexus.trades
            WHERE status = 'closed'
            ORDER BY exit_date DESC
            LIMIT 50
        """)

        if not closed_trades.empty:
            # P&L summary
            total_pnl = closed_trades['pnl_dollars'].sum()
            win_rate = (closed_trades['pnl_dollars'] > 0).mean() * 100

            col1, col2 = st.columns(2)
            col1.metric("Total P&L", f"${total_pnl:,.2f}", delta_color="normal")
            col2.metric("Win Rate", f"{win_rate:.0f}%")

            st.dataframe(closed_trades, use_container_width=True, hide_index=True)
        else:
            st.info("No closed trades")

# =============================================================================
# PAGE: Knowledge Graph
# =============================================================================
elif page == "Knowledge Graph":
    st.title("Knowledge Graph Explorer")

    st.info("💡 For full graph visualization, use [Neo4j Browser](http://localhost:7474) or Neo4j Bloom")

    # Quick stats from Neo4j
    try:
        from graph.layer import TradingGraph

        @st.cache_resource
        def get_graph():
            g = TradingGraph()
            g.connect()
            return g

        graph = get_graph()
        stats = graph.get_stats()

        st.subheader("Node Counts")
        node_df = pd.DataFrame([
            {"Type": k, "Count": v}
            for k, v in stats.node_counts.items()
        ]).sort_values("Count", ascending=False)
        st.bar_chart(node_df.set_index("Type"))

        st.subheader("Relationship Counts")
        edge_df = pd.DataFrame([
            {"Type": k, "Count": v}
            for k, v in stats.edge_counts.items()
        ]).sort_values("Count", ascending=False)
        st.bar_chart(edge_df.set_index("Type"))

        # Ticker context lookup
        st.subheader("Ticker Context")
        ticker = st.text_input("Enter ticker", "NVDA").upper()
        if ticker:
            ctx = graph.get_ticker_context(ticker)

            col1, col2 = st.columns(2)
            with col1:
                st.write("**Peers:**", ctx.get("peers", []))
                st.write("**Risks:**", ctx.get("risks", []))
            with col2:
                st.write("**Strategies:**", ctx.get("strategies", []))
                st.write("**Biases:**", ctx.get("biases", []))

    except Exception as e:
        st.error(f"Neo4j connection failed: {e}")
        st.write("Make sure Neo4j is running: `docker compose up -d neo4j`")

# =============================================================================
# PAGE: RAG Explorer
# =============================================================================
elif page == "RAG Explorer":
    st.title("RAG Document Explorer")

    # Document stats
    doc_stats = query_df(db, """
        SELECT doc_type, COUNT(*) as count, SUM(chunk_count) as chunks
        FROM nexus.rag_documents
        GROUP BY doc_type
        ORDER BY count DESC
    """)

    if not doc_stats.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Documents by Type")
            st.bar_chart(doc_stats.set_index("doc_type")["count"])
        with col2:
            st.subheader("Chunks by Type")
            st.bar_chart(doc_stats.set_index("doc_type")["chunks"])

    # Document browser
    st.subheader("Recent Documents")
    docs = query_df(db, """
        SELECT doc_id, doc_type, ticker, doc_date, chunk_count, created_at
        FROM nexus.rag_documents
        ORDER BY created_at DESC
        LIMIT 20
    """)

    if not docs.empty:
        st.dataframe(docs, use_container_width=True, hide_index=True)

    # Semantic search
    st.subheader("Semantic Search")
    search_query = st.text_input("Search query", "earnings surprise")
    search_ticker = st.text_input("Filter by ticker (optional)", "").upper()

    if st.button("Search"):
        try:
            from rag.search import semantic_search

            results = semantic_search(
                search_query,
                ticker=search_ticker if search_ticker else None,
                top_k=5
            )

            for r in results:
                with st.expander(f"{r.doc_id} (score: {r.similarity:.3f})"):
                    st.write(r.content[:500] + "..." if len(r.content) > 500 else r.content)
        except Exception as e:
            st.error(f"Search failed: {e}")

# =============================================================================
# PAGE: Calibration
# =============================================================================
elif page == "Calibration":
    st.title("Confidence Calibration")

    st.write("Tracks stated confidence vs actual accuracy to improve predictions")

    calibration = query_df(db, """
        SELECT ticker, analysis_type, confidence_bucket,
               total_predictions, correct_predictions,
               ROUND(actual_accuracy * 100, 1) as accuracy_pct
        FROM nexus.confidence_calibration
        WHERE total_predictions >= 3
        ORDER BY confidence_bucket, ticker
    """)

    if not calibration.empty:
        # Overall calibration chart
        overall = calibration.groupby("confidence_bucket").agg({
            "total_predictions": "sum",
            "correct_predictions": "sum"
        }).reset_index()
        overall["accuracy"] = overall["correct_predictions"] / overall["total_predictions"] * 100
        overall["expected"] = overall["confidence_bucket"]

        st.subheader("Calibration Curve")
        chart_data = overall[["confidence_bucket", "accuracy", "expected"]].set_index("confidence_bucket")
        st.line_chart(chart_data)

        st.caption("Ideal: accuracy line matches expected line (45° diagonal)")

        # Detail table
        st.subheader("By Ticker")
        st.dataframe(calibration, use_container_width=True, hide_index=True)
    else:
        st.info("Not enough data for calibration (need 3+ predictions per bucket)")

# External Services Links
st.sidebar.divider()
st.sidebar.subheader("🔗 Other Tools")
st.sidebar.markdown("""
- [Metabase BI](http://localhost:3001) - SQL & Charts
- [Neo4j Browser](http://localhost:7475) - Graph Viz
- [Portal Home](http://localhost:8000) - All Services
""")

# Footer
st.sidebar.divider()
st.sidebar.caption(f"Connected to: {db.conn.info.host}:{db.conn.info.port}")
