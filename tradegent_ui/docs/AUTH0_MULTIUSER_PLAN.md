# Implementation Plan: Auth0 Multi-User Environment

## Overview

Add Auth0 authentication and multi-user support to the Tradegent UI, enabling user registration, per-user IB accounts, and role-based access control.

## Requirements (Confirmed)

| Requirement | Choice |
|-------------|--------|
| **Auth Methods** | Social + Email (Google, GitHub, email/password via Auth0) |
| **IB Accounts** | Per-user (each user connects their own IB account) |
| **Data Migration** | Migrate existing data to admin user |
| **RBAC** | Advanced (custom roles with granular permissions) |

---

## Current State

| Layer | Status | Gap |
|-------|--------|-----|
| **Frontend** | NextAuth.js with hardcoded demo users | No Auth0, no real user DB |
| **Backend** | Zero authentication | All endpoints open, no JWT validation |
| **Database** | Single-tenant (28+ tables) | No users table, no user_id columns |
| **WebSocket** | Session-based only | No authentication |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Auth0 Tenant                                │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐   │
│   │ Google  │  │ GitHub  │  │ Email/  │  │ Roles & Permissions │   │
│   │  OAuth  │  │  OAuth  │  │Password │  │ (RBAC via Actions)  │   │
│   └────┬────┘  └────┬────┘  └────┬────┘  └──────────┬──────────┘   │
└────────┼────────────┼───────────┼───────────────────┼──────────────┘
         │            │           │                   │
         └────────────┴─────┬─────┴───────────────────┘
                            │ JWT (RS256)
┌───────────────────────────▼─────────────────────────────────────────┐
│                    Frontend (Next.js 14)                            │
│   NextAuth.js v5 → Auth0 Provider → Access Token in Session         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ Bearer Token
┌───────────────────────────▼─────────────────────────────────────────┐
│                    Backend (FastAPI)                                │
│   JWT Middleware → User Context → Permission Checks → User Filtering│
└───────────────────────────┬─────────────────────────────────────────┘
                            │ user_id WHERE clause
┌───────────────────────────▼─────────────────────────────────────────┐
│                    PostgreSQL                                       │
│   users │ roles │ permissions │ user_roles │ role_permissions       │
│   + user_id column on all 28+ existing tables                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### New Tables

```sql
-- Users (synced from Auth0)
nexus.users (
    id, auth0_sub, email, name, picture,
    is_active, is_admin,
    ib_account_id, ib_trading_mode, ib_gateway_port,
    preferences JSONB,
    last_login_at, created_at, updated_at
)

-- RBAC
nexus.roles (id, name, display_name, description, is_system)
nexus.permissions (id, code, display_name, resource_type, action)
nexus.role_permissions (role_id, permission_id)
nexus.user_roles (user_id, role_id, assigned_by, assigned_at)
```

### Permissions Matrix

| Permission | Admin | Trader | Analyst | Viewer |
|------------|:-----:|:------:|:-------:|:------:|
| `read:portfolio` | ✓ | ✓ | ✓ | ✓ |
| `write:portfolio` | ✓ | ✓ | - | - |
| `read:trades` | ✓ | ✓ | ✓ | ✓ |
| `write:trades` | ✓ | ✓ | - | - |
| `read:analyses` | ✓ | ✓ | ✓ | ✓ |
| `write:analyses` | ✓ | ✓ | ✓ | - |
| `read:watchlist` | ✓ | ✓ | ✓ | ✓ |
| `write:watchlist` | ✓ | ✓ | ✓ | - |
| `admin:users` | ✓ | - | - | - |
| `admin:system` | ✓ | - | - | - |

### Tables Requiring user_id Column (28 total)

**Core (8):** stocks, trades, watchlist, schedules, run_history, analysis_results, task_queue, analysis_lineage

**Knowledge Base (10):** kb_stock_analyses, kb_earnings_analyses, kb_research_analyses, kb_ticker_profiles, kb_trade_journals, kb_watchlist_entries, kb_reviews, kb_learnings, kb_strategies, kb_scanner_configs

**Agent UI (3):** sessions, messages, tasks

---

## Implementation Phases

### Phase 1: Auth0 Tenant Setup
**No code changes - Auth0 dashboard configuration**

