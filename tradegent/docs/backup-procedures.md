# Backup Procedures

## Overview

Backup strategy for Trading Knowledge Base: Neo4j (graph), PostgreSQL (vectors/metadata), and knowledge YAML files.

## Neo4j Backup

### Online Backup

```bash
# Create backup directory
mkdir -p /opt/data/tradegent_swarm/backups/neo4j

# Backup using docker exec
docker exec nexus-neo4j neo4j-admin database dump neo4j \
    --to-path=/data/backup \
    --overwrite-destination

# Copy backup to host
docker cp nexus-neo4j:/data/backup/neo4j.dump \
    /opt/data/tradegent_swarm/backups/neo4j/neo4j_$(date +%Y%m%d_%H%M%S).dump
```

### Export Cypher (Human-Readable)

```bash
# Export all nodes and relationships as Cypher statements
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" \
    "CALL apoc.export.cypher.all('/data/backup/export.cypher', {format: 'plain'})"

docker cp nexus-neo4j:/data/backup/export.cypher \
    /opt/data/tradegent_swarm/backups/neo4j/export_$(date +%Y%m%d).cypher
```

### Volume Backup

```bash
# Stop Neo4j for consistent backup
docker compose stop neo4j

# Backup volume
docker run --rm \
    -v trading_light_pilot_neo4j_data:/data \
    -v /opt/data/tradegent_swarm/backups:/backup \
    alpine tar cvzf /backup/neo4j/neo4j_volume_$(date +%Y%m%d).tar.gz /data

# Restart
docker compose start neo4j
```

## PostgreSQL Backup

### pg_dump (Recommended)

```bash
# Create backup directory
mkdir -p /opt/data/tradegent_swarm/backups/postgres

# Backup entire database
docker exec nexus-postgres pg_dump -U lightrag -Fc lightrag \
    > /opt/data/tradegent_swarm/backups/postgres/lightrag_$(date +%Y%m%d_%H%M%S).dump

# Backup specific schemas
docker exec nexus-postgres pg_dump -U lightrag -Fc -n rag lightrag \
    > /opt/data/tradegent_swarm/backups/postgres/rag_$(date +%Y%m%d).dump

docker exec nexus-postgres pg_dump -U lightrag -Fc -n graph lightrag \
    > /opt/data/tradegent_swarm/backups/postgres/graph_$(date +%Y%m%d).dump
```

### Plain SQL Backup

```bash
# Human-readable SQL backup
docker exec nexus-postgres pg_dump -U lightrag lightrag \
    > /opt/data/tradegent_swarm/backups/postgres/lightrag_$(date +%Y%m%d).sql
```

### Volume Backup

```bash
# Stop PostgreSQL for consistent backup
docker compose stop postgres

# Backup volume
docker run --rm \
    -v trading_light_pilot_pg_data:/data \
    -v /opt/data/tradegent_swarm/backups:/backup \
    alpine tar cvzf /backup/postgres/pg_volume_$(date +%Y%m%d).tar.gz /data

# Restart
docker compose start postgres
```

## Knowledge Files Backup

### Git-Based (Primary)

```bash
cd /opt/data/tradegent_swarm

# Ensure all changes committed
git status
git add tradegent_knowledge/knowledge/
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push

# Create tagged backup point
git tag -a backup-$(date +%Y%m%d) -m "Knowledge backup $(date +%Y-%m-%d)"
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push --tags
```

### Archive Backup

```bash
mkdir -p /opt/data/tradegent_swarm/backups/knowledge

tar cvzf /opt/data/tradegent_swarm/backups/knowledge/knowledge_$(date +%Y%m%d).tar.gz \
    /opt/data/tradegent_swarm/tradegent_knowledge/knowledge/
```

## Automated Backup Script

```bash
#!/bin/bash
# File: tradegent/scripts/backup.sh

set -e

BACKUP_ROOT="/opt/data/tradegent_swarm/backups"
DATE=$(date +%Y%m%d_%H%M%S)

echo "Starting backup: $DATE"

# Create directories
mkdir -p "$BACKUP_ROOT"/{neo4j,postgres,knowledge}

# Neo4j
echo "Backing up Neo4j..."
docker exec nexus-neo4j neo4j-admin database dump neo4j --to-path=/data/backup --overwrite-destination 2>/dev/null || true
docker cp nexus-neo4j:/data/backup/neo4j.dump "$BACKUP_ROOT/neo4j/neo4j_$DATE.dump" 2>/dev/null || echo "Neo4j backup skipped"

# PostgreSQL
echo "Backing up PostgreSQL..."
docker exec nexus-postgres pg_dump -U lightrag -Fc lightrag > "$BACKUP_ROOT/postgres/lightrag_$DATE.dump"

# Knowledge files
echo "Backing up knowledge files..."
tar czf "$BACKUP_ROOT/knowledge/knowledge_$DATE.tar.gz" -C /opt/data/tradegent_swarm tradegent_knowledge/knowledge/

# Cleanup old backups (keep 7 days)
find "$BACKUP_ROOT" -type f -mtime +7 -delete

echo "Backup complete: $DATE"
```

