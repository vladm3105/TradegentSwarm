#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Trading Knowledge Base Backup Script
# Backs up Neo4j and PostgreSQL (RAG) data
# ═══════════════════════════════════════════════════════════════

set -e

BACKUP_DIR="${HOME}/backups/trading_kb_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "═══════════════════════════════════════════════════════════"
echo "Knowledge Base Backup - $(date)"
echo "Backup directory: $BACKUP_DIR"
echo "═══════════════════════════════════════════════════════════"

# ─── PostgreSQL (RAG) Backup ───────────────────────────────────
echo ""
echo "→ Backing up PostgreSQL (RAG tables)..."

# Backup the nexus schema (RAG tables)
docker exec nexus-postgres pg_dump \
    -U "${PG_USER:-tradegent}" \
    --schema=nexus \
    --no-owner \
    "${PG_DB:-tradegent}" > "$BACKUP_DIR/nexus_pg_rag.sql"

if [ $? -eq 0 ]; then
    echo "  ✅ PostgreSQL backup complete: nexus_pg_rag.sql"
    wc -l "$BACKUP_DIR/nexus_pg_rag.sql" | awk '{print "     Lines: "$1}'
else
    echo "  ❌ PostgreSQL backup failed"
fi

# ─── Neo4j Backup ──────────────────────────────────────────────
# Note: Neo4j Community Edition requires stopping the container
# for a consistent backup. Use cypher export for online backup.

echo ""
echo "→ Backing up Neo4j (graph data via Cypher export)..."

# Export all nodes and relationships as Cypher statements
docker exec nexus-neo4j cypher-shell \
    -u neo4j \
    -p "${NEO4J_PASS}" \
    "CALL apoc.export.cypher.all(null, {format: 'cypher-shell', stream: true}) YIELD cypherStatements RETURN cypherStatements" \
    2>/dev/null > "$BACKUP_DIR/neo4j_export.cypher" || true

if [ -s "$BACKUP_DIR/neo4j_export.cypher" ]; then
    echo "  ✅ Neo4j export complete: neo4j_export.cypher"
    wc -l "$BACKUP_DIR/neo4j_export.cypher" | awk '{print "     Lines: "$1}'
else
    echo "  ⚠️ Neo4j Cypher export empty or failed"
    echo "     Trying file-based backup (requires container restart)..."

    # Alternative: volume backup
    echo "     Copying data volume..."
    docker cp nexus-neo4j:/data "$BACKUP_DIR/neo4j_data" 2>/dev/null || {
        echo "  ❌ Neo4j backup failed"
    }
fi

# ─── Logs Backup ───────────────────────────────────────────────
echo ""
echo "→ Backing up logs..."

if [ -d "logs" ]; then
    cp -r logs "$BACKUP_DIR/logs"
    echo "  ✅ Logs backed up"
else
    echo "  ⚠️ No logs directory found"
fi

# ─── Summary ───────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Backup complete!"
echo "Location: $BACKUP_DIR"
du -sh "$BACKUP_DIR" | awk '{print "Size: "$1}'
echo ""
echo "To restore PostgreSQL:"
echo "  psql -U tradegent -d tradegent < $BACKUP_DIR/nexus_pg_rag.sql"
echo ""
echo "To restore Neo4j (via Cypher):"
echo "  cat $BACKUP_DIR/neo4j_export.cypher | cypher-shell -u neo4j -p <password>"
echo "═══════════════════════════════════════════════════════════"