1. Create Auth0 Application (Regular Web App)
2. Configure callback URLs: `http://localhost:3001/api/auth/callback/auth0`
3. Enable connections: Google, GitHub, Database
4. Create API: `https://tradegent-api.local`
5. Define permissions (scopes) in API settings
6. Create roles: admin, trader, analyst, viewer
7. Create Login Flow Action to add roles/permissions to JWT

**Environment Variables:**
```bash
# Frontend (.env.local)
AUTH0_SECRET=<32-byte-secret>
AUTH0_BASE_URL=http://localhost:3001
AUTH0_ISSUER_BASE_URL=https://your-tenant.auth0.com
AUTH0_CLIENT_ID=<client-id>
AUTH0_CLIENT_SECRET=<client-secret>
AUTH0_AUDIENCE=https://tradegent-api.local

# Backend (.env)
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://tradegent-api.local
```

---

### Phase 2: Database Migrations

**Files to create:**
- `tradegent/db/migrations/010_auth0_users.sql` - Users + RBAC tables
- `tradegent/db/migrations/011_add_user_id_columns.sql` - Add user_id to 28 tables
- `tradegent/db/migrations/012_migrate_existing_data.sql` - Backfill to admin user

**Migration Order:**
1. Create users table with system admin placeholder
2. Create roles, permissions, role_permissions, user_roles
3. Seed default roles and permissions
4. Add user_id columns (nullable initially)
5. Backfill existing data to admin user (user_id = 1)
6. Create indexes on user_id columns

---

### Phase 3: Frontend Authentication

**Files to modify:**
- `frontend/lib/auth.ts` - Replace Credentials with Auth0 provider
- `frontend/app/login/page.tsx` - Auth0 Universal Login redirect
- `frontend/lib/api.ts` - Add Authorization header
- `frontend/lib/websocket.ts` - Add token to WebSocket URL
- `frontend/components/user-menu.tsx` - Update for Auth0 session

**Key Changes:**
```typescript
// lib/auth.ts - Auth0 provider
import Auth0 from 'next-auth/providers/auth0';

providers: [
  Auth0({
    authorization: { params: { audience: AUTH0_AUDIENCE } }
  })
]

// lib/api.ts - Add bearer token
headers['Authorization'] = `Bearer ${session.accessToken}`;

// lib/websocket.ts - Token in URL
wsUrl.searchParams.set('token', accessToken);
```

---

### Phase 4: Backend JWT Validation

**Files to create:**
- `server/auth.py` - JWT validation, UserClaims, permission decorators
- `server/routes/auth.py` - User sync, /api/auth/me, IB account config

**Files to modify:**
- `server/main.py` - Include auth router, protect endpoints
- `server/dashboard.py` - Add user filtering to all queries
- `server/config.py` - Add Auth0 settings

**Key Components:**
```python
# auth.py
async def validate_token(token: str) -> UserClaims
async def get_current_user() -> UserClaims  # Dependency
def require_permission(permission: str)  # Decorator

# Protect endpoint example
@app.get("/api/dashboard/stats")
async def get_stats(user: UserClaims = Depends(get_current_user)):
    user_id = get_db_user_id(user.sub)
    # All queries: WHERE user_id = %s
```

---

### Phase 5: WebSocket Authentication

**Files to modify:**
- `server/main.py` - WebSocket endpoint with token validation

**Changes:**
```python
@app.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket):
    user = await validate_websocket_token(websocket)  # From query param
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    # Continue with authenticated user context
```

---

### Phase 6: Per-User IB Account

**Files to create:**
- `frontend/app/(routes)/settings/ib-account/page.tsx` - IB config UI

**Files to modify:**
- `agent/mcp_client.py` - Pass user's IB account to MCP calls

**User Settings:**
- `ib_account_id` - User's IB account ID
- `ib_trading_mode` - paper | live
- `ib_gateway_port` - For multi-gateway setups

---

### Phase 7: RBAC Admin UI

**Files to create:**
- `frontend/app/(routes)/admin/users/page.tsx` - User management
- `server/routes/admin.py` - Admin API endpoints

**Features:**
- List all users with roles
- Change user roles
- Activate/deactivate users
- View permission matrix

---

