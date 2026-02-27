#!/bin/bash
# Trading Knowledge Base Backup Script
# Backs up Neo4j, PostgreSQL, and knowledge files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_ROOT="${PROJECT_ROOT}/backups"
DATE=$(date +%Y%m%d_%H%M%S)

echo "=== Trading Knowledge Base Backup ==="
echo "Started: $(date)"
echo "Backup root: $BACKUP_ROOT"

# Create directories
mkdir -p "$BACKUP_ROOT"/{neo4j,postgres,knowledge}

# Neo4j Backup
echo ""
echo "--- Neo4j Backup ---"
if docker ps --format '{{.Names}}' | grep -q tradegent-neo4j-1; then
    # Try dump approach first
    if docker exec tradegent-neo4j-1 neo4j-admin database dump neo4j --to-path=/data/backup --overwrite-destination 2>/dev/null; then
        docker cp tradegent-neo4j-1:/data/backup/neo4j.dump "$BACKUP_ROOT/neo4j/neo4j_$DATE.dump"
        echo "Neo4j dump: $BACKUP_ROOT/neo4j/neo4j_$DATE.dump"
    else
        # Fallback to Cypher export
        echo "Using Cypher export (dump unavailable in community edition)"
        docker exec tradegent-neo4j-1 cypher-shell -u neo4j -p "${NEO4J_PASS:-neo4j}" \
            "CALL apoc.export.cypher.all('/data/backup/export.cypher', {format: 'plain'})" 2>/dev/null || true
        if docker cp tradegent-neo4j-1:/data/backup/export.cypher "$BACKUP_ROOT/neo4j/export_$DATE.cypher" 2>/dev/null; then
            echo "Neo4j export: $BACKUP_ROOT/neo4j/export_$DATE.cypher"
        else
            echo "Neo4j backup: Skipped (export unavailable)"
        fi
    fi
else
    echo "Neo4j: Not running, skipped"
fi

# PostgreSQL Backup
echo ""
echo "--- PostgreSQL Backup ---"
if docker ps --format '{{.Names}}' | grep -q tradegent-postgres-1; then
    docker exec tradegent-postgres-1 pg_dump -U tradegent -Fc tradegent \
        > "$BACKUP_ROOT/postgres/tradegent_$DATE.dump"
    echo "PostgreSQL dump: $BACKUP_ROOT/postgres/tradegent_$DATE.dump"

    # Also create plain SQL for readability
    docker exec tradegent-postgres-1 pg_dump -U tradegent -d tradegent \
        > "$BACKUP_ROOT/postgres/tradegent_$DATE.sql"
    echo "PostgreSQL SQL: $BACKUP_ROOT/postgres/tradegent_$DATE.sql"
else
    echo "PostgreSQL: Not running, skipped"
fi

# Knowledge Files Backup
echo ""
echo "--- Knowledge Files Backup ---"
KNOWLEDGE_DIR="${PROJECT_ROOT}/tradegent_knowledge/knowledge"
if [ -d "$KNOWLEDGE_DIR" ]; then
    tar czf "$BACKUP_ROOT/knowledge/knowledge_$DATE.tar.gz" \
        -C "$PROJECT_ROOT" tradegent_knowledge/knowledge/
    echo "Knowledge archive: $BACKUP_ROOT/knowledge/knowledge_$DATE.tar.gz"
else
    echo "Knowledge directory not found: $KNOWLEDGE_DIR"
fi

# Cleanup old backups (keep 7 days)
echo ""
echo "--- Cleanup Old Backups ---"
find "$BACKUP_ROOT" -type f -mtime +7 -delete -print 2>/dev/null || true

# Summary
echo ""
echo "=== Backup Complete ==="
echo "Finished: $(date)"

# List backup sizes
echo ""
echo "Backup sizes:"
du -sh "$BACKUP_ROOT"/* 2>/dev/null || true
