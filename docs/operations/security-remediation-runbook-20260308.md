# Security Remediation Runbook (2026-03-08)

## Purpose
Execute post-hardening operational controls for credential rotation, token/session invalidation, API key revocation, and log hygiene.

## Scope
- `tradegent_ui` authentication and websocket hardening follow-up
- Local/runtime secret replacement
- Live token/session invalidation procedures
- Historical log exposure reduction

## Preconditions
- Maintenance window approved
- Admin shell access to host
- Access to PostgreSQL (`nexus` schema)
- Access to process manager (Docker Compose and/or systemd)

## Environment Matrix
| Deployment mode | Config location | Restart command |
|---|---|---|
| Local development | `tradegent_ui/.env`, `tradegent_ui/server/.env` | restart local UI process |
| Docker Compose | `tradegent/.env` and compose-managed env | `cd tradegent && docker compose up -d --force-recreate` |
| systemd services | service `EnvironmentFile` values | `sudo systemctl daemon-reload && sudo systemctl restart <service>` |

## Phase 1: Generate Replacement Secrets
Generate replacement values and store in a secure vault.

```bash
# 1) JWT secret (>= 32 bytes)
openssl rand -base64 48

# 2) Admin/demo passwords
openssl rand -base64 24

# 3) Generic API-style random value
openssl rand -hex 32
```

## Phase 2: Apply New Secrets
Update the active environment files or secret store entries with rotated values.

### Local files (if used)
```bash
# Example: edit values without printing secrets
cd /opt/data/tradegent_swarm
chmod 600 tradegent_ui/.env tradegent_ui/server/.env

# Confirm required security flags
rg -n '^(DEBUG|APP_ENV|ALLOW_DEMO_TOKENS)=' tradegent_ui/.env tradegent_ui/server/.env
# Expected:
# DEBUG=false
# ALLOW_DEMO_TOKENS=false
# APP_ENV=development (or production in deployed envs)
```

### Docker Compose deployment
```bash
cd /opt/data/tradegent_swarm/tradegent
# Update .env / secret source values first, then:
docker compose up -d --force-recreate
```

### systemd deployment
```bash
# Update referenced EnvironmentFile first, then:
sudo systemctl daemon-reload
sudo systemctl restart tradegent
sudo systemctl restart tradegent-ib-mcp
```

## Phase 3: Invalidate Tokens and Revoke API Keys
### Built-in JWT mode
- Rotating `JWT_SECRET` invalidates all previously issued built-in JWT tokens.
- Force re-login for all users after service restart.

### API key revocation
```sql
-- Revoke all active API keys
UPDATE nexus.api_keys
SET is_active = false,
    updated_at = now()
WHERE is_active = true;
```

### Optional: targeted API key revocation
```sql
UPDATE nexus.api_keys
SET is_active = false,
    updated_at = now()
WHERE user_id = <USER_ID>
  AND is_active = true;
```

## Phase 4: Log Hygiene and Exposure Reduction
### Remove prompt previews from current codebase (verification)
```bash
cd /opt/data/tradegent_swarm
rg -n 'content_preview=|\?token=' tradegent_ui/server/main.py tradegent_ui/server/auth.py
# Expected: no security-sensitive preview logging or query-token auth paths
```

### Identify sensitive artifacts in local logs
```bash
cd /opt/data/tradegent_swarm
rg -n 'demo-token-|Authorization: Bearer|sk-proj-|JWT_SECRET=|ADMIN_PASSWORD=' logs tradegent/logs tradegent_ui/logs 2>/dev/null
```

### Purge or rotate logs containing sensitive fields
```bash
# Example local rotation (adjust paths to your retention policy)
find tradegent/logs tradegent_ui/logs -type f -name '*.log' -mtime +7 -delete
```

## Phase 5: Verification Checklist
### Security behavior checks
```bash
cd /opt/data/tradegent_swarm
.venv/bin/python -m pytest tradegent_ui/tests/test_security_hardening.py -q
```

### Regression checks
```bash
cd /opt/data/tradegent_swarm
.venv/bin/python -m pytest \
  tradegent_ui/tests/test_security_hardening.py \
  tradegent_ui/tests/test_adk_bridge_and_execution.py \
  tradegent_ui/tests/test_intent_classifier.py -q
```

### Runtime checks
```bash
# API health
curl -s http://localhost:8081/health | cat

# Verify sync-user requires auth (expect 401/403)
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST http://localhost:8081/api/auth/sync-user \
  -H 'content-type: application/json' \
  -d '{}'
```

### Database checks
```sql
SELECT COUNT(*) AS active_api_keys
FROM nexus.api_keys
WHERE is_active = true;

-- Expected: 0 immediately after global revoke
```

## Phase 6: Post-Change Monitoring (24h)
Monitor for auth failures, websocket auth failures, and unexpected permission errors.

```bash
# Example local log checks
rg -n 'ws\.auth\.failed|ws\.stream\.auth\.failed|Permission denied|Role denied' \
  tradegent_ui/logs/*.log 2>/dev/null
```

## Rollback Procedure
- Restore previous known-good config from secure backup.
- Restart affected services.
- Reissue minimum required credentials only.
- Re-run Phase 5 verification.

## Evidence Capture
Record the following in change ticket:
- Secret rotation completion timestamp
- Service restart timestamps
- API key revocation query result
- Test command outputs
- Post-change monitoring summary
