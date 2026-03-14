# Tradegent UI Frontend

Modern Next.js frontend for the Tradegent trading platform, featuring a real-time agent chat, trading analytics, and portfolio management.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14 - Port 3001)                │
├─────────────────────────────────────────────────────────────────────┤
│  Layout                                                             │
│  ├── Sidebar (navigation, collapsible)                              │
│  ├── Header (search, WebSocket status, theme, user menu)            │
│  └── Main Content (page routes)                                     │
│       └── Chat Panel (collapsible, available on all pages)          │
├─────────────────────────────────────────────────────────────────────┤
│  State Management                                                   │
│  ├── Zustand (UI state, chat messages, connection state)            │
│  ├── TanStack Query (server state, API caching)                     │
│  └── NextAuth.js (authentication, session)                          │
├─────────────────────────────────────────────────────────────────────┤
│  Communication                                                      │
│  ├── REST API → FastAPI backend (/api/*)                            │
│  └── WebSocket → Real-time agent chat (/ws/agent)                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript 5.7
- **Styling**: Tailwind CSS 3.4
- **UI Components**: Radix UI primitives
- **State Management**: Zustand
- **Data Fetching**: TanStack Query
- **Charts**: Recharts
- **Authentication**: NextAuth.js v5
- **Testing**: Vitest (unit), Playwright (E2E)

## Quick Start

### Prerequisites

- Node.js 20+
- npm 10+
- Backend server running on port 8081

### Development

```bash
# Install dependencies
npm install

# Start development server (port 3001)
npm run dev

# Open http://debian:3001 (or http://localhost:3001)
```

Note:
- Dev and start scripts bind to `0.0.0.0` by default.
- In multi-host setups, use the same DNS host for login/callback flows (for example, `debian`) to avoid cookie-domain mismatches.

### Built-in Accounts

| Account | Email | Password |
|---------|-------|----------|
| Admin (Superuser) | admin@tradegent.local | TradegentAdmin2024! |
| Demo | demo@tradegent.local | demo123 |

> **Note:** Authentication is always enabled. The admin account is similar to PostgreSQL's `postgres` user.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server on port 3001 |
| `npm run build` | Build for production |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |
| `npm run typecheck` | Run TypeScript type checking |
| `npm run test` | Run Vitest in watch mode |
| `npm run test:run` | Run Vitest once |
| `npm run test:coverage` | Run Vitest with coverage |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run test:e2e:ui` | Run Playwright with UI |

## Project Structure

```
frontend/
├── app/                    # Next.js App Router
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Dashboard (/)
│   ├── login/              # Login page
│   ├── api/                # API routes
│   │   ├── auth/           # NextAuth handlers
│   │   └── orchestrator/   # Backend proxy
│   └── (routes)/           # Protected routes
│       ├── analysis/       # Analysis management
│       ├── trades/         # Trade journal
│       ├── watchlist/      # Watchlist tracking
│       ├── charts/         # Performance charts
│       ├── scanner/        # Market scanners
│       ├── schedules/      # Schedule management + history
│       ├── knowledge/      # Knowledge base
│       └── settings/       # User settings
├── components/
│   ├── ui/                 # Base UI components (Radix)
│   ├── charts/             # Recharts components
│   ├── tradegent-components.tsx  # A2UI trading components
│   ├── a2ui-renderer.tsx   # A2UI component renderer
│   ├── chat-panel.tsx      # Agent chat panel
│   ├── sidebar.tsx         # Navigation sidebar
│   ├── header.tsx          # Top header bar
│   └── error-boundary.tsx  # Error handling
├── hooks/                  # Custom React hooks
├── lib/                    # Utilities and clients
│   ├── api.ts              # API client
│   ├── auth.ts             # NextAuth configuration
│   ├── websocket.ts        # WebSocket client
│   └── utils.ts            # Helper functions
├── stores/                 # Zustand stores
├── types/                  # TypeScript definitions
├── tests/                  # Vitest unit tests
└── e2e/                    # Playwright E2E tests
```

## Configuration

### Environment Variables

Create `.env.local` from `.env.local.example`:

```bash
# API Connection
NEXT_PUBLIC_API_URL=http://localhost:8081
NEXT_PUBLIC_WS_URL=ws://localhost:8081/ws/agent

# Authentication (generate secret with: openssl rand -base64 32)
AUTH_SECRET=<your-secret>
AUTH_TRUST_HOST=true

# Admin User (superuser - like PostgreSQL's postgres)
ADMIN_EMAIL=admin@tradegent.local
ADMIN_PASSWORD=TradegentAdmin2024!
ADMIN_NAME=System Administrator

# Demo Account (optional)
DEMO_EMAIL=demo@tradegent.local
DEMO_PASSWORD=demo123

# Auth0 (optional - leave empty for built-in auth)
NEXT_PUBLIC_AUTH0_CONFIGURED=false
```

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Portfolio overview, P&L summary, quick actions |
| `/analysis` | Analysis | View and manage stock analyses with date+time timestamps |
| `/trades` | Trade Journal | Trade history and journal entries |
| `/watchlist` | Watchlist | Active watchlist with triggers |
| `/charts` | Charts | Performance analytics and Grafana |
| `/scanner` | Scanner | Market scanners, run history, and opportunities |
| `/schedules` | Schedules | Create/edit schedules, enable/disable, and run now |
| `/schedules/history` | Schedule History | View recent execution history by schedule |
| `/knowledge` | Knowledge | RAG search and knowledge base |
| `/settings` | Settings | User preferences and system config |
| `/login` | Login | Authentication page |

Notes:
- The Analysis table Date column renders full timestamp (date and time) to distinguish multiple reports created on the same day.
- Scanner result rendering expects a non-null `scanner_code`; backend responses now normalize this from stored run metadata.

## A2UI Components

Trading-specific components rendered by the agent chat:

| Component | Purpose |
|-----------|---------|
| `AnalysisCard` | Stock analysis with recommendation |
| `PositionCard` | Portfolio position with P&L |
| `TradeCard` | Trade journal entry |
| `WatchlistCard` | Watchlist entry with triggers |
| `GateResult` | Do Nothing Gate indicators |
| `ScenarioChart` | Bull/base/bear scenario bars |
| `MetricsRow` | Key-value metrics display |
| `ErrorCard` | Error display with retry |
| `LoadingCard` | Loading state indicator |

## Keyboard Shortcuts

### Global Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` / `Cmd+K` | Focus search |
| `Ctrl+/` | Toggle chat panel |
| `Ctrl+B` | Toggle sidebar |
| `Escape` | Close panels/modals |

### Navigation Shortcuts

| Shortcut | Page |
|----------|------|
| `Alt+1` | Dashboard |
| `Alt+2` | Analysis |
| `Alt+3` | Trades |
| `Alt+4` | Watchlist |
| `Alt+5` | Charts |
| `Alt+6` | Scanner |
| `Alt+7` | Schedules |
| `Alt+8` | Schedule History |
| `Alt+9` | Knowledge |
| `Alt+0` | Settings |

## Docker

### Build and Run

```bash
# Build image
docker build -t tradegent-frontend .

# Run container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://backend:8081 \
  tradegent-frontend
```

### Docker Compose

From the parent directory:

```bash
docker compose up agui-frontend
```

## Logging

The frontend includes a structured logging system for debugging and observability.

### Log Levels

| Level | Usage |
|-------|-------|
| `debug` | Detailed debugging info (disabled by default) |
| `info` | General information |
| `warn` | Warnings and non-critical issues |
| `error` | Errors and failures |

### Enable Debug Logging

```javascript
// In browser console
window.__logger.enableDebug()

// Or set environment variable
NEXT_PUBLIC_DEBUG=true
```

### Log Format

```
[2026-03-01T14:30:00.123Z] [INFO][api] API GET /api/dashboard/stats { status: 200, duration: 45 }
```

### Log Storage

- Last 100 log entries stored in `sessionStorage` under key `app_logs`
- Access via browser console: `window.__logger.getLogs()`
- Clear logs: `window.__logger.clearLogs()`

### Component Loggers

```typescript
import { createLogger } from '@/lib/logger';

const log = createLogger('my-component');
log.info('Something happened', { key: 'value' });
log.api('POST', '/api/chat', { messageId: 'abc' });
log.ws('connected', { sessionId: 'xyz' });
```

## WebSocket Connection States

The WebSocket status indicator in the header shows real-time connection state:

| State | Icon | Color | Description |
|-------|------|-------|-------------|
| `connected` | Wifi | Green | Connected to backend |
| `connecting` | Loader (spin) | Yellow | Initial connection in progress |
| `reconnecting` | RefreshCw (spin) | Yellow | Reconnecting after disconnect |
| `disconnected` | WifiOff | Red | Not connected |

### Reconnection Behavior

- Automatic reconnection with exponential backoff
- Max 10 reconnection attempts
- Initial delay: 1 second, max delay: 30 seconds
- Jitter added to prevent thundering herd
- Message queue preserved during reconnection

## Error Boundaries

The frontend uses granular error boundaries to prevent cascading failures:

| Boundary | Coverage | Fallback |
|----------|----------|----------|
| `PageErrorBoundary` | Full page | "Something went wrong" with reload |
| `ChatErrorBoundary` | Chat panel | "Chat error" with reconnect |
| `ChartErrorBoundary` | Individual charts | "Unable to load chart" |
| `WidgetErrorBoundary` | Dashboard widgets | Card with error message |

### Usage

```tsx
import { ChartErrorBoundary } from '@/components/error-boundary';

<ChartErrorBoundary>
  <PnLChart data={data} />
</ChartErrorBoundary>
```

## State Management

### Zustand Stores

| Store | Purpose | Key State |
|-------|---------|-----------|
| `useUIStore` | UI state | sidebar, chat panel, theme |
| `useChatStore` | Chat state | messages, connection, streaming |

### TanStack Query

Server state managed with React Query:

```typescript
// Queries use staleTime to reduce refetches
const { data } = useQuery({
  queryKey: ['dashboard', 'stats'],
  queryFn: api.dashboard.stats,
  staleTime: 30_000, // 30 seconds
});
```

### Session State

NextAuth.js manages authentication:

```typescript
import { useSession } from 'next-auth/react';

const { data: session, status } = useSession();
// status: 'loading' | 'authenticated' | 'unauthenticated'
```

## Testing

### Unit Tests (Vitest)

```bash
# Run all tests
npm run test:run

# Run with coverage
npm run test:coverage

# Watch mode
npm run test
```

### E2E Tests (Playwright)

```bash
# Install browsers (first time)
npx playwright install

# Run tests
npm run test:e2e

# Run with UI
npm run test:e2e:ui
```

## Backend Integration

The frontend connects to the FastAPI backend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/chat` | POST | Send chat message |
| `/api/task/{id}` | GET | Get task status |
| `/api/dashboard/stats` | GET | Dashboard statistics |
| `/api/dashboard/pnl` | GET | P&L data |
| `/api/dashboard/performance` | GET | Ticker performance |
| `/api/dashboard/analysis-quality` | GET | Analysis quality metrics |
| `/api/dashboard/watchlist-summary` | GET | Watchlist summary |
| `/ws/agent` | WS | Real-time agent communication |

> **Note:** Dashboard endpoints return real data from PostgreSQL BI views. If you see mock data (e.g., total_pnl=12547.82), ensure the BI views are applied:
> ```bash
> docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent < tradegent/db/bi_views.sql
> ```

## Trading Theme

- **Gain color**: `#22c55e` (green-500)
- **Loss color**: `#ef4444` (red-500)
- **Warning**: `#f59e0b` (amber-500)

Recommendation badges:
- **BUY**: Green
- **WATCH**: Blue
- **NO_POSITION**: Gray
- **AVOID**: Red

Gate results:
- **PASS**: Green (4/4 criteria)
- **MARGINAL**: Yellow (3/4 criteria)
- **FAIL**: Red (<3 criteria)

## Development

### Debug Tools

```javascript
// Browser console commands
window.__logger.enableDebug()    // Enable debug logging
window.__logger.getLogs()        // Get recent logs
window.__logger.clearLogs()      // Clear log storage

// React Query Devtools
// Visible in bottom-right corner in development mode
```

### Common Issues

| Issue | Solution |
|-------|----------|
| WebSocket "Disconnected" | Start backend: `uvicorn server.main:app --port 8081` |
| Login fails | Check `AUTH_SECRET` and `ADMIN_*` vars in `.env.local` |
| Backend won't start | Verify `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `JWT_SECRET` in `server/.env` |
| Charts not loading | Verify backend dashboard endpoints are working |
| Dashboard shows mock data | Apply BI views: `psql < tradegent/db/bi_views.sql` |
| Style issues | Clear `.next` cache: `rm -rf .next && npm run dev` |

### File Watch Limits

If you see "ENOSPC: System limit for file watchers reached":

```bash
# Increase inotify limit
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## License

MIT
