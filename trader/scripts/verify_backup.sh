#!/bin/bash
# Trading Knowledge Base Backup Verification Script
# Verifies integrity and recency of backups

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_ROOT="${PROJECT_ROOT}/backups"

echo "=== Trading Knowledge Base Backup Verification ==="
echo "Checking: $BACKUP_ROOT"
echo ""

WARNINGS=0

# Check Neo4j backups
echo "--- Neo4j Backups ---"
LATEST_NEO4J=$(ls -t "$BACKUP_ROOT/neo4j/"*.dump 2>/dev/null | head -1)
if [ -z "$LATEST_NEO4J" ]; then
    LATEST_NEO4J=$(ls -t "$BACKUP_ROOT/neo4j/"*.cypher 2>/dev/null | head -1)
fi

if [ -n "$LATEST_NEO4J" ]; then
    SIZE=$(stat -c%s "$LATEST_NEO4J" 2>/dev/null || stat -f%z "$LATEST_NEO4J")
    AGE_DAYS=$(( ($(date +%s) - $(stat -c%Y "$LATEST_NEO4J" 2>/dev/null || stat -f%m "$LATEST_NEO4J")) / 86400 ))
    echo "Latest: $(basename "$LATEST_NEO4J")"
    echo "Size: $(numfmt --to=iec $SIZE 2>/dev/null || echo "$SIZE bytes")"
    echo "Age: $AGE_DAYS days"
    if [ "$AGE_DAYS" -gt 1 ]; then
        echo "⚠️  WARNING: Neo4j backup is older than 1 day"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "❌ NO NEO4J BACKUP FOUND"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Check PostgreSQL backups
echo "--- PostgreSQL Backups ---"
LATEST_PG=$(ls -t "$BACKUP_ROOT/postgres/"*.dump 2>/dev/null | head -1)
if [ -n "$LATEST_PG" ]; then
    SIZE=$(stat -c%s "$LATEST_PG" 2>/dev/null || stat -f%z "$LATEST_PG")
    AGE_DAYS=$(( ($(date +%s) - $(stat -c%Y "$LATEST_PG" 2>/dev/null || stat -f%m "$LATEST_PG")) / 86400 ))
    echo "Latest: $(basename "$LATEST_PG")"
    echo "Size: $(numfmt --to=iec $SIZE 2>/dev/null || echo "$SIZE bytes")"
    echo "Age: $AGE_DAYS days"
    if [ "$AGE_DAYS" -gt 1 ]; then
        echo "⚠️  WARNING: PostgreSQL backup is older than 1 day"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Verify dump integrity
    if command -v pg_restore &> /dev/null; then
        if pg_restore -l "$LATEST_PG" > /dev/null 2>&1; then
            echo "Integrity: OK (pg_restore list succeeded)"
        else
            echo "⚠️  WARNING: pg_restore cannot read dump"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
else
    echo "❌ NO POSTGRESQL BACKUP FOUND"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Check Knowledge backups
echo "--- Knowledge Backups ---"
LATEST_KNOWLEDGE=$(ls -t "$BACKUP_ROOT/knowledge/"*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST_KNOWLEDGE" ]; then
    SIZE=$(stat -c%s "$LATEST_KNOWLEDGE" 2>/dev/null || stat -f%z "$LATEST_KNOWLEDGE")
    AGE_DAYS=$(( ($(date +%s) - $(stat -c%Y "$LATEST_KNOWLEDGE" 2>/dev/null || stat -f%m "$LATEST_KNOWLEDGE")) / 86400 ))
    FILE_COUNT=$(tar tzf "$LATEST_KNOWLEDGE" 2>/dev/null | wc -l)
    echo "Latest: $(basename "$LATEST_KNOWLEDGE")"
    echo "Size: $(numfmt --to=iec $SIZE 2>/dev/null || echo "$SIZE bytes")"
    echo "Files: $FILE_COUNT"
    echo "Age: $AGE_DAYS days"
    if [ "$AGE_DAYS" -gt 1 ]; then
        echo "⚠️  WARNING: Knowledge backup is older than 1 day"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Verify archive integrity
    if tar tzf "$LATEST_KNOWLEDGE" > /dev/null 2>&1; then
        echo "Integrity: OK (tar listing succeeded)"
    else
        echo "⚠️  WARNING: Archive may be corrupted"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "❌ NO KNOWLEDGE BACKUP FOUND"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Summary
echo "=== Verification Summary ==="
if [ "$WARNINGS" -eq 0 ]; then
    echo "✅ All backups verified successfully"
    exit 0
else
    echo "⚠️  $WARNINGS warning(s) found"
    exit 1
fi
