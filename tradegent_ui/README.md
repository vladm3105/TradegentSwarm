# Tradegent Agent UI

Agent-driven user interface for the Tradegent trading platform. Natural language interaction with trading operations through dynamically generated A2UI components.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              Tradegent Frontend (Next.js 14) - Port 3001            │
│         App Router │ TypeScript │ Tailwind │ A2UI Renderer          │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ REST API + WebSocket
                                 │ HTTP: /api/* │ WS: /ws/agent
┌────────────────────────────────▼────────────────────────────────────┐
│                  AG-UI Server (FastAPI) - Port 8081                 │
├─────────────────────────────────────────────────────────────────────┤
│                        COORDINATOR AGENT                            │
│              (Intent Classification + Routing)                      │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│   Analysis   │    Trade     │   Portfolio  │     Research          │
│    Agent     │    Agent     │    Agent     │      Agent            │
└──────────────┴──────────────┴──────────────┴───────────────────────┘
                                 │ MCP Protocol
┌────────────────────────────────▼────────────────────────────────────┐
│                         MCP Servers                                  │
│   trading-rag (stdio) │ trading-graph (stdio) │ ib-mcp (HTTP:8100)  │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### One-command startup (recommended)

From repository root, start backend + frontend together:

```bash
./scripts/start_tradegent_ui.sh
```

This prevents the common reconnect loop caused by frontend running while backend is down.

### 1. Configure Environment

```bash
cd tradegent_ui/server

# Copy example and configure
cp ../.env.example .env

# Edit .env and set REQUIRED variables:
# - ADMIN_EMAIL (e.g., admin@tradegent.local)
# - ADMIN_PASSWORD (e.g., TradegentAdmin2024!)
# - JWT_SECRET (generate with: openssl rand -base64 32)
# - PG_PASS (PostgreSQL password)
# - LLM_API_KEY (OpenRouter or OpenAI API key)
```

### 2. Start Backend Server

```bash
cd tradegent_ui

# Install dependencies
pip install -e .

# Run database migrations
psql -h localhost -p 5433 -U tradegent -d tradegent -f db/schema.sql

# Start server (validates required config on startup)
uvicorn server.main:app --host 0.0.0.0 --port 8081 --reload
```

### 3. Start Frontend (Next.js)

```bash
cd tradegent_ui/frontend

# Install dependencies
npm install

# Start development server (port 3001)
npm run dev

# Or run with Docker
docker build -t tradegent-frontend .
docker run -p 3001:3000 -e NEXT_PUBLIC_API_URL=http://localhost:8081 tradegent-frontend
```

### 4. Run Database Migrations (Auth Support)

```bash
# Run auth migrations (010-014)
cat db/migrations/010_auth0_users.sql | docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent
cat db/migrations/011_add_user_id_columns.sql | docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent
cat db/migrations/012_migrate_existing_data.sql | docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent
cat db/migrations/013_audit_log.sql | docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent
cat db/migrations/014_settings_section.sql | docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent
```

### 5. Access UI

Open http://localhost:3001 in your browser.

**Built-in Accounts:**
| Account | Email | Password | Roles |
|---------|-------|----------|-------|
| Admin (Superuser) | admin@tradegent.local | (set in .env) | admin |
| Demo | demo@tradegent.local | (set in .env) | trader |

> **Note:** The admin account is similar to PostgreSQL's `postgres` user - a superuser that always exists. Credentials are stored in `.env` and authentication is **always enabled**.

## Authentication & Authorization

> **Security:** Authentication is **always enabled** and cannot be disabled. This prevents accidental exposure in production.

### Authentication Modes

The system supports two authentication modes:

| Mode | Description | When Used |
|------|-------------|-----------|
| **Built-in Auth** | Email/password with HS256 JWT tokens | Default (Auth0 not configured) |
| **Auth0** | Social login (Google, GitHub) + email/password | When Auth0 is configured |

### Admin User (Superuser)

Similar to PostgreSQL's `postgres` user, the admin user is a superuser that always exists. Admin credentials are stored in `.env` and validated at startup - the server will not start without them.

**Required Environment Variables:**

```bash
# server/.env (REQUIRED)
APP_ENV=development  # use production in deployed environments
DEBUG=false
ALLOW_DEMO_TOKENS=false
ADMIN_EMAIL=admin@tradegent.local
ADMIN_PASSWORD=<YOUR_SECURE_PASSWORD>  # CHANGE THIS!
ADMIN_NAME=System Administrator
JWT_SECRET=<generate-with-openssl-rand-base64-32>  # CHANGE THIS!

# Optional demo account
DEMO_EMAIL=
DEMO_PASSWORD=
```

**Generate JWT Secret:**
```bash
openssl rand -base64 32
```

**Startup Validation:**
The server validates these required settings on startup:
- `ADMIN_EMAIL` - Must be set
- `ADMIN_PASSWORD` - Must be set
- `JWT_SECRET` - Must be set (for token signing)

If any are missing, the server exits with a clear error message.

### Auth0 Configuration

To enable Auth0 authentication:

1. **Create Auth0 Application** in the Auth0 Dashboard:
   - Application Type: Regular Web Application
   - Allowed Callback URLs: `http://localhost:3001/api/auth/callback/auth0`
   - Allowed Logout URLs: `http://localhost:3001`
   - Allowed Web Origins: `http://localhost:3001`

2. **Create Auth0 API**:
   - Identifier: `https://tradegent-api.local`
   - Enable RBAC and "Add Permissions in Access Token"

3. **Configure in Settings UI**:
   - Login as admin
   - Go to Settings > Auth0 tab
   - Enter Auth0 Domain, Client ID, Client Secret
   - Click Save and request server restart

### RBAC (Role-Based Access Control)

The system implements role-based access control with four predefined roles. Each role is designed for a specific user persona with appropriate permissions.

#### Role Definitions

**Admin** (`admin`)
- **Description**: Full system access including user management and configuration
- **Use Case**: System administrators, platform owners
- **Capabilities**:
  - All trading and analysis capabilities
  - User management (create, update, deactivate users)
  - Role assignment and permission management
  - System configuration (Auth0, rate limits, etc.)
  - View audit logs and login history
  - GDPR data deletion
  - Access to all API endpoints

**Trader** (`trader`)
- **Description**: Full trading capabilities with portfolio and position management
- **Use Case**: Active traders executing trades
- **Capabilities**:
  - View and manage portfolio positions
  - Execute trades (paper and live)
  - Create and manage trade journal entries
  - Run stock and earnings analyses
  - Manage watchlist entries
  - Search and query knowledge base
  - Configure personal IB account settings
  - Create API keys for automation
- **Restrictions**: No access to admin functions or user management

**Analyst** (`analyst`)
- **Description**: Research and analysis capabilities without trade execution
- **Use Case**: Research analysts, strategists, interns
- **Capabilities**:
  - Run stock and earnings analyses
  - Create and manage watchlist entries
  - Search and query knowledge base
  - Add learnings and strategies to knowledge base
  - View portfolio (read-only)
  - View trade history (read-only)
- **Restrictions**: Cannot execute trades or manage positions

**Viewer** (`viewer`)
- **Description**: Read-only access to all dashboards and data
- **Use Case**: Stakeholders, observers, compliance reviewers
- **Capabilities**:
  - View portfolio positions and P&L
  - View trade history and journal
  - View analyses and watchlist
  - View knowledge base content
  - View dashboard metrics
- **Restrictions**: Cannot create, modify, or execute anything

#### Permissions Matrix
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
| `read:knowledge` | ✓ | ✓ | ✓ | ✓ |
| `write:knowledge` | ✓ | ✓ | ✓ | - |
| `admin:users` | ✓ | - | - | - |
| `admin:system` | ✓ | - | - | - |

#### Role Management

**Assigning Roles (Admin Only)**

Roles are managed via the Admin UI or API:

```bash
# Via API
curl -X PUT "http://localhost:8081/api/admin/users/2/roles" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["trader", "analyst"]}'
```

**Via Admin UI**:
1. Login as admin
2. Navigate to Admin > Users
3. Click on a user
4. Select roles from dropdown
5. Save changes

**Default Role Assignment**:
- New users via Auth0: No roles (must be assigned by admin)
- Admin user (superuser): `admin` role with all permissions
- Demo user: `trader` role

**Multiple Roles**:
Users can have multiple roles. Permissions are combined (union):
- User with `trader` + `analyst` = all trader permissions + all analyst permissions
- Most users need only one role

#### Role-Based UI Features

| Feature | Admin | Trader | Analyst | Viewer |
|---------|:-----:|:------:|:-------:|:------:|
| Dashboard | ✓ | ✓ | ✓ | ✓ |
| Chat Interface | ✓ | ✓ | ✓ | View only |
| Portfolio Page | Full | Full | Read-only | Read-only |
| Trades Page | Full | Full | Read-only | Read-only |
| Analyses Page | Full | Full | Full | Read-only |
| Watchlist Page | Full | Full | Full | Read-only |
| Settings Page | Full + Auth0 | Full | Full | Limited |
| Admin Panel | ✓ | - | - | - |

### API Keys

Users can create API keys for CLI/automation access:

```bash
# API key format: tg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Use in requests:
curl -H "Authorization: Bearer tg_your_api_key" http://localhost:8081/api/dashboard/stats
```

**API Key Features:**
- Created via Settings > API Keys
- Optional expiration dates
- Key shown only once on creation
- Can be revoked at any time

### WebSocket Authentication

WebSocket connections require a token:

```javascript
// Pass token via websocket subprotocol (browser-safe)
const ws = new WebSocket('ws://localhost:8081/ws/agent', ['bearer', yourJwtToken]);
```

Notes:
- Query-string token auth (`?token=...`) is not supported.
- The same subprotocol token pattern is required for `/ws/stream`.

## API Endpoints

### REST API

**Core Endpoints:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check with MCP server status |
| `/ready` | GET | No | Kubernetes readiness probe |
| `/api/chat` | POST | Yes | Process chat message |
| `/api/task/{task_id}` | GET | Yes | Get task status |
| `/api/task/{task_id}` | DELETE | Yes | Cancel task |
| `/api/stats` | GET | Yes | System statistics |

**Authentication Endpoints:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/me` | GET | Yes | Get current user profile |
| `/api/auth/sync-user` | POST | Yes | Sync authenticated user profile during login flow |
| `/api/auth/complete-onboarding` | POST | Yes | Mark onboarding completed |

**User Endpoints:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/users/me/profile` | PUT | Yes | Update user profile |
| `/api/users/me/ib-account` | GET | Yes | Get IB account settings |
| `/api/users/me/ib-account` | PUT | Yes | Update IB account settings |
| `/api/users/me/api-keys` | GET | Yes | List user's API keys |
| `/api/users/me/api-keys` | POST | Yes | Create new API key |
| `/api/users/me/api-keys/{id}` | DELETE | Yes | Revoke API key |

**Admin Endpoints (admin role required):**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/users` | GET | Admin | List all users |
| `/api/admin/users/{id}/roles` | PUT | Admin | Update user roles |
| `/api/admin/users/{id}/status` | PUT | Admin | Activate/deactivate user |
| `/api/admin/users/{id}/data` | DELETE | Admin | Delete user data (GDPR) |
| `/api/admin/roles` | GET | Admin | List all roles |
| `/api/admin/permissions` | GET | Admin | List all permissions |

**Settings Endpoints (admin role required):**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/settings/system` | GET | Admin | Get system settings |
| `/api/settings/auth0` | GET | Admin | Get Auth0 config (secrets masked) |
| `/api/settings/auth0` | PUT | Admin | Update Auth0 configuration |
| `/api/settings/restart-server` | POST | Admin | Request server restart |

**Dashboard Endpoints:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/dashboard/stats` | GET | Yes | Dashboard statistics |
| `/api/dashboard/pnl` | GET | Yes | P&L summary |
| `/api/dashboard/performance` | GET | Yes | Performance metrics |
| `/api/dashboard/analysis-quality` | GET | Yes | Analysis quality metrics |
| `/api/dashboard/service-health` | GET | Yes | Service health status |
| `/api/dashboard/watchlist-summary` | GET | Yes | Watchlist summary |

**Watchlist Endpoints:**
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/watchlists` | GET | Yes | List named watchlists (manual/scanner/auto) with entry counts |
| `/api/watchlists` | POST | Yes | Create manual watchlist |
| `/api/watchlists/{id}` | PATCH | Yes | Update watchlist metadata (name, description, color, pinned) |
| `/api/watchlists/{id}` | DELETE | Yes | Delete empty manual watchlist |
| `/api/watchlist/list` | GET | Yes | List watchlist entries (supports `watchlist_id` filter) |
| `/api/watchlist/detail/{id}` | GET | Yes | Get single watchlist entry details |
| `/api/watchlist/stats` | GET | Yes | Get watchlist stats (supports `watchlist_id` filter) |

Notes:
- `watchlist_source_type` values are `manual`, `scanner`, or `auto`.
- The default auto-generated list is `Analysis Signals`.

> **Note:** Dashboard endpoints return real data from PostgreSQL BI views. See [Dashboard Data Source](#dashboard-data-source) section below.

### WebSocket

Connect to `ws://localhost:8080/ws/agent` for real-time communication.

**Message Types:**

```json
// Send message
{"type": "message", "content": "analyze NVDA", "async": false}

// Subscribe to task progress
{"type": "subscribe", "task_id": "abc-123"}

// Ping
{"type": "ping"}
```

## A2UI Components

| Component | Description |
|-----------|-------------|
| `AnalysisCard` | Stock analysis summary with recommendation |
| `PositionCard` | Portfolio position with P&L |
| `TradeCard` | Trade journal entry |
| `WatchlistCard` | Watchlist entry with trigger |
| `GateResult` | Do Nothing Gate result |
| `ScenarioChart` | Scenario probability visualization |
| `MetricsRow` | Key metrics display |
| `ChartCard` | Price/data chart |
| `ErrorCard` | Error display |
| `LoadingCard` | Loading state |
| `TextCard` | Rich text content |
| `TableCard` | Data table |

## Configuration

### Backend Environment Variables (server/.env)

**Core Settings:**
| Variable | Default | Description |
|----------|---------|-------------|
| `AGUI_HOST` | 0.0.0.0 | Server host |
| `AGUI_PORT` | 8081 | Server port |
| `FRONTEND_URL` | http://localhost:3001 | Frontend URL for CORS |
| `DEBUG` | false | Enable debug logging |

**LLM Settings:**
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | openrouter | LLM provider |
| `LLM_API_KEY` | - | LLM API key (required) |
| `LLM_MODEL` | google/gemini-2.0-flash-001 | LLM model |

**Database Settings:**
| Variable | Default | Description |
|----------|---------|-------------|
| `PG_HOST` | localhost | PostgreSQL host |
| `PG_PORT` | 5433 | PostgreSQL port |
| `PG_USER` | tradegent | PostgreSQL user |
| `PG_PASS` | - | PostgreSQL password (required) |
| `PG_DB` | tradegent | PostgreSQL database |

**IB MCP Settings:**
| Variable | Default | Description |
|----------|---------|-------------|
| `IB_MCP_URL` | http://localhost:8100/mcp | IB MCP server URL |

**Admin User (REQUIRED):**
| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_EMAIL` | - | Admin user email (REQUIRED) |
| `ADMIN_PASSWORD` | - | Admin user password - plaintext (REQUIRED) |
| `ADMIN_NAME` | System Administrator | Admin user display name |
| `JWT_SECRET` | - | Secret for JWT signing - 32 bytes (REQUIRED) |

**Demo Account (Optional):**
| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_EMAIL` | demo@tradegent.local | Demo user email |
| `DEMO_PASSWORD` | demo123 | Demo user password |

**Auth0 Settings (Optional):**
| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH0_DOMAIN` | - | Auth0 tenant domain |
| `AUTH0_CLIENT_ID` | - | Auth0 client ID |
| `AUTH0_CLIENT_SECRET` | - | Auth0 client secret |
| `AUTH0_AUDIENCE` | https://tradegent-api.local | Auth0 API audience |

**Rate Limiting:**
| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | true | Enable rate limiting |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | 60 | Max requests/minute per user |
| `MAX_SESSIONS_PER_USER` | 5 | Max concurrent sessions |

### Skill Settings

Analysis skills have optional features controlled via database settings.

**SVG Generation:**

When using the Agent UI, SVG generation is typically disabled since the UI provides its own visualization. This reduces disk usage and processing time.

```bash
# Disable SVG generation (recommended when using Agent UI)
python tradegent.py settings set svg_generation_enabled false

# Enable SVG generation (for file-based workflows)
python tradegent.py settings set svg_generation_enabled true

# Check current setting
python tradegent.py settings get svg_generation_enabled
```

| Setting | Default | Description |
|---------|---------|-------------|
| `svg_generation_enabled` | true | Generate SVG dashboard visualizations for analyses |

**Via SQL:**
```sql
-- Check setting
SELECT value FROM nexus.settings WHERE section = 'skills' AND key = 'svg_generation_enabled';

-- Disable
UPDATE nexus.settings SET value = 'false' WHERE section = 'skills' AND key = 'svg_generation_enabled';

-- Enable
UPDATE nexus.settings SET value = 'true' WHERE section = 'skills' AND key = 'svg_generation_enabled';
```

### Frontend Environment Variables (frontend/.env.local)

**Core Settings:**
| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | http://localhost:8081 | Backend API URL |
| `NEXTAUTH_URL` | http://localhost:3001 | NextAuth base URL |
| `NEXTAUTH_SECRET` | - | NextAuth encryption secret |

**Built-in Authentication:**
| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_EMAIL` | admin@tradegent.local | Admin user email |
| `ADMIN_PASSWORD` | - | Admin user password |
| `DEMO_EMAIL` | demo@tradegent.local | Demo user email |
| `DEMO_PASSWORD` | - | Demo user password |

**Auth0 Settings (Optional — NextAuth v5 provider):**
| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_AUTH0_CONFIGURED` | false | Auth0 enabled flag |
| `AUTH0_CLIENT_ID` | - | Auth0 client ID |
| `AUTH0_CLIENT_SECRET` | - | Auth0 client secret |
| `AUTH0_DOMAIN` | - | Auth0 tenant domain (e.g., `dev-xxx.us.auth0.com`) |
| `AUTH0_AUDIENCE` | https://tradegent-api.local | Auth0 API audience |

## Database Schema

### Auth Tables (Migration 010)

```sql
-- Users (synced from Auth0)
nexus.users (
    id, auth0_sub, email, name, picture,
    is_active, is_admin, email_verified,
    ib_account_id, ib_trading_mode, ib_gateway_port,
    preferences JSONB,
    last_login_at, created_at, updated_at
)

-- RBAC
nexus.roles (id, name, display_name, description, is_system)
nexus.permissions (id, code, display_name, resource_type, action)
nexus.role_permissions (role_id, permission_id)
nexus.user_roles (user_id, role_id, assigned_by, assigned_at)

-- API Keys
nexus.api_keys (id, user_id, key_hash, key_prefix, name, permissions, expires_at)

-- Sessions
nexus.user_sessions (id, user_id, session_token_hash, device_info, ip_address, expires_at)
```

### Audit Tables (Migration 013)

```sql
-- Audit Log
nexus.audit_log (id, user_id, action, resource_type, resource_id, details, ip_address, created_at)

-- Login History
nexus.login_history (id, user_id, success, ip_address, user_agent, failure_reason, created_at)

-- GDPR Deletion Requests
nexus.gdpr_deletion_requests (id, user_id, user_email, status, tables_cleared, processed_at)
```

### Multi-Tenancy (Migration 011-012)

All user-specific tables have a `user_id` column for data isolation:
- Core: stocks, trades, watchlist, schedules, run_history, analysis_results, task_queue
- Knowledge Base: kb_stock_analyses, kb_earnings_analyses, kb_research_analyses, etc.
- RAG: rag_documents, rag_chunks
- Agent UI: sessions, messages, tasks

### Helper Functions

```sql
-- Get user permissions
SELECT nexus.get_user_permissions(1);  -- Returns TEXT[]

-- Check permission
SELECT nexus.user_has_permission(1, 'write:trades');  -- Returns BOOLEAN

-- Get user roles
SELECT nexus.get_user_roles(1);  -- Returns TEXT[]

-- Log audit action
SELECT nexus.log_audit(1, 'trade.execute', 'trade', '123', '{"ticker": "NVDA"}');
```

## Dashboard Data Source

The dashboard endpoints (`/api/dashboard/*`) retrieve real data from PostgreSQL BI views. These views aggregate data from the core tables for efficient querying.

### BI Views

| View | Dashboard Endpoint | Description |
|------|-------------------|-------------|
| `v_bi_portfolio_summary` | `/stats` | Total P&L, open positions, market value |
| `v_bi_daily_pnl` | `/stats`, `/pnl` | Daily P&L with cumulative tracking |
| `v_bi_weekly_pnl` | `/pnl` | Weekly P&L aggregation |
| `v_bi_monthly_pnl` | `/pnl` | Monthly P&L with cumulative |
| `v_bi_ticker_performance` | `/stats`, `/performance` | Performance by ticker |

### Applying BI Views

If dashboard shows mock data, apply the BI views:

```bash
# Apply BI views to database
docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent < tradegent/db/bi_views.sql

# Verify views exist
docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent -c \
  "SELECT viewname FROM pg_views WHERE schemaname = 'nexus' AND viewname LIKE 'v_bi_%';"
```

### Data Tables

The BI views aggregate data from these core tables:

| Table | Data Source |
|-------|-------------|
| `nexus.trades` | Trade journal entries (entry/exit, P&L) |
| `nexus.kb_stock_analyses` | Stock analysis records |
| `nexus.kb_watchlist_entries` | Watchlist entries |
| `nexus.confidence_calibration` | Prediction accuracy tracking |

### Fallback Behavior

If database queries fail (connection error, missing views), endpoints return mock data to prevent frontend errors. Check server logs for `*_error` messages to diagnose issues.

## Project Structure

```
tradegent_ui/
├── agent/                      # Python agents
│   ├── base_agent.py          # Base class with MCP integration
│   ├── coordinator.py          # Intent routing
│   ├── analysis_agent.py       # Analysis operations
│   ├── trade_agent.py          # Trade operations
│   ├── portfolio_agent.py      # Portfolio operations
│   ├── research_agent.py       # RAG/Graph queries
│   ├── mcp_client.py           # MCP client pool
│   ├── stdio_mcp.py            # Stdio MCP client
│   ├── intent_classifier.py    # Intent classification
│   ├── llm_client.py           # LLM for A2UI generation
│   ├── context_manager.py      # Conversation context
│   └── tool_mappings.py        # Tool → MCP mapping
│
├── server/                     # FastAPI server
│   ├── main.py                # ASGI app with auth middleware
│   ├── config.py              # Configuration with auth settings
│   ├── auth.py                # JWT validation, permissions
│   ├── database.py            # PostgreSQL connection pool
│   ├── audit.py               # Audit logging
│   ├── rate_limit.py          # Per-user rate limiting
│   ├── errors.py              # Error hierarchy
│   ├── task_manager.py        # Long-running tasks
│   ├── dashboard.py           # Dashboard endpoints
│   ├── .env                   # Backend environment variables
│   └── routes/
│       ├── __init__.py
│       ├── auth.py            # Auth endpoints (/api/auth/*)
│       ├── admin.py           # Admin endpoints (/api/admin/*)
│       ├── users.py           # User endpoints (/api/users/*)
│       └── settings.py        # Settings endpoints (/api/settings/*)
│
├── frontend/                   # Next.js 14 application (TypeScript, strict)
│   ├── app/
│   │   ├── login/page.tsx     # Login page
│   │   ├── verify-email/page.tsx
│   │   └── (routes)/
│   │       ├── settings/page.tsx  # Settings with Auth0 tab
│   │       ├── admin/users/page.tsx
│   │       └── onboarding/page.tsx
│   ├── components/            # React components
│   ├── hooks/                 # Custom React hooks
│   ├── lib/
│   │   ├── auth.ts            # NextAuth v5 (built-in credentials + Auth0)
│   │   ├── api.ts             # Typed REST client (UserProfile, AdminUser, ApiKey)
│   │   ├── messages.ts        # TradegentMessage envelope types
│   │   ├── unified-client.ts  # Transport-agnostic REST + WS client facade
│   │   ├── websocket.ts       # Low-level WebSocket client
│   │   ├── websocket-auth.ts  # Auth-aware WebSocket helpers
│   │   └── logger.ts          # Structured browser logger
│   ├── stores/                # Zustand state management
│   ├── types/                 # TypeScript types
│   ├── .env.local             # Frontend environment variables
│   └── README.md              # Frontend documentation
│
├── db/
│   ├── schema.sql             # Base database schema
│   └── migrations/
│       ├── 010_auth0_users.sql      # Users, roles, permissions
│       ├── 011_add_user_id_columns.sql
│       ├── 012_migrate_existing_data.sql
│       ├── 013_audit_log.sql        # Audit & login history
│       └── 014_settings_section.sql # Settings table update
│
├── schemas/
│   └── a2ui_schema.json       # A2UI JSON schema
│
├── pyproject.toml
└── README.md
```

## Logging & Observability

### Logging

Logs are written to `logs/agui.log` in JSON format with automatic rotation (10MB x 5 backups).

**View logs:**
```bash
# Real-time JSON parsing
tail -f logs/agui.log | jq .

# Search by correlation ID
grep "abc123" logs/agui.log

# Filter by level
cat logs/agui.log | jq 'select(.level == "error")'

# Filter by event pattern (agent activity)
cat logs/agui.log | jq 'select(.event | startswith("agent."))'

# Filter by session
cat logs/agui.log | jq 'select(.session_id == "auth0|123")'

# Filter by ticker
cat logs/agui.log | jq 'select(.ticker == "NVDA")'
```

**Enable debug logging:**
```bash
DEBUG=true uvicorn server.main:app ...
```

Security note:
- `DEBUG=true` does not enable demo-token auth by itself.
- Demo-token auth requires `ALLOW_DEMO_TOKENS=true` and non-production `APP_ENV`.

**Log Fields:**
| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 timestamp |
| `level` | Log level (info, warning, error, debug) |
| `event` | Log message (dot-separated pattern) |
| `correlation_id` | Request correlation ID (B3 trace ID) |
| `session_id` | User session identifier |
| `ticker` | Stock symbol (when applicable) |
| `duration_ms` | Operation duration in milliseconds |
| `agent_type` | Agent type (analysis, trade, portfolio, research) |
| `component_count` | Number of A2UI components generated |

### Agent Activity Log Events

Comprehensive logging for tracking agent activity through the system.

**Agent Coordinator:**
| Event | Level | Description |
|-------|-------|-------------|
| `agent.process.started` | info | Query processing started |
| `agent.process.completed` | info | Query processing completed |
| `agent.intent.classified` | info | Intent classification result |
| `agent.intent.unknown` | warning | Could not classify intent |
| `agent.routing.specialist` | info | Routing to specialist agent |
| `agent.routing.completed` | info | Specialist agent finished |
| `agent.clarification.needed` | info | Clarification required |
| `agent.clarification.llm_generated` | debug | LLM generated clarification |

**Tool Execution:**
| Event | Level | Description |
|-------|-------|-------------|
| `tool.executing` | info | Tool execution starting |
| `tool.completed` | info | Tool execution completed |
| `tool.failed` | error | Tool execution failed |
| `tool.unknown` | warning | Unknown tool requested |

**A2UI Generation:**
| Event | Level | Description |
|-------|-------|-------------|
| `a2ui.generating` | info | A2UI generation starting |
| `a2ui.generated` | info | A2UI generation completed |
| `a2ui.failed` | error | A2UI generation failed |

**MCP Calls:**
| Event | Level | Description |
|-------|-------|-------------|
| `mcp.ib.calling` | debug | IB MCP call starting |
| `mcp.ib.success` | info | IB MCP call succeeded |
| `mcp.ib.error_response` | warning | IB MCP returned error |
| `mcp.ib.timeout` | error | IB MCP request timed out |
| `mcp.rag.calling` | debug | RAG MCP call starting |
| `mcp.rag.success` | info | RAG MCP call succeeded |
| `mcp.rag.failed` | warning | RAG MCP call failed |
| `mcp.graph.calling` | debug | Graph MCP call starting |
| `mcp.graph.success` | info | Graph MCP call succeeded |
| `mcp.graph.failed` | warning | Graph MCP call failed |

**LLM Calls:**
| Event | Level | Description |
|-------|-------|-------------|
| `llm.a2ui.generating` | info | A2UI LLM call starting |
| `llm.a2ui.generated` | info | A2UI LLM call completed |
| `llm.a2ui.json_error` | error | Invalid JSON from LLM |
| `llm.a2ui.timeout` | error | LLM request timed out |
| `llm.classify.starting` | debug | Intent classification starting |
| `llm.classify.completed` | info | Intent classification completed |
| `llm.classify.failed` | error | Intent classification failed |

**Task Manager:**
| Event | Level | Description |
|-------|-------|-------------|
| `task.submitted` | info | Task submitted to queue |
| `task.processing.started` | info | Task processing started |
| `task.processing.completed` | info | Task completed successfully |
| `task.processing.failed` | warning | Task completed with error |
| `task.processing.error` | error | Task threw exception |
| `task.progress` | debug | Task progress update |

**WebSocket:**
| Event | Level | Description |
|-------|-------|-------------|
| `ws.connected` | info | WebSocket connection opened |
| `ws.disconnected` | info | WebSocket connection closed |
| `ws.message.received` | debug | Message received |
| `ws.chat.started` | info | Chat processing started |
| `ws.chat.completed` | info | Chat processing completed |
| `ws.chat.error` | error | Chat processing failed |
| `ws.task.created` | info | Async task created |
| `ws.task.completed` | info | Async task finished |
| `ws.subscribe.started` | info | Task subscription started |
| `ws.subscribe.completed` | info | Task subscription ended |
| `ws.auth.failed` | warning | WebSocket auth failed |

**Example Log Queries:**
```bash
# Track a specific chat interaction
cat logs/agui.log | jq 'select(.session_id == "auth0|123" and .event | startswith("ws.chat"))'

# Find slow tool executions (>1s)
cat logs/agui.log | jq 'select(.event == "tool.completed" and .duration_ms > 1000)'

# Find all errors for a ticker
cat logs/agui.log | jq 'select(.ticker == "NVDA" and .level == "error")'

# Summarize intent classification
cat logs/agui.log | jq 'select(.event == "agent.intent.classified") | {intents, tickers, classify_ms}'
```

### Observability Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_LOGS_ENABLED` | `false` | Export logs to Loki via OTEL |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTEL Collector endpoint |
| `LOG_MAX_SIZE_MB` | `10` | Max log file size before rotation |
| `LOG_BACKUP_COUNT` | `5` | Number of backup log files |
| `DEBUG` | `false` | Enable debug logging |

### Tracing

Distributed traces are exported to Tempo via OTEL Collector when enabled.

**Span types:**
| Span | Description |
|------|-------------|
| `http.request.*` | FastAPI request handling |
| `mcp.call.*` | MCP server calls (trading-rag, trading-graph, ib-mcp) |
| `gen_ai.chat` | A2UI response generation (LLM) |
| `gen_ai.classify` | Intent classification (LLM) |

**LLM Spans (GenAI Semantic Conventions):**

LLM calls are traced with OpenTelemetry GenAI semantic conventions:

```
gen_ai.chat
├── gen_ai.system: openrouter
├── gen_ai.request.model: google/gemini-2.0-flash-001
├── gen_ai.usage.input_tokens: 1523
├── gen_ai.usage.output_tokens: 892
├── gen_ai.response.finish_reasons: ["stop"]
├── duration_ms: 1250.5
└── event: a2ui_generated {agent_type: "analysis", component_count: 3}
```

**GenAI Attributes:**
| Attribute | Description |
|-----------|-------------|
| `gen_ai.system` | Provider (openai, anthropic, openrouter) |
| `gen_ai.request.model` | Model name |
| `gen_ai.operation.name` | Operation (chat, classify) |
| `gen_ai.usage.input_tokens` | Input tokens |
| `gen_ai.usage.output_tokens` | Output tokens |
| `gen_ai.response.finish_reasons` | Why generation stopped |

### Metrics

Prometheus metrics collected:
- `agentui_http_request_duration` - HTTP request latency (histogram)
- `agentui_mcp_call_duration` - MCP call latency (histogram)
- `agentui_mcp_calls_total` - Total MCP calls (counter)
- `agentui_llm_call_duration` - LLM API latency (histogram)
- `agentui_llm_tokens_input` - Input tokens (counter)
- `agentui_llm_tokens_output` - Output tokens (counter)

### Correlation IDs

All requests include `correlation_id` in logs for tracing:
- Extracted from incoming `X-B3-TraceId` headers
- Generated if not provided
- Propagated to downstream MCP calls
- Included in response headers (`X-B3-TraceId`, `X-Correlation-Id`)

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
ruff check .
ruff format .
```

## Example Interactions

### Analyze a Stock

```
User: "Analyze NVDA"

→ Coordinator classifies: ANALYSIS intent
→ Routes to AnalysisAgent
→ Agent calls get_analysis(ticker="NVDA")
→ Returns A2UI with AnalysisCard, GateResult, ScenarioChart
```

### Show Portfolio

```
User: "Show my positions"

→ Coordinator classifies: PORTFOLIO intent
→ Routes to PortfolioAgent
→ Agent calls get_positions(), get_pnl()
→ Returns A2UI with PositionCard components
```

### Research

```
User: "What do you know about ZIM?"

→ Coordinator classifies: RESEARCH intent
→ Routes to ResearchAgent
→ Agent calls graph_context(ticker="ZIM"), rag_search(query="ZIM")
→ Returns A2UI with context summary
```
