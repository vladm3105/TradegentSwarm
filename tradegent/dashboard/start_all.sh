#!/bin/bash
# Start all Tradegent dashboard services
# Usage: ./dashboard/start_all.sh

cd "$(dirname "$0")/.."

echo "╔══════════════════════════════════════════╗"
echo "║  Starting Tradegent Dashboard Stack      ║"
echo "╚══════════════════════════════════════════╝"

# Start Docker services
echo "Starting Docker services..."
docker compose up -d postgres neo4j metabase

# Wait for services
sleep 5

# Start Portal
echo "Starting Portal..."
pkill -f "serve_portal.py" 2>/dev/null
LD_LIBRARY_PATH= nohup python dashboard/serve_portal.py > /tmp/portal.log 2>&1 &

# Start Streamlit
echo "Starting Streamlit..."
pkill -f "streamlit run" 2>/dev/null
sleep 1
LD_LIBRARY_PATH= nohup streamlit run dashboard/app.py --server.port 8501 > /tmp/streamlit.log 2>&1 &

sleep 3

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  All Services Started                    ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Portal:     http://localhost:8000       ║"
echo "║  Streamlit:  http://localhost:8501       ║"
echo "║  Metabase:   http://localhost:3001       ║"
echo "║  Neo4j:      http://localhost:7475       ║"
echo "╚══════════════════════════════════════════╝"