## Critical Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `tradegent/db/migrations/010_auth0_users.sql` | Create | Users + RBAC schema |
| `tradegent/db/migrations/011_add_user_id_columns.sql` | Create | Multi-tenancy |
| `tradegent/db/migrations/012_migrate_existing_data.sql` | Create | Data migration |
| `frontend/lib/auth.ts` | Modify | Auth0 provider |
| `frontend/app/login/page.tsx` | Modify | Auth0 login button |
| `frontend/lib/api.ts` | Modify | Bearer token header |
| `frontend/lib/websocket.ts` | Modify | Token in WebSocket |
| `server/auth.py` | Create | JWT validation |
| `server/routes/auth.py` | Create | Auth endpoints |
| `server/main.py` | Modify | Protect all endpoints |
| `server/dashboard.py` | Modify | User filtering |
| `server/config.py` | Modify | Auth0 settings |

---

## Verification

### 1. Database
```bash
# Run migrations
psql -f db/migrations/010_auth0_users.sql
psql -f db/migrations/011_add_user_id_columns.sql
psql -f db/migrations/012_migrate_existing_data.sql

# Verify
psql -c "SELECT * FROM nexus.users;"
psql -c "SELECT * FROM nexus.roles;"
psql -c "SELECT COUNT(*), COUNT(user_id) FROM nexus.stocks;"
```

### 2. Frontend Auth
```bash
npm run dev
# Navigate to http://localhost:3001
# Should redirect to /login
# Click "Sign in with Auth0"
# Complete Auth0 login
# Should redirect to dashboard
```

### 3. Backend Auth
```bash
# Without token (expect 401)
curl http://localhost:8081/api/dashboard/stats

# With token (expect 200)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8081/api/dashboard/stats
```

### 4. WebSocket
```javascript
// Without token (expect close 4001)
new WebSocket('ws://localhost:8081/ws/agent')

// With token (expect connect)
new WebSocket('ws://localhost:8081/ws/agent?token=...')
```

---

## Rollback Plan

1. **Database**: Migrations are additive (new tables, new columns). Rollback by:
   - Setting user_id columns back to nullable
   - Queries work without user filtering

2. **Frontend**: Revert `lib/auth.ts` to Credentials provider

3. **Backend**: Remove auth middleware from endpoint dependencies

---

## Complexity Assessment

| Component | Complexity | Effort |
|-----------|------------|--------|
| Auth0 setup | Low | 2h |
| Database migrations | Medium | 4h |
| Frontend auth | Medium | 6h |
| Backend JWT | Medium | 6h |
| WebSocket auth | Low | 2h |
| Per-user IB | Medium | 4h |
| RBAC admin UI | Medium | 4h |
| Testing | Medium | 4h |
| **Total** | **Medium** | **32h** |

---

## Gap Analysis & Additional Requirements

### Gap 1: Token Refresh

**Issue:** Access tokens expire (default 24h). No refresh handling in plan.

**Solution:**
```typescript
// lib/auth.ts - Add token refresh
callbacks: {
  async jwt({ token, account }) {
    if (account) {
      token.accessToken = account.access_token;
      token.refreshToken = account.refresh_token;
      token.expiresAt = account.expires_at! * 1000;
    }

    // Return existing token if not expired
    if (Date.now() < (token.expiresAt as number)) {
      return token;
    }

    // Refresh expired token
    return await refreshAccessToken(token);
  }
}

async function refreshAccessToken(token: JWT) {
  const response = await fetch(`${AUTH0_ISSUER_URL}/oauth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: AUTH0_CLIENT_ID,
      client_secret: AUTH0_CLIENT_SECRET,
      refresh_token: token.refreshToken as string,
    }),
  });
  // Update token with new access_token
}
```

**Auth0 Config:** Enable "Refresh Token Rotation" in Application settings.

---

### Gap 2: Logout Flow

**Issue:** No federated logout (user stays logged into Auth0).

**Solution:**
```typescript
// lib/auth.ts - Add logout event
events: {
  async signOut({ token }) {
    // Redirect to Auth0 logout
    const logoutUrl = new URL(`${AUTH0_ISSUER_URL}/v2/logout`);
    logoutUrl.searchParams.set('client_id', AUTH0_CLIENT_ID);
    logoutUrl.searchParams.set('returnTo', AUTH0_BASE_URL);
  }
}

