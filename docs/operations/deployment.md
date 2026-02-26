# Deployment Guide

Deploy TradegentSwarm for production use with Docker and systemd.

---

## Architecture

```
┌─ HOST MACHINE ─────────────────────────────────────────────────┐
│                                                                │
│  ┌─ systemd ──────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  tradegent.service                                      │   │
│  │    └─ python service.py                                 │   │
│  │                                                         │   │
│  │  tradegent-ib-mcp.service                               │   │
│  │    └─ python -m ibmcp --transport streamable-http      │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─ Docker Compose ────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  postgres (5433)   ib-gateway (4002)   neo4j (7688)    │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Component | Version | Purpose |
|-----------|---------|---------|
| Docker | 20+ | Container runtime |
| Docker Compose | 2.0+ | Service orchestration |
| Python | 3.11+ | Platform runtime |
| Node.js | 20+ | Claude Code dependency |
| Claude Code CLI | Latest | AI engine |

---

## Quick Start

### 1. Clone and Configure

```bash
git clone git@github.com:vladm3105/TradegentSwarm.git
cd TradegentSwarm/tradegent

cp .env.template .env
# Edit .env with credentials
```

### 2. Start Infrastructure

```bash
docker compose up -d
```

### 3. Initialize Database

```bash
python orchestrator.py db-init
```

### 4. Verify

```bash
python orchestrator.py status
```

---

## Docker Compose

### Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| postgres | pgvector/pgvector:pg16 | 5433 | RAG embeddings |
| ib-gateway | gnzsnz/ib-gateway | 4002 | Paper trading |
| neo4j | neo4j:5-community | 7688 | Knowledge graph |

### docker-compose.yml

```yaml
version: "3.8"

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: nexus-postgres
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: ${PG_USER}
      POSTGRES_PASSWORD: ${PG_PASS}
      POSTGRES_DB: ${PG_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  ib-gateway:
    image: ghcr.io/gnzsnz/ib-gateway:latest
    container_name: nexus-ib-gateway
    ports:
      - "4002:4002"
      - "5900:5900"
    environment:
      TWS_USERID: ${IB_USER}
      TWS_PASSWORD: ${IB_PASS}
      TRADING_MODE: paper
      VNC_SERVER_PASSWORD: ${VNC_PASS}
    volumes:
      - ib_data:/home/ibgateway/Jts

  neo4j:
    image: neo4j:5-community
    container_name: nexus-neo4j
    ports:
      - "7474:7474"
      - "7688:7687"
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASS}
    volumes:
      - neo4j_data:/data

volumes:
  postgres_data:
  ib_data:
  neo4j_data:
```

### Commands

```bash
# Start all
docker compose up -d

# View logs
docker compose logs -f

# Stop all
docker compose down

# Restart single service
docker compose restart postgres

# View status
docker compose ps
```

---

## Systemd Services

### Main Service

Create `/etc/systemd/system/tradegent.service`:

```ini
[Unit]
Description=TradegentSwarm Trading Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=tradegent
WorkingDirectory=/opt/data/tradegent_swarm/tradegent
Environment=PATH=/home/tradegent/.nvm/versions/node/v20.11.0/bin:/usr/bin
EnvironmentFile=/opt/data/tradegent_swarm/tradegent/.env
ExecStart=/usr/bin/python3 service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### IB MCP Service

Create `/etc/systemd/system/tradegent-ib-mcp.service`:

```ini
[Unit]
Description=IB MCP Server for TradegentSwarm
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=tradegent
WorkingDirectory=/opt/data/trading/mcp_ib
Environment=PYTHONPATH=/opt/data/trading/mcp_ib/src
Environment=IB_GATEWAY_HOST=localhost
Environment=IB_GATEWAY_PORT=4002
Environment=IB_CLIENT_ID=2
Environment=IB_READONLY=false
Environment=IB_OUTSIDE_RTH=true
ExecStart=/usr/bin/python3 -m ibmcp --transport streamable-http --host 0.0.0.0 --port 8100
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable tradegent tradegent-ib-mcp
sudo systemctl start tradegent tradegent-ib-mcp
```

### Service Commands

```bash
# Status
sudo systemctl status tradegent

# Logs
sudo journalctl -u tradegent -f

# Restart
sudo systemctl restart tradegent

# Stop
sudo systemctl stop tradegent
```

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `PG_USER` | PostgreSQL user |
| `PG_PASS` | PostgreSQL password |
| `PG_DB` | Database name |
| `PG_HOST` | PostgreSQL host |
| `PG_PORT` | PostgreSQL port |
| `NEO4J_URI` | Neo4j bolt URI |
| `NEO4J_USER` | Neo4j user |
| `NEO4J_PASS` | Neo4j password |
| `IB_USER` | IB username |
| `IB_PASS` | IB password |
| `OPENAI_API_KEY` | OpenAI API key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_PROVIDER` | openai | Embedding provider |
| `EXTRACT_PROVIDER` | openai | Extraction provider |
| `IB_READONLY` | false | Set `true` to block orders |
| `IB_OUTSIDE_RTH` | true | Allow orders outside regular trading hours |

---

## IB Gateway Setup

### First-Time Login

1. Start IB Gateway:
   ```bash
   docker compose up -d ib-gateway
   ```

2. Connect via VNC:
   ```bash
   vncviewer localhost:5900
   # Password: value of VNC_PASS
   ```

3. Complete login and 2FA

4. Gateway stores credentials for auto-reconnect

### Verify Connection

```bash
# Check container status
docker compose ps ib-gateway

# Test API connection
python -c "
from ib_insync import IB
ib = IB()
ib.connect('localhost', 4002, clientId=99)
print('Connected:', ib.isConnected())
ib.disconnect()
"
```

---

## Health Checks

### Automated Checks

```bash
# All services
python orchestrator.py status

# Database
psql -h localhost -p 5433 -U lightrag -c "SELECT 1"

# Neo4j
cypher-shell -a bolt://localhost:7688 -u neo4j -p $NEO4J_PASS "RETURN 1"

# IB MCP
curl http://localhost:8100/health
```

### Docker Health

```bash
docker compose ps
# All services should show "Up (healthy)"
```

---

## Backup Strategy

### Database Backup

```bash
# PostgreSQL
pg_dump -h localhost -p 5433 -U lightrag lightrag > backup.sql

# Neo4j
docker exec nexus-neo4j neo4j-admin database dump --to-path=/dumps neo4j
```

### Knowledge Base Backup

```bash
tar -czf knowledge_$(date +%Y%m%d).tar.gz \
  tradegent_knowledge/knowledge/
```

### Scheduled Backup

```bash
# crontab -e
0 2 * * * /opt/data/tradegent_swarm/scripts/backup.sh
```

---

## Security

### Network

- All services bind to localhost by default
- IB Gateway uses paper trading port (4002)
- Neo4j browser disabled in production

### Credentials

- Store secrets in `.env` (not committed)
- Use environment variables, not config files
- Rotate API keys regularly

### Access Control

- Run services as non-root user
- Limit file permissions on `.env`
- Use systemd sandboxing

---

## Troubleshooting

### Service won't start

```bash
sudo journalctl -u tradegent -n 50
```

### Docker containers unhealthy

```bash
docker compose logs postgres
docker compose restart postgres
```

### IB Gateway disconnects

1. Check VNC for 2FA prompt
2. Verify credentials in `.env`
3. Check IB maintenance schedule

---

## Related Documentation

- [Monitoring](monitoring.md)
- [Troubleshooting](troubleshooting.md)
- [Runbooks](runbooks.md)