### Cron Schedule

```bash
# Add to crontab (crontab -e)
# Daily backup at 2 AM
0 2 * * * /opt/data/tradegent_swarm/trader/scripts/backup.sh >> /var/log/trading_backup.log 2>&1
```

## Restore Procedures

### Neo4j Restore

```bash
# Stop Neo4j
docker compose stop neo4j

# Clear existing data
docker run --rm -v trading_light_pilot_neo4j_data:/data alpine rm -rf /data/*

# Restore from dump
docker run --rm \
    -v trading_light_pilot_neo4j_data:/data \
    -v /opt/data/tradegent_swarm/backups/neo4j:/backup \
    neo4j:5-community neo4j-admin database load neo4j --from-path=/backup/neo4j_YYYYMMDD.dump

# Start Neo4j
docker compose start neo4j
```

### PostgreSQL Restore

```bash
# Drop and recreate database
docker exec nexus-postgres psql -U lightrag -c "DROP DATABASE IF EXISTS lightrag_restore;"
docker exec nexus-postgres psql -U lightrag -c "CREATE DATABASE lightrag_restore;"

# Restore from dump
docker exec -i nexus-postgres pg_restore -U lightrag -d lightrag_restore \
    < /opt/data/tradegent_swarm/backups/postgres/lightrag_YYYYMMDD.dump

# Verify and swap
docker exec nexus-postgres psql -U lightrag -d lightrag_restore \
    -c "SELECT COUNT(*) FROM rag.chunks;"
```

### Knowledge Files Restore

```bash
# From git
cd /opt/data/tradegent_swarm
git checkout backup-YYYYMMDD -- tradegent_knowledge/knowledge/

# From archive
tar xvzf /opt/data/tradegent_swarm/backups/knowledge/knowledge_YYYYMMDD.tar.gz \
    -C /opt/data/tradegent_swarm
```

## Backup Verification

```bash
#!/bin/bash
# File: tradegent/scripts/verify_backup.sh

BACKUP_ROOT="/opt/data/tradegent_swarm/backups"

echo "Verifying latest backups..."

# Check Neo4j dump
LATEST_NEO4J=$(ls -t "$BACKUP_ROOT/neo4j/"*.dump 2>/dev/null | head -1)
if [ -n "$LATEST_NEO4J" ]; then
    SIZE=$(stat -c%s "$LATEST_NEO4J")
    echo "Neo4j: $LATEST_NEO4J (${SIZE} bytes)"
else
    echo "Neo4j: NO BACKUP FOUND"
fi

# Check PostgreSQL dump
LATEST_PG=$(ls -t "$BACKUP_ROOT/postgres/"*.dump 2>/dev/null | head -1)
if [ -n "$LATEST_PG" ]; then
    SIZE=$(stat -c%s "$LATEST_PG")
    echo "PostgreSQL: $LATEST_PG (${SIZE} bytes)"
else
    echo "PostgreSQL: NO BACKUP FOUND"
fi

# Check knowledge archive
LATEST_KNOWLEDGE=$(ls -t "$BACKUP_ROOT/knowledge/"*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST_KNOWLEDGE" ]; then
    SIZE=$(stat -c%s "$LATEST_KNOWLEDGE")
    COUNT=$(tar tzf "$LATEST_KNOWLEDGE" | wc -l)
    echo "Knowledge: $LATEST_KNOWLEDGE (${SIZE} bytes, ${COUNT} files)"
else
    echo "Knowledge: NO BACKUP FOUND"
fi
```

## Retention Policy

| Backup Type | Retention | Storage Location |
|-------------|-----------|------------------|
| Daily dumps | 7 days | Local + Git LFS |
| Weekly snapshots | 4 weeks | Local |
| Monthly archives | 12 months | Off-site/cloud |
| Git tags | Indefinite | GitHub |