// components/user-menu.tsx
const handleLogout = () => {
  signOut({
    callbackUrl: `${AUTH0_ISSUER_URL}/v2/logout?client_id=${AUTH0_CLIENT_ID}&returnTo=${AUTH0_BASE_URL}`
  });
};
```

---

### Gap 3: Account Linking

**Issue:** User signs up with Google, then tries email with same address.

**Solution:** Enable Auth0 Account Linking in dashboard:
1. Auth0 Dashboard → Authentication → Database → Settings
2. Enable "Disable Sign Ups" (force users to use existing identity)
3. Or: Create Auth0 Rule for automatic account linking

---

### Gap 4: Email Verification

**Issue:** New email/password users should verify email.

**Solution:**
1. Auth0 Dashboard → Branding → Email Templates → Verification Email
2. Auth0 Dashboard → Authentication → Database → Require email verification
3. Handle unverified state in frontend:

```typescript
// lib/auth.ts
async jwt({ token, profile }) {
  if (profile?.email_verified === false) {
    token.emailVerified = false;
  }
}

// middleware.ts - Block unverified users
if (!token.emailVerified) {
  return Response.redirect('/verify-email');
}
```

---

### Gap 5: MFA/2FA Support

**Issue:** No multi-factor authentication.

**Solution:**
1. Auth0 Dashboard → Security → Multi-factor Auth
2. Enable "Adaptive MFA" or "Always require MFA"
3. Options: SMS, Authenticator App, Email, WebAuthn

No code changes needed - Auth0 handles MFA in Universal Login.

---

### Gap 6: Rate Limiting

**Issue:** No per-user API rate limits.

**Solution:**
```python
# server/rate_limit.py
from fastapi import Request, HTTPException
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests = defaultdict(list)

    async def check(self, user_id: str):
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.requests[user_id] = [t for t in self.requests[user_id] if t > minute_ago]

        if len(self.requests[user_id]) >= self.rpm:
            raise HTTPException(429, "Rate limit exceeded")

        self.requests[user_id].append(now)

rate_limiter = RateLimiter()

# main.py - Add middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if user := getattr(request.state, "user", None):
        await rate_limiter.check(user.sub)
    return await call_next(request)
```

---

### Gap 7: Audit Logging

**Issue:** No tracking of user actions.

**Solution:**
```sql
-- Migration: 013_audit_log.sql
CREATE TABLE nexus.audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES nexus.users(id),
    action VARCHAR(100) NOT NULL,        -- create_analysis, execute_trade, etc.
    resource_type VARCHAR(50),           -- stock, trade, watchlist
    resource_id VARCHAR(100),            -- ticker or ID
    details JSONB,                       -- Action-specific data
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_user_time ON nexus.audit_log(user_id, created_at DESC);
```

```python
# server/audit.py
async def log_action(user_id: int, action: str, resource_type: str,
                     resource_id: str, details: dict, request: Request):
    # Insert into audit_log
```

---

### Gap 8: API Keys for CLI/Automation

**Issue:** Users need programmatic access without browser login.

**Solution:**
```sql
-- Migration: Add to 010_auth0_users.sql
CREATE TABLE nexus.api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL,       -- SHA-256 of key
    key_prefix VARCHAR(8) NOT NULL,      -- First 8 chars for identification
    name VARCHAR(100),
    permissions TEXT[],                  -- Subset of user's permissions
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

```python
# server/auth.py - Add API key validation
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    token = credentials.credentials

    # Check if it's an API key (starts with "tg_")
    if token.startswith("tg_"):
        return await validate_api_key(token)

    # Otherwise validate as JWT
    return await validate_token(token)
```

---

### Gap 9: Service-to-Service Auth

**Issue:** MCP calls to RAG/Graph/IB don't have user context.

**Solution:**
1. Pass user_id through MCP tool calls
2. MCP servers accept user_id parameter for filtering

```python
# agent/mcp_client.py
async def call_tool(tool_name: str, params: dict, user_id: int):
    params["_user_id"] = user_id  # Internal parameter
    return await self._client.call_tool(tool_name, params)

# rag/mcp_server.py - Update tools
@tool("rag_search")
async def rag_search(query: str, ticker: str = None, _user_id: int = None):
    # Filter by user_id in vector search
```

---

### Gap 10: Knowledge File Storage

**Issue:** tradegent_knowledge YAML files are shared, not per-user.

**Solution Options:**

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A. DB-only** | Store in PostgreSQL kb_* tables only | Simple, user isolated | No file backup |
| **B. User folders** | `knowledge/{user_id}/analysis/...` | File backup | Complex git structure |
| **C. Hybrid** | DB primary, files for admin only | Best of both | Admin-only file access |

**Recommended:** Option C (Hybrid)
- All users store in PostgreSQL kb_* tables with user_id
- Only admin user syncs to tradegent_knowledge repo
- Other users can export to local files if needed

---

