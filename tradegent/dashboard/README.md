# Tradegent Dashboard

Multi-layer dashboard for exploring the knowledge base across PostgreSQL, Neo4j, and RAG.

## Quick Start

```bash
cd tradegent

# Install dependencies
pip install streamlit pandas

# Run dashboard
streamlit run dashboard/app.py
```

Dashboard opens at: http://localhost:8501

## Pages

| Page | Data Source | Shows |
|------|-------------|-------|
| **Overview** | PostgreSQL | Key metrics, recent analyses, service status |
| **Analyses** | PostgreSQL | Analysis history with filters |
| **Trades** | PostgreSQL | Open positions, closed trades, P&L |
| **Knowledge Graph** | Neo4j | Node/edge counts, ticker context |
| **RAG Explorer** | pgvector | Documents by type, semantic search |
| **Calibration** | PostgreSQL | Confidence vs accuracy tracking |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Dashboard                    │
├─────────────────────────────────────────────────────────┤
│                          │                               │
│  ┌───────────────────────┼───────────────────────────┐  │
│  │                       │                           │  │
│  ▼                       ▼                           ▼  │
│ PostgreSQL            Neo4j                      pgvector │
│ (nexus.*)          (Knowledge)                   (RAG)    │
│                                                           │
│ • stocks           • Ticker nodes              • documents│
│ • trades           • Company nodes             • chunks   │
│ • analysis_results • Relationships             • embeddings│
│ • schedules        • Context queries           • search   │
│ • calibration                                             │
└───────────────────────────────────────────────────────────┘
```

## Environment

Requires `.env` or environment variables:

```bash
export PG_USER=tradegent
export PG_PASS=<password>
export PG_DB=tradegent
export PG_HOST=localhost
export PG_PORT=5433
export NEO4J_URI=bolt://localhost:7688
export NEO4J_USER=neo4j
export NEO4J_PASS=<password>
```

## For Full Graph Visualization

Use Neo4j Browser or Bloom:

```bash
# Neo4j Browser
open http://localhost:7474

# Connect with bolt://localhost:7688
# Username: neo4j
```

## Extending the Dashboard

Add new pages by adding elif blocks in `app.py`:

```python
elif page == "My New Page":
    st.title("My Page")
    # Query data
    df = pd.read_sql("SELECT ...", db.conn)
    # Display
    st.dataframe(df)
```
