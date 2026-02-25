#!/usr/bin/env python3
"""
Initialize Graph Schema

Creates required labels, indexes, and seed data to prevent
query warnings about missing schema elements.

Usage:
    python scripts/init_graph_schema.py
    python scripts/init_graph_schema.py --seed  # Include sample data
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.layer import TradingGraph


def init_schema(graph: TradingGraph, seed: bool = False) -> dict:
    """
    Initialize graph schema with required labels and indexes.

    Returns:
        dict with created elements
    """
    results = {
        "constraints": [],
        "indexes": [],
        "nodes": [],
        "relationships": [],
        "errors": []
    }

    # Schema initialization queries
    schema_queries = [
        # Indexes for common lookups
        ("CREATE INDEX ticker_symbol IF NOT EXISTS FOR (t:Ticker) ON (t.symbol)", "index:ticker_symbol"),
        ("CREATE INDEX strategy_name IF NOT EXISTS FOR (s:Strategy) ON (s.name)", "index:strategy_name"),
        ("CREATE INDEX trade_id IF NOT EXISTS FOR (t:Trade) ON (t.id)", "index:trade_id"),
        ("CREATE INDEX document_id IF NOT EXISTS FOR (d:Document) ON (d.id)", "index:document_id"),

        # Constraints for uniqueness
        ("CREATE CONSTRAINT ticker_unique IF NOT EXISTS FOR (t:Ticker) REQUIRE t.symbol IS UNIQUE", "constraint:ticker_unique"),
        ("CREATE CONSTRAINT trade_unique IF NOT EXISTS FOR (t:Trade) REQUIRE t.id IS UNIQUE", "constraint:trade_unique"),
    ]

    with graph._driver.session(database=graph.database) as session:
        # Create indexes and constraints
        for query, name in schema_queries:
            try:
                session.run(query)
                if "INDEX" in query:
                    results["indexes"].append(name)
                else:
                    results["constraints"].append(name)
                print(f"  ✓ Created {name}")
            except Exception as e:
                if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                    print(f"  - {name} (already exists)")
                else:
                    results["errors"].append(f"{name}: {e}")
                    print(f"  ✗ {name}: {e}")

        # Create placeholder Trade node to establish label
        try:
            session.run("""
                MERGE (t:Trade {id: '__schema_placeholder__'})
                ON CREATE SET t.created = datetime(), t.placeholder = true
                RETURN t
            """)
            results["nodes"].append("Trade:__schema_placeholder__")
            print("  ✓ Created Trade label placeholder")
        except Exception as e:
            results["errors"].append(f"Trade placeholder: {e}")
            print(f"  ✗ Trade placeholder: {e}")

        if seed:
            # Seed sample WORKS_FOR relationships with required properties
            seed_data = [
                ("earnings-momentum", "NVDA", 0.75, 8),
                ("earnings-momentum", "AMD", 0.65, 5),
                ("breakout", "NVDA", 0.60, 10),
                ("breakout", "AAPL", 0.55, 12),
                ("mean-reversion", "INTC", 0.50, 6),
            ]

            for strategy, ticker, win_rate, sample_size in seed_data:
                try:
                    session.run("""
                        MERGE (s:Strategy {name: $strategy})
                        MERGE (t:Ticker {symbol: $ticker})
                        MERGE (s)-[r:WORKS_FOR]->(t)
                        SET r.win_rate = $win_rate,
                            r.sample_size = $sample_size,
                            r.updated = datetime()
                        RETURN s, r, t
                    """, {
                        "strategy": strategy,
                        "ticker": ticker,
                        "win_rate": win_rate,
                        "sample_size": sample_size
                    })
                    results["relationships"].append(f"{strategy}-WORKS_FOR->{ticker}")
                    print(f"  ✓ Seeded {strategy} -> {ticker} (win_rate={win_rate}, n={sample_size})")
                except Exception as e:
                    results["errors"].append(f"Seed {strategy}->{ticker}: {e}")
                    print(f"  ✗ Seed {strategy}->{ticker}: {e}")

    return results


def verify_schema(graph: TradingGraph) -> dict:
    """Verify schema elements exist."""
    results = {
        "labels": [],
        "indexes": [],
        "relationships_with_props": 0
    }

    with graph._driver.session(database=graph.database) as session:
        # Check labels
        result = session.run("CALL db.labels() YIELD label RETURN label")
        results["labels"] = [r["label"] for r in result]

        # Check indexes
        result = session.run("SHOW INDEXES YIELD name RETURN name")
        results["indexes"] = [r["name"] for r in result]

        # Check WORKS_FOR relationships with properties
        result = session.run("""
            MATCH ()-[r:WORKS_FOR]->()
            WHERE r.win_rate IS NOT NULL AND r.sample_size IS NOT NULL
            RETURN count(r) AS cnt
        """)
        record = result.single()
        results["relationships_with_props"] = record["cnt"] if record else 0

    return results


def main():
    parser = argparse.ArgumentParser(description="Initialize graph schema")
    parser.add_argument("--seed", action="store_true", help="Include sample seed data")
    parser.add_argument("--verify", action="store_true", help="Only verify schema, don't create")
    args = parser.parse_args()

    print("=== Graph Schema Initialization ===\n")

    graph = TradingGraph()
    graph.connect()

    if not graph.health_check():
        print("ERROR: Cannot connect to Neo4j")
        sys.exit(1)

    print(f"Connected to Neo4j: {graph.uri}\n")

    if args.verify:
        print("Verifying schema...\n")
        results = verify_schema(graph)
        print(f"Labels: {results['labels']}")
        print(f"Indexes: {results['indexes']}")
        print(f"WORKS_FOR with properties: {results['relationships_with_props']}")

        # Check for required elements
        missing = []
        if "Trade" not in results["labels"]:
            missing.append("Trade label")
        if results["relationships_with_props"] == 0:
            missing.append("WORKS_FOR relationships with win_rate/sample_size")

        if missing:
            print(f"\nMissing: {', '.join(missing)}")
            print("Run without --verify to create missing elements")
            sys.exit(1)
        else:
            print("\n✓ Schema complete")
    else:
        print("Creating schema elements...\n")
        results = init_schema(graph, seed=args.seed)

        print(f"\n=== Summary ===")
        print(f"Constraints: {len(results['constraints'])}")
        print(f"Indexes: {len(results['indexes'])}")
        print(f"Nodes: {len(results['nodes'])}")
        print(f"Relationships: {len(results['relationships'])}")
        if results['errors']:
            print(f"Errors: {len(results['errors'])}")
            for err in results['errors']:
                print(f"  - {err}")

        print("\nVerifying...\n")
        verify = verify_schema(graph)
        print(f"Labels: {verify['labels']}")
        print(f"WORKS_FOR with properties: {verify['relationships_with_props']}")

        if "Trade" in verify["labels"] and (not args.seed or verify["relationships_with_props"] > 0):
            print("\n✓ Schema initialization complete")
        else:
            print("\n⚠ Some elements may be missing")

    graph.close()


if __name__ == "__main__":
    main()