### Gap 11: Neo4j User Isolation

**Issue:** Graph database has no user_id on nodes.

**Solution:**
```cypher
// Add user_id property to all nodes
MATCH (n:Ticker) SET n.user_id = 1;
MATCH (n:Analysis) SET n.user_id = 1;

// Update queries to filter
MATCH (t:Ticker {symbol: $ticker, user_id: $user_id})-[r]->(n)
WHERE n.user_id = $user_id
RETURN t, r, n
```

```python
# graph/layer.py - Update all queries
def get_ticker_context(self, ticker: str, user_id: int):
    query = """
    MATCH (t:Ticker {symbol: $ticker, user_id: $user_id})
    ...
    """
```

---

### Gap 12: RAG User Isolation

**Issue:** Vector database embeddings are shared.

**Solution:**
```sql
-- Update rag_documents and rag_chunks
ALTER TABLE nexus.rag_documents ADD COLUMN user_id INTEGER REFERENCES nexus.users(id);
ALTER TABLE nexus.rag_chunks ADD COLUMN user_id INTEGER REFERENCES nexus.users(id);

-- Update search query
SELECT * FROM nexus.rag_chunks
WHERE user_id = $1
ORDER BY embedding <=> $2
LIMIT $3;
```

---

### Gap 13: Testing Strategy

**Issue:** How to test auth without real Auth0?

**Solution:**

**Development:** Mock Auth0 with test tokens
```typescript
// tests/mocks/auth.ts
export const mockSession = {
  user: { id: 'test|123', email: 'test@example.com' },
  accessToken: 'mock-token',
  expires: '2099-01-01',
};
```

**CI/CD:** Use Auth0 test tenant or mock server
```bash
# .env.test
AUTH0_ISSUER_BASE_URL=http://localhost:3333  # Mock server
```

**Backend Tests:**
```python
# tests/conftest.py
@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}

@pytest.fixture(autouse=True)
def mock_auth(monkeypatch):
    async def mock_validate(_):
        return UserClaims(sub="test|123", email="test@test.com")
    monkeypatch.setattr("server.auth.validate_token", mock_validate)
```

---

### Gap 14: IB Gateway Architecture

**Issue:** Per-user IB accounts require separate gateway connections.

**Solution Options:**

| Option | Architecture | Complexity |
|--------|--------------|------------|
| **A. Single gateway, multi-account** | One IB Gateway, switch account per request | Low |
| **B. Gateway pool** | Pool of gateways, assign to users | Medium |
| **C. Per-user gateway** | Docker container per user | High |

**Recommended:** Option A (Single gateway for now)
- Use IB's account switching via `reqAccountUpdates(account)`
- Each user configures their account ID in settings
- Scale to Option B if needed

```python
# ib_mcp - Update for multi-account
async def get_positions(account: str = None):
    if account:
        ib.reqAccountUpdates(True, account)
    # Return positions for specified account
```

---

### Gap 15: Session Management

**Issue:** Multi-device sessions, session revocation.

**Solution:**
```sql
-- Track active sessions
CREATE TABLE nexus.user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(64),
    device_info JSONB,
    ip_address INET,
    last_active_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Session Revocation:**
- Admin can revoke all sessions for a user
- User can revoke specific sessions from Settings

---

### Gap 16: CORS Configuration

**Issue:** Need to allow Auth0 domains.

**Solution:**
```python
# server/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:3001"),
        f"https://{os.getenv('AUTH0_DOMAIN')}",  # Auth0 domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Gap 17: Auth0 Error Handling

**Issue:** What happens when Auth0 is unavailable?

**Solution:**
```typescript
// lib/auth.ts
async jwt({ token, account }) {
  try {
    // Normal flow
  } catch (error) {
    if (error.message.includes('Auth0')) {
      // Log error, allow cached session to continue
      console.error('Auth0 unavailable:', error);
      return token; // Use existing token
    }
    throw error;
  }
}
```

**Backend:** Cache JWKS for 24h, fallback to cached keys if Auth0 unreachable.

---

### Gap 18: User Deletion / GDPR

**Issue:** Users may request data deletion.

