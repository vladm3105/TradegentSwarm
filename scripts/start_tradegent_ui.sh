#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$ROOT_DIR/tradegent_ui"
FRONTEND_DIR="$UI_DIR/frontend"
LOG_DIR="$UI_DIR/logs"
BACKEND_HEALTH_URL="http://127.0.0.1:8081/health"
FRONTEND_URL="http://127.0.0.1:3001/login"
VENV_PY="$ROOT_DIR/.venv/bin/python"

mkdir -p "$LOG_DIR"

is_port_open() {
  local port="$1"
  ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
}

wait_for_url() {
  local url="$1"
  local timeout_seconds="$2"
  local elapsed=0

  while [[ "$elapsed" -lt "$timeout_seconds" ]]; do
    if curl -fsS -m 2 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  return 1
}

start_backend() {
  echo "[start-ui] Ensuring backend is running on :8081"

  if curl -fsS -m 2 "$BACKEND_HEALTH_URL" >/dev/null 2>&1; then
    echo "[start-ui] Backend already healthy"
    return 0
  fi

  if [[ ! -x "$VENV_PY" ]]; then
    echo "[start-ui] ERROR: Python venv not found at $VENV_PY"
    echo "[start-ui] Create the venv first or update the script path"
    return 1
  fi

  (
    cd "$UI_DIR"
    nohup "$VENV_PY" -m uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload \
      >> "$LOG_DIR/backend-start.log" 2>&1 &
  )

  if wait_for_url "$BACKEND_HEALTH_URL" 30; then
    echo "[start-ui] Backend is healthy"
    return 0
  fi

  echo "[start-ui] ERROR: Backend failed to become healthy within 30s"
  echo "[start-ui] Check logs: $LOG_DIR/backend-start.log"
  return 1
}

start_frontend() {
  echo "[start-ui] Ensuring frontend is running on :3001"

  if is_port_open 3001; then
    echo "[start-ui] Frontend port 3001 already listening"
    return 0
  fi

  (
    cd "$FRONTEND_DIR"
    nohup npm run dev >> "$LOG_DIR/frontend-start.log" 2>&1 &
  )

  if wait_for_url "$FRONTEND_URL" 45; then
    echo "[start-ui] Frontend is responding"
    return 0
  fi

  echo "[start-ui] ERROR: Frontend failed to respond within 45s"
  echo "[start-ui] Check logs: $LOG_DIR/frontend-start.log"
  return 1
}

print_status() {
  echo "[start-ui] Status summary"
  if curl -fsS -m 2 "$BACKEND_HEALTH_URL" >/dev/null 2>&1; then
    echo "  backend: healthy (8081)"
  else
    echo "  backend: down (8081)"
  fi

  if is_port_open 3001; then
    echo "  frontend: listening (3001)"
  else
    echo "  frontend: down (3001)"
  fi
}

main() {
  start_backend
  start_frontend
  print_status
}

main "$@"
