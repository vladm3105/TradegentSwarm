#!/bin/bash
# Trading Knowledge Base Health Check Script
# Checks status of all services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRADER_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Trading Knowledge Base Health Check ==="
echo "Timestamp: $(date)"
echo ""

ERRORS=0

# Docker Services
echo "--- Docker Services ---"
cd "$TRADER_DIR"

for service in nexus-postgres nexus-neo4j nexus-ib-gateway; do
    if docker ps --format '{{.Names}}' | grep -q "$service"; then
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "running")
        echo "✅ $service: $HEALTH"
    else
        echo "❌ $service: NOT RUNNING"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# PostgreSQL Connection
echo "--- PostgreSQL ---"
if docker exec nexus-postgres pg_isready -U lightrag > /dev/null 2>&1; then
    echo "✅ Connection: OK"

    # Check schemas
    SCHEMA_COUNT=$(docker exec nexus-postgres psql -U lightrag -d lightrag -t -c \
        "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('rag', 'graph');" 2>/dev/null | tr -d ' ')
    if [ "$SCHEMA_COUNT" = "2" ]; then
        echo "✅ Schemas: rag, graph"
    else
        echo "⚠️  Schemas: Only $SCHEMA_COUNT/2 found"
    fi

    # Check table counts
    DOC_COUNT=$(docker exec nexus-postgres psql -U lightrag -d lightrag -t -c \
        "SELECT COUNT(*) FROM rag.documents;" 2>/dev/null | tr -d ' ' || echo "0")
    CHUNK_COUNT=$(docker exec nexus-postgres psql -U lightrag -d lightrag -t -c \
        "SELECT COUNT(*) FROM rag.chunks;" 2>/dev/null | tr -d ' ' || echo "0")
    echo "   Documents: $DOC_COUNT"
    echo "   Chunks: $CHUNK_COUNT"
else
    echo "❌ Connection: FAILED"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Neo4j Connection
echo "--- Neo4j ---"
if curl -sf http://localhost:7475 > /dev/null 2>&1; then
    echo "✅ HTTP (7475): OK"
else
    echo "❌ HTTP (7475): FAILED"
    ERRORS=$((ERRORS + 1))
fi

if nc -z localhost 7688 2>/dev/null; then
    echo "✅ Bolt (7688): OK"

    # Check node counts (requires auth)
    NODE_COUNT=$(docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS:-neo4j}" \
        "MATCH (n) RETURN COUNT(n) AS count" 2>/dev/null | tail -1 | tr -d ' ' || echo "?")
    REL_COUNT=$(docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS:-neo4j}" \
        "MATCH ()-[r]->() RETURN COUNT(r) AS count" 2>/dev/null | tail -1 | tr -d ' ' || echo "?")
    echo "   Nodes: $NODE_COUNT"
    echo "   Relationships: $REL_COUNT"
else
    echo "❌ Bolt (7688): FAILED"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Ollama (Embedding)
echo "--- Ollama (Embedding) ---"
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Connection: OK"

    # Check for required model
    if curl -s http://localhost:11434/api/tags | grep -q "nomic-embed-text"; then
        echo "✅ Model: nomic-embed-text"
    else
        echo "⚠️  Model: nomic-embed-text not found"
    fi
else
    echo "❌ Connection: FAILED (http://localhost:11434)"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# IB Gateway (optional)
echo "--- IB Gateway ---"
if nc -z localhost 4002 2>/dev/null; then
    echo "✅ Port 4002: OK"
else
    echo "⚠️  Port 4002: Not available (paper trading)"
fi
echo ""

# Summary
echo "=== Health Check Summary ==="
if [ "$ERRORS" -eq 0 ]; then
    echo "✅ All critical services healthy"
    exit 0
else
    echo "❌ $ERRORS critical error(s) found"
    exit 1
fi