**Solution:**
```python
# server/routes/admin.py
@router.delete("/users/{user_id}/data")
async def delete_user_data(
    user_id: int,
    admin: UserClaims = Depends(require_permission("admin:users")),
):
    """Delete all user data (GDPR compliance)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Delete from all tables with user_id
            for table in USER_DATA_TABLES:
                cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))

            # Delete from Neo4j
            await graph.delete_user_data(user_id)

            # Delete from RAG
            await rag.delete_user_data(user_id)

            # Finally delete user
            cur.execute("DELETE FROM nexus.users WHERE id = %s", (user_id,))

            conn.commit()

    return {"status": "deleted"}
```

---

## Updated Implementation Phases

### Phase 8: Token Refresh & Logout (NEW)
**Files to modify:**
- `frontend/lib/auth.ts` - Add token refresh logic
- `frontend/components/user-menu.tsx` - Auth0 federated logout

### Phase 9: Audit & Rate Limiting (NEW)
**Files to create:**
- `tradegent/db/migrations/013_audit_log.sql`
- `server/audit.py`
- `server/rate_limit.py`

### Phase 10: API Keys (NEW)
**Files to create:**
- `frontend/app/(routes)/settings/api-keys/page.tsx`
- `server/routes/api_keys.py`

### Phase 11: Knowledge System User Isolation (NEW)
**Files to modify:**
- `tradegent/rag/search.py` - Add user_id filtering
- `tradegent/graph/layer.py` - Add user_id to queries
- Neo4j migration for user_id property

---

## Revised Complexity Assessment

| Component | Complexity | Effort |
|-----------|------------|--------|
| Auth0 setup | Low | 2h |
| Database migrations | Medium | 6h |
| Frontend auth + refresh | Medium | 8h |
| Backend JWT + rate limit | Medium | 8h |
| WebSocket auth | Low | 2h |
| Per-user IB | Medium | 4h |
| RBAC admin UI | Medium | 4h |
| Audit logging | Low | 2h |
| API keys | Medium | 4h |
| RAG/Graph user isolation | High | 8h |
| Testing | Medium | 4h |
| **Total** | **Medium-High** | **52h** |

---

## Additional Gaps Identified (Round 2)

### Gap 19: Blocked User Mid-Session

**Issue:** Admin deactivates user while they have active session.

**Solution:**
```python
# server/auth.py - Check user status on each request
async def get_current_user(...) -> UserClaims:
    claims = await validate_token(token)

    # Check if user is still active in database
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT is_active FROM nexus.users WHERE auth0_sub = %s",
                (claims.sub,)
            )
            row = cur.fetchone()
            if not row or not row["is_active"]:
                raise HTTPException(403, "Account deactivated")

    return claims
```

**Frontend:** Handle 403 response by redirecting to login with message.

---

### Gap 20: New User Onboarding Flow

**Issue:** New users need guided setup (IB account, preferences).

**Solution:**
```typescript
// frontend/app/(routes)/onboarding/page.tsx
// Step 1: Welcome + profile info
// Step 2: IB Account connection (optional)
// Step 3: Preferences (default analysis type, notifications)
// Step 4: Tour of features

// lib/auth.ts - Redirect new users to onboarding
async session({ session, token }) {
  const user = await fetchUserFromDb(token.sub);
  if (user.preferences?.onboarding_completed !== true) {
    session.requiresOnboarding = true;
  }
  return session;
}

// middleware.ts
if (session.requiresOnboarding && !pathname.startsWith('/onboarding')) {
  return Response.redirect('/onboarding');
}
```

---

### Gap 21: User Profile Page

**Issue:** No page for users to update their profile info.

**Solution:**
```typescript
// frontend/app/(routes)/settings/profile/page.tsx
// - Name (synced from Auth0, can override)
// - Email (read-only, from Auth0)
// - Avatar (from Auth0 or upload)
// - Timezone preference
// - Notification settings

// backend/server/routes/users.py
@router.put("/api/users/me/profile")
async def update_profile(
    name: str = None,
    timezone: str = None,
    notification_prefs: dict = None,
    user: UserClaims = Depends(get_current_user),
):
    # Update user preferences in database
```

---

### Gap 22: Invite-Only vs Open Registration

**Issue:** Should anyone be able to sign up, or invite-only?

**Solution Options:**

| Mode | Implementation | When to Use |
|------|----------------|-------------|
| **Open** | Anyone can register via Auth0 | Public product |
| **Invite-only** | Admin generates invite codes | Private/Enterprise |
| **Allowlist** | Only pre-approved emails can register | Controlled access |

