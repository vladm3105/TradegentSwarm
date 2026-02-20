#!/usr/bin/env python3
"""Test graph pipeline: extract entities → store in Neo4j → query relationships."""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Add trader to path
trader_path = Path(__file__).parent.parent / "trader"
sys.path.insert(0, str(trader_path))

# Load .env BEFORE importing graph modules
graph_env = trader_path / "graph" / ".env"
if graph_env.exists():
    load_dotenv(graph_env)

from graph.layer import TradingGraph
from graph.extract import extract_text, _commit_to_graph

# A shorter trading story for faster extraction
STORY = """
NVIDIA (NVDA) beat Q4 earnings with $22B revenue. CEO Jensen Huang cited AI demand.
Competitors AMD and Intel trail in data center GPUs.
Key risk: China export restrictions reduce TAM by 15%.
Trading thesis: Long NVDA at $800, target $1200, stop $700.
"""


def main():
    print("=" * 70)
    print("Graph Test: Extract → Store → Query")
    print("=" * 70)

    # Step 1: Check Neo4j connection
    print("\n[1] Checking Neo4j connection...")
    try:
        with TradingGraph() as graph:
            stats = graph.get_stats()
            print(f"    Connected to Neo4j")
            print(f"    Nodes: {stats.total_nodes}, Edges: {stats.total_edges}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return 1

    # Step 2: Extract entities from text
    print("\n[2] Extracting entities from story...")
    try:
        result = extract_text(
            text=STORY,
            doc_type="research",
            doc_id="test_nvda_analysis",
            extractor="ollama",
        )
        print(f"    Entities: {len(result.entities)}")
        print(f"    Relations: {len(result.relations)}")
        print(f"    Extractor: {result.extractor}")

        if result.entities:
            print(f"    Sample entities:")
            for e in result.entities[:5]:
                print(f"      - {e.type}: {e.value}")

        # Commit to Neo4j
        print(f"    Committing to Neo4j...")
        _commit_to_graph(result)
        print(f"    Committed!")
    except Exception as e:
        print(f"    ERROR extracting: {e}")
        return 1

    # Step 3: Query the graph
    print("\n[3] Querying graph for NVDA context...")
    try:
        with TradingGraph() as graph:
            # Get ticker context
            context = graph.get_ticker_context("NVDA")

            print(f"    Peers: {len(context.get('peers', []))}")
            if context.get('peers'):
                print(f"      {', '.join(context['peers'][:5])}")

            print(f"    Competitors: {len(context.get('competitors', []))}")
            if context.get('competitors'):
                print(f"      {', '.join(context['competitors'][:5])}")

            print(f"    Risks: {len(context.get('risks', []))}")
            if context.get('risks'):
                for r in context['risks'][:3]:
                    print(f"      - {r}")

            print(f"    Strategies: {len(context.get('strategies', []))}")
            if context.get('strategies'):
                for s in context['strategies'][:2]:
                    print(f"      - {s}")

    except Exception as e:
        print(f"    ERROR querying: {e}")
        return 1

    # Step 4: Run custom Cypher query
    print("\n[4] Running custom Cypher query...")
    try:
        with TradingGraph() as graph:
            results = graph.run_cypher(
                "MATCH (t:Ticker {symbol: $ticker})-[r]->(n) "
                "RETURN type(r) as rel_type, labels(n)[0] as node_type, n.name as name "
                "LIMIT 10",
                {"ticker": "NVDA"}
            )
            print(f"    Found {len(results)} relationships:")
            for r in results[:5]:
                print(f"      {r.get('rel_type', '?')} -> {r.get('node_type', '?')}: {r.get('name', 'N/A')}")
    except Exception as e:
        print(f"    ERROR in Cypher: {e}")

    print("\n" + "=" * 70)
    print("Graph Test Complete")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
