# IB Gateway Docker

IB Gateway runs using `gnzsnz/ib-gateway:stable` image.

## Port Mapping

| Mode | External Port | Container |
|------|---------------|-----------|
| Paper | 4002 | paper-ib-gateway |
| Live | 4001 | live-ib-gateway |

## Starting Gateways

```bash
cd tradegent

# Start paper gateway (default)
docker compose up -d paper-ib-gateway

# Start live gateway (requires --profile)
docker compose --profile live up -d live-ib-gateway

# View logs
docker compose logs -f paper-ib-gateway
```

## Trading Mode Switch

Set `IB_MODE` in `.env`:

```bash
IB_MODE=paper              # or "live"
IB_PAPER_USER=<username>
IB_PAPER_PASS=<password>
IB_PAPER_ACCOUNT=<account>
```

## VNC Access (2FA, troubleshooting)

| Mode | VNC Port | Password |
|------|----------|----------|
| Paper | 5902 | nexus123 |
| Live | 5901 | nexuslive123 |

```bash
vncviewer localhost:5902  # Paper gateway
```

## Preflight Checks

```bash
# Full check (start of session)
cd tradegent && python preflight.py --full

# Quick check (before each analysis)
cd tradegent && python preflight.py
```

**Services Checked (Full):**
- `postgres_container` - Docker container running
- `neo4j_container` - Docker container running
- `ib_gateway` - Container healthy
- `rag` - pgvector connectivity
- `graph` - Neo4j connectivity
- `ib_mcp` - MCP server on port 8100
- `ib_gateway_port` - API port (4002 paper)
- `market` - Market hours status (ET)

**Status Meanings:**
- `healthy` - Fully operational
- `degraded` - Available with limitations
- `unhealthy` - Unavailable
- `READY` - Can proceed with analysis
- `NOT READY` - Cannot proceed

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `TWS_USERID` | IB account username |
| `TWS_PASSWORD` | IB account password |
| `TRADING_MODE` | `paper`, `live`, or `both` |
| `READ_ONLY_API` | Block order placement |
| `TWOFA_TIMEOUT_ACTION` | `exit` or `restart` on 2FA timeout |