**For Invite-Only:**
```sql
CREATE TABLE nexus.invites (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    email VARCHAR(255),              -- Optional: restrict to specific email
    created_by INTEGER REFERENCES nexus.users(id),
    used_by INTEGER REFERENCES nexus.users(id),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

```typescript
// Auth0 Action - Check invite code
exports.onExecutePreUserRegistration = async (event, api) => {
  const inviteCode = event.request.query?.invite;
  if (!inviteCode) {
    api.access.deny('invalid_invite', 'Invite code required');
  }
  // Validate invite code via API
};
```

**Recommended:** Start with allowlist (only specified emails can register), expand later.

---

### Gap 23: db_layer.py Method Updates

**Issue:** 80+ database methods need user_id parameter.

**Solution:** Create a migration checklist:

| Method Category | Methods | Changes Needed |
|-----------------|---------|----------------|
| **Stocks** | `get_enabled_stocks`, `add_stock`, `update_stock`, `delete_stock` | Add `user_id` param |
| **Trades** | `get_trades`, `add_trade`, `update_trade`, `get_trade_by_id` | Add `user_id` param |
| **Watchlist** | `get_watchlist`, `add_to_watchlist`, `remove_from_watchlist` | Add `user_id` param |
| **Schedules** | `get_schedules`, `create_schedule`, `update_schedule` | Add `user_id` param |
| **Analysis** | `save_analysis`, `get_analysis_results`, `get_analysis_history` | Add `user_id` param |
| **KB Tables** | All kb_* getters and setters | Add `user_id` param |
| **Task Queue** | `enqueue_task`, `get_pending_tasks`, `complete_task` | Add `user_id` param |
| **Run History** | `log_run`, `get_run_history` | Add `user_id` param |

**Pattern:**
```python
# Before
def get_enabled_stocks(self, state: str | None = None):
    query = "SELECT * FROM nexus.stocks WHERE is_enabled = true"

# After
def get_enabled_stocks(self, user_id: int, state: str | None = None):
    query = "SELECT * FROM nexus.stocks WHERE user_id = %s AND is_enabled = true"
    params = [user_id]
```

---

### Gap 24: Frontend TypeScript Types

**Issue:** Types need user context.

**Solution:**
```typescript
// types/auth.ts
export interface UserSession {
  id: string;          // Auth0 sub
  email: string;
  name?: string;
  picture?: string;
  roles: string[];
  permissions: string[];
  ib_account_id?: string;
  ib_trading_mode?: 'paper' | 'live';
}

// Extend NextAuth types
declare module 'next-auth' {
  interface Session {
    user: UserSession;
    accessToken: string;
    requiresOnboarding?: boolean;
  }
}

