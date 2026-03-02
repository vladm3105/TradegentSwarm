#!/usr/bin/env python3
"""
Metabase Portal Dashboard Setup
===============================
Creates a starter portal dashboard with links and key metrics.

Prerequisites:
1. Metabase running at http://localhost:3001
2. Initial setup completed (admin account created)
3. Database connection configured

Usage:
    python dashboard/setup_metabase_portal.py --email admin@example.com --password yourpassword

Or set environment variables:
    export METABASE_EMAIL=admin@example.com
    export METABASE_PASSWORD=yourpassword
    python dashboard/setup_metabase_portal.py
"""
import requests
import json
import os
import argparse
from typing import Optional

METABASE_URL = os.getenv("METABASE_URL", "http://localhost:3001")


def get_session(email: str, password: str) -> Optional[str]:
    """Login and get session token."""
    try:
        resp = requests.post(
            f"{METABASE_URL}/api/session",
            json={"username": email, "password": password},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("id")
        else:
            print(f"Login failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None


def get_database_id(session: str) -> Optional[int]:
    """Find the tradegent database ID."""
    resp = requests.get(
        f"{METABASE_URL}/api/database",
        headers={"X-Metabase-Session": session},
        timeout=10
    )
    if resp.status_code == 200:
        for db in resp.json().get("data", []):
            if "tradegent" in db.get("name", "").lower():
                return db["id"]
        # Return first non-sample database
        for db in resp.json().get("data", []):
            if db.get("id") != 1:  # Skip sample database
                return db["id"]
    return None


def create_dashboard(session: str, name: str, description: str) -> Optional[int]:
    """Create a new dashboard."""
    resp = requests.post(
        f"{METABASE_URL}/api/dashboard",
        headers={"X-Metabase-Session": session},
        json={"name": name, "description": description},
        timeout=10
    )
    if resp.status_code == 200:
        return resp.json().get("id")
    else:
        print(f"Failed to create dashboard: {resp.text}")
        return None


def add_text_card(session: str, dashboard_id: int, text: str, row: int, col: int,
                  size_x: int = 6, size_y: int = 4) -> bool:
    """Add a text/markdown card to dashboard."""
    resp = requests.post(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
        headers={"X-Metabase-Session": session},
        json={
            "cardId": None,
            "row": row,
            "col": col,
            "size_x": size_x,
            "size_y": size_y,
            "visualization_settings": {
                "virtual_card": {
                    "name": None,
                    "display": "text",
                    "visualization_settings": {},
                    "dataset_query": {},
                    "archived": False
                },
                "text": text
            }
        },
        timeout=10
    )
    return resp.status_code == 200


def add_query_card(session: str, dashboard_id: int, database_id: int,
                   name: str, query: str, display: str,
                   row: int, col: int, size_x: int = 6, size_y: int = 4) -> bool:
    """Add a native query card to dashboard."""
    # First create the card/question
    card_resp = requests.post(
        f"{METABASE_URL}/api/card",
        headers={"X-Metabase-Session": session},
        json={
            "name": name,
            "dataset_query": {
                "type": "native",
                "native": {"query": query},
                "database": database_id
            },
            "display": display,
            "visualization_settings": {}
        },
        timeout=10
    )

    if card_resp.status_code != 200:
        print(f"Failed to create card '{name}': {card_resp.text}")
        return False

    card_id = card_resp.json().get("id")

    # Add card to dashboard
    resp = requests.post(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
        headers={"X-Metabase-Session": session},
        json={
            "cardId": card_id,
            "row": row,
            "col": col,
            "size_x": size_x,
            "size_y": size_y
        },
        timeout=10
    )
    return resp.status_code == 200


def setup_portal_dashboard(email: str, password: str, url: str = None):
    """Create the complete portal dashboard."""
    global METABASE_URL
    if url:
        METABASE_URL = url

    print("=" * 50)
    print("Metabase Portal Dashboard Setup")
    print("=" * 50)

    # Login
    print("\n1. Logging in...")
    session = get_session(email, password)
    if not session:
        print("   ✗ Login failed. Check credentials.")
        return False
    print("   ✓ Logged in")

    # Get database
    print("\n2. Finding database...")
    db_id = get_database_id(session)
    if not db_id:
        print("   ✗ No database found. Configure database in Metabase first.")
        return False
    print(f"   ✓ Using database ID: {db_id}")

    # Create dashboard
    print("\n3. Creating dashboard...")
    dashboard_id = create_dashboard(
        session,
        "📈 Tradegent Portal",
        "Trading platform home - links, metrics, and quick access"
    )
    if not dashboard_id:
        print("   ✗ Failed to create dashboard")
        return False
    print(f"   ✓ Created dashboard ID: {dashboard_id}")

    # Add cards
    print("\n4. Adding cards...")

    # Row 0: Header and Quick Links
    header_text = """# 📈 Tradegent Trading Platform

Welcome to your trading command center. Access all tools and view key metrics.

---

## 🔗 Quick Links

| Tool | URL | Purpose |
|------|-----|---------|
| **Streamlit** | [localhost:8501](http://localhost:8501) | Custom dashboards, RAG search |
| **Neo4j Browser** | [localhost:7475](http://localhost:7475) | Knowledge graph visualization |
| **IB Gateway VNC** | [localhost:5902](http://localhost:5902) | Paper trading gateway |
| **PostgreSQL** | localhost:5433 | Database (psql/DBeaver) |

---"""

    if add_text_card(session, dashboard_id, header_text, row=0, col=0, size_x=12, size_y=5):
        print("   ✓ Added header card")

    # Row 5: Key Metrics
    metrics_header = """## 📊 Key Metrics"""
    if add_text_card(session, dashboard_id, metrics_header, row=5, col=0, size_x=12, size_y=1):
        print("   ✓ Added metrics header")

    # Metric cards
    metrics = [
        ("Active Stocks", "SELECT COUNT(*) as count FROM nexus.stocks WHERE is_enabled = true", "scalar", 6, 0, 4, 3),
        ("Analyses (7d)", "SELECT COUNT(*) as count FROM nexus.analysis_results WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'", "scalar", 6, 4, 4, 3),
        ("Open Trades", "SELECT COUNT(*) as count FROM nexus.trades WHERE status = 'open'", "scalar", 6, 8, 4, 3),
    ]

    for name, query, display, row, col, size_x, size_y in metrics:
        if add_query_card(session, dashboard_id, db_id, name, query, display, row, col, size_x, size_y):
            print(f"   ✓ Added metric: {name}")
        else:
            print(f"   ✗ Failed: {name}")

    # Row 9: Recent Activity header
    activity_header = """## 📋 Recent Activity"""
    if add_text_card(session, dashboard_id, activity_header, row=9, col=0, size_x=12, size_y=1):
        print("   ✓ Added activity header")

    # Row 10: Recent Analyses table
    recent_analyses_query = """
SELECT
    ticker,
    analysis_type::text as type,
    recommendation,
    confidence || '%' as confidence,
    COALESCE(expected_value_pct::text || '%', '-') as "EV%",
    CASE WHEN gate_passed THEN '✓' ELSE '✗' END as gate,
    TO_CHAR(created_at, 'MM-DD HH24:MI') as date
FROM nexus.analysis_results
ORDER BY created_at DESC
LIMIT 10
"""
    if add_query_card(session, dashboard_id, db_id, "Recent Analyses",
                      recent_analyses_query, "table", 10, 0, 12, 6):
        print("   ✓ Added recent analyses table")

    # Row 16: Service Status
    status_header = """## 🖥️ Service Status"""
    if add_text_card(session, dashboard_id, status_header, row=16, col=0, size_x=12, size_y=1):
        print("   ✓ Added status header")

    service_status_query = """
SELECT
    state,
    TO_CHAR(last_heartbeat, 'YYYY-MM-DD HH24:MI:SS') as last_heartbeat,
    ticks_total as total_ticks,
    analyses_total as total_analyses,
    today_analyses,
    CASE
        WHEN last_heartbeat > NOW() - INTERVAL '5 minutes' THEN '🟢 Healthy'
        WHEN last_heartbeat > NOW() - INTERVAL '15 minutes' THEN '🟡 Degraded'
        ELSE '🔴 Unhealthy'
    END as health
FROM nexus.service_status
"""
    if add_query_card(session, dashboard_id, db_id, "Service Status",
                      service_status_query, "table", 17, 0, 12, 3):
        print("   ✓ Added service status")

    # Row 20: Knowledge Base Stats
    kb_header = """## 📚 Knowledge Base"""
    if add_text_card(session, dashboard_id, kb_header, row=20, col=0, size_x=12, size_y=1):
        print("   ✓ Added KB header")

    kb_stats_query = """
SELECT
    doc_type,
    COUNT(*) as documents,
    SUM(chunk_count) as chunks,
    COUNT(DISTINCT ticker) as tickers
FROM nexus.rag_documents
GROUP BY doc_type
ORDER BY documents DESC
"""
    if add_query_card(session, dashboard_id, db_id, "Documents by Type",
                      kb_stats_query, "bar", 21, 0, 6, 4):
        print("   ✓ Added KB stats chart")

    stock_watchlist_query = """
SELECT
    ticker,
    state,
    CASE WHEN is_enabled THEN '✓' ELSE '✗' END as enabled,
    priority,
    default_analysis_type::text as type,
    TO_CHAR(next_earnings_date, 'MM-DD') as earnings
FROM nexus.stocks
ORDER BY priority DESC, ticker
LIMIT 15
"""
    if add_query_card(session, dashboard_id, db_id, "Stock Watchlist",
                      stock_watchlist_query, "table", 21, 6, 6, 4):
        print("   ✓ Added stock watchlist")

    print("\n" + "=" * 50)
    print("✓ Portal dashboard created successfully!")
    print(f"\nOpen: {METABASE_URL}/dashboard/{dashboard_id}")
    print("\nTo set as homepage:")
    print("  1. Go to Admin Settings → Homepage")
    print("  2. Select 'A specific dashboard'")
    print("  3. Choose '📈 Tradegent Portal'")
    print("=" * 50)

    return True


def main():
    parser = argparse.ArgumentParser(description="Setup Metabase Portal Dashboard")
    parser.add_argument("--email", default=os.getenv("METABASE_EMAIL"),
                        help="Metabase admin email")
    parser.add_argument("--password", default=os.getenv("METABASE_PASSWORD"),
                        help="Metabase admin password")
    parser.add_argument("--url", default=METABASE_URL,
                        help="Metabase URL (default: http://localhost:3001)")

    args = parser.parse_args()

    if not args.email or not args.password:
        print("Error: Email and password required")
        print("\nUsage:")
        print("  python setup_metabase_portal.py --email admin@example.com --password pass")
        print("\nOr set environment variables:")
        print("  export METABASE_EMAIL=admin@example.com")
        print("  export METABASE_PASSWORD=yourpassword")
        return

    if args.url != METABASE_URL:
        setup_portal_dashboard(args.email, args.password, args.url)
    else:
        setup_portal_dashboard(args.email, args.password)


if __name__ == "__main__":
    main()
