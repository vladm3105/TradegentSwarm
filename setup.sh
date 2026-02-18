#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Nexus Light Trading Platform v2.1 - Setup
#
# Architecture:
#   Docker  → Infrastructure (PG, Neo4j, IB Gateway, LightRAG)
#   Host    → Orchestrator + Claude Code CLI
# ═══════════════════════════════════════════════════════════════
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  Nexus Light v2.1 - Setup                ║"
echo "╚══════════════════════════════════════════╝"

# Step 1: Prerequisites
echo -e "\n[1/7] Prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "❌ Docker Compose not found"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 not found"; exit 1; }
command -v claude >/dev/null 2>&1 || { echo "❌ Claude Code CLI not found — install: npm install -g @anthropic-ai/claude-code"; exit 1; }
echo "✅ All prerequisites found"

# Step 2: Environment
echo -e "\n[2/7] Environment..."
if [ ! -f .env ]; then
    cp .env.template .env
    echo "⚠️  Created .env — edit with your credentials, then re-run setup.sh"
    exit 0
fi
echo "✅ .env exists"

# Step 3: Directories
echo -e "\n[3/7] Directories..."
mkdir -p analyses trades logs db
echo "✅ Created"

# Step 4: Python deps (on host)
echo -e "\n[4/7] Python dependencies (host)..."
pip install --quiet psycopg[binary] requests 2>/dev/null \
    || pip install --quiet --break-system-packages psycopg[binary] requests
echo "✅ psycopg3, requests installed"

# Step 5: Start Docker infrastructure
echo -e "\n[5/7] Starting Docker infrastructure..."
docker compose up -d
echo "Waiting for databases..."
sleep 10

# Verify postgres
for i in $(seq 1 30); do
    if docker exec nexus-postgres pg_isready -U lightrag >/dev/null 2>&1; then
        echo "✅ PostgreSQL ready"; break
    fi
    [ $i -eq 30 ] && { echo "❌ PostgreSQL timeout"; exit 1; }
    sleep 2
done

# Verify IB Gateway
if nc -z localhost 4002 2>/dev/null; then
    echo "✅ IB Gateway paper port open"
else
    echo "⚠️  IB Gateway not connected — check VNC at localhost:5900"
fi

# Step 6: Initialize Nexus schema
echo -e "\n[6/7] Initializing database schema..."
export $(grep -v '^#' .env | xargs)
export PG_HOST=localhost

python3 -c "
from db_layer import NexusDB
db = NexusDB()
db.connect()
db.init_schema()
stocks = db.get_enabled_stocks()
scanners = db.get_enabled_scanners()
schedules = db.get_enabled_schedules()
print(f'✅ Schema ready: {len(stocks)} stocks | {len(scanners)} scanners | {len(schedules)} schedules')
db.close()
"

# Step 7: Initialize schedule times
echo -e "\n[7/7] Initializing schedule times..."
python3 service.py init

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Setup Complete!                                         ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║                                                          ║"
echo "║  Architecture:                                           ║"
echo "║    Docker → PG, Neo4j, IB Gateway, LightRAG             ║"
echo "║    Host   → Orchestrator + Claude Code CLI               ║"
echo "║                                                          ║"
echo "║  Start the service (on host):                            ║"
echo "║    python3 service.py                                    ║"
echo "║                                                          ║"
echo "║  Or use systemd (see nexus-light.service):               ║"
echo "║    sudo cp nexus-light.service /etc/systemd/system/      ║"
echo "║    sudo systemctl enable --now nexus-light               ║"
echo "║                                                          ║"
echo "║  Or just use screen/tmux:                                ║"
echo "║    screen -S nexus python3 service.py                    ║"
echo "║                                                          ║"
echo "║  One-off commands (separate terminal):                   ║"
echo "║    python3 orchestrator.py status                        ║"
echo "║    python3 orchestrator.py analyze NFLX --type earnings  ║"
echo "║    python3 orchestrator.py settings list                 ║"
echo "║    python3 orchestrator.py settings set dry_run_mode false║"
echo "║    python3 service.py health                             ║"
echo "║                                                          ║"
echo "║  Docker services:                                        ║"
echo "║    docker compose ps                                     ║"
echo "║    docker compose logs -f ib-gateway                     ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