// types/api.ts - Add user context to requests
export interface ApiContext {
  user_id: number;
  permissions: string[];
}
```

---

### Gap 25: Public vs Protected Endpoints

**Issue:** Which endpoints should remain public?

**Solution:**

| Endpoint | Access | Reason |
|----------|--------|--------|
| `/health` | Public | Kubernetes probes |
| `/ready` | Public | Load balancer checks |
| `/api/auth/sync-user` | Semi-public* | Called during login flow |
| `/api/chat` | Protected | User data |
| `/api/dashboard/*` | Protected | User data |
| `/api/task/*` | Protected | User data |
| `/ws/agent` | Protected | User data |

*`sync-user` should validate the request comes from Auth0 callback.

```python
# server/main.py
PUBLIC_ENDPOINTS = ["/health", "/ready", "/api/auth/sync-user"]

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in PUBLIC_ENDPOINTS:
        return await call_next(request)

    # Require auth for all other endpoints
    token = request.headers.get("Authorization")
    if not token:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # ... validate token
```

---

### Gap 26: Production Deployment Checklist

**Issue:** Different configurations for dev/staging/prod.

**Solution:**

| Setting | Development | Production |
|---------|-------------|------------|
| `AUTH0_BASE_URL` | `http://localhost:3001` | `https://app.tradegent.io` |
| `AUTH0_AUDIENCE` | `https://tradegent-api.local` | `https://api.tradegent.io` |
| Token expiry | 24h | 1h (with refresh) |
| MFA | Disabled | Adaptive |
| Rate limits | 120/min | 60/min |
| HTTPS | Optional | Required |
| Cookies | `SameSite=Lax` | `SameSite=Strict; Secure` |

**Environment-specific configs:**
```bash
# .env.development
AUTH0_BASE_URL=http://localhost:3001
NEXTAUTH_URL=http://localhost:3001

# .env.production
AUTH0_BASE_URL=https://app.tradegent.io
NEXTAUTH_URL=https://app.tradegent.io
```

---

### Gap 27: Concurrent Login Limits

**Issue:** Should we limit active sessions per user?

**Solution:**
```sql
-- Check session count before allowing new login
SELECT COUNT(*) FROM nexus.user_sessions
WHERE user_id = $1 AND expires_at > now();

-- If > 5 active sessions, force logout oldest
DELETE FROM nexus.user_sessions
WHERE id = (
    SELECT id FROM nexus.user_sessions
    WHERE user_id = $1
    ORDER BY created_at ASC
    LIMIT 1
);
```

**Config:**
```python
# server/config.py
MAX_SESSIONS_PER_USER = 5
```

---

### Gap 28: Password Reset UI

**Issue:** Password reset handled by Auth0 but needs UI integration.

**Solution:**
```typescript
// frontend/app/login/page.tsx
<Button
  variant="link"
  onClick={() => {
    // Redirect to Auth0 password reset
    window.location.href = `${AUTH0_ISSUER_URL}/u/reset-password?client_id=${AUTH0_CLIENT_ID}`;
  }}
>
  Forgot password?
</Button>
```

Auth0 Dashboard: Configure email templates for password reset.

---

## Final Implementation Phases (Complete)

| Phase | Description | Effort |
|-------|-------------|--------|
| 1 | Auth0 Tenant Setup | 2h |
| 2 | Database Migrations (users, RBAC, user_id columns) | 6h |
| 3 | Frontend Auth (Auth0 provider, login, middleware) | 8h |
| 4 | Backend JWT Validation + Rate Limiting | 8h |
| 5 | WebSocket Authentication | 2h |
| 6 | Per-User IB Account | 4h |
| 7 | RBAC Admin UI | 4h |
| 8 | Token Refresh & Logout | 3h |
| 9 | Audit Logging | 2h |
| 10 | API Keys for CLI | 4h |
| 11 | RAG/Graph User Isolation | 8h |
| 12 | db_layer.py Refactoring | 6h |
| 13 | Onboarding Flow | 4h |
| 14 | User Profile & Settings Pages | 3h |
| 15 | Testing & Verification | 4h |
| **Total** | | **68h** |

---

## Complete Files Checklist

### New Files to Create (17)

| File | Purpose |
|------|---------|
| `db/migrations/010_auth0_users.sql` | Users + RBAC tables |
| `db/migrations/011_add_user_id_columns.sql` | Multi-tenancy |
| `db/migrations/012_migrate_existing_data.sql` | Data migration |
| `db/migrations/013_audit_log.sql` | Audit trail |
| `server/auth.py` | JWT validation |
| `server/rate_limit.py` | Per-user rate limiting |
| `server/audit.py` | Audit logging |
| `server/routes/auth.py` | Auth endpoints |
| `server/routes/admin.py` | Admin endpoints |
| `server/routes/api_keys.py` | API key management |
| `frontend/app/(routes)/onboarding/page.tsx` | New user onboarding |
| `frontend/app/(routes)/settings/profile/page.tsx` | User profile |
| `frontend/app/(routes)/settings/ib-account/page.tsx` | IB settings |
| `frontend/app/(routes)/settings/api-keys/page.tsx` | API keys UI |
| `frontend/app/(routes)/admin/users/page.tsx` | User management |
| `frontend/types/auth.ts` | Auth TypeScript types |
| `tests/mocks/auth.ts` | Auth test mocks |

### Files to Modify (15)

| File | Changes |
|------|---------|
| `frontend/lib/auth.ts` | Auth0 provider + token refresh |
| `frontend/lib/api.ts` | Bearer token header |
| `frontend/lib/websocket.ts` | Token in WebSocket |
| `frontend/middleware.ts` | Protected routes + onboarding |
| `frontend/components/user-menu.tsx` | Auth0 logout |
| `frontend/app/login/page.tsx` | Auth0 login button |
| `server/main.py` | Auth middleware + protected endpoints |
| `server/config.py` | Auth0 settings |
| `server/dashboard.py` | User filtering |
| `tradegent/db_layer.py` | Add user_id to all methods |
| `tradegent/rag/search.py` | User isolation |
| `tradegent/rag/embed.py` | User isolation |
| `tradegent/graph/layer.py` | User isolation |
| `agent/mcp_client.py` | Pass user context |
| `.env.local.example` | Auth0 variables |
