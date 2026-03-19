# Tradegent UI Handoff - 2026-03-19

## Scope

UI stack in `tradegent_ui/`:
- FastAPI backend (`tradegent_ui/server`) on `8081`
- Next.js frontend (`tradegent_ui/frontend`) on `3001`
- Auth migrations in `tradegent_ui/db/migrations`

## Current State

- Branch: `main`
- Commit: `991a787` (shared monorepo commit)
- Git status: clean and synced with `origin/main`

## Startup (Recommended)

From repository root:

```bash
cd /opt/data/tradegent_swarm
./scripts/start_tradegent_ui.sh
```

This script is preferred to avoid partial startup (frontend up, backend down).

## Manual Startup

Backend:

```bash
cd /opt/data/tradegent_swarm/tradegent_ui
pip install -e .
uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload
```

Frontend:

```bash
cd /opt/data/tradegent_swarm/tradegent_ui/frontend
npm install
npm run dev
```

## Required Configuration

Server environment file:
- `tradegent_ui/server/.env`

Required keys:
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `JWT_SECRET`
- `PG_PASS`
- `LLM_API_KEY` (provider key)

Authentication is always enabled by design.

## Smoke Test Checklist

1. Backend health endpoint responds on `:8081`.
2. Frontend loads on `:3001`.
3. Login works with admin credentials from `.env`.
4. Chat request returns response and persists session/message records.
5. One operational chat command succeeds (example: `automation status`).

## Known Operational Notes

- If frontend reconnect loops appear, backend is usually down or not healthy.
- Keep REST for command-style interactions; WebSocket for streaming/live events.
- Chat logging is backend-authoritative; persistence failure should log without breaking response delivery.

## Useful Paths

- UI backend code: `/opt/data/tradegent_swarm/tradegent_ui/server`
- UI frontend code: `/opt/data/tradegent_swarm/tradegent_ui/frontend`
- UI logs: `/opt/data/tradegent_swarm/tradegent_ui/logs`
