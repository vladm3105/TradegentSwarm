# Tradegent Agent UI Features

## Overview

The Tradegent Agent UI provides a comprehensive trading dashboard with real-time monitoring, analytics, and automation controls.

---

## Feature Categories

### 1. Safety & Trading Controls

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| Automation Status | Current mode, pause state, circuit-breaker state | `GET /api/automation/status` |
| Trading Mode | Switch between dry-run, paper, live (with confirmation for live) | `POST /api/automation/mode` |
| Pause/Resume | Pause or resume automated trading | `POST /api/automation/pause`, `POST /api/automation/resume` |
| Circuit Breaker | View, update, and reset breaker state | `GET/PUT /api/automation/circuit-breaker/settings`, `POST /api/automation/circuit-breaker/reset` |

**Circuit Breaker Triggers:**
- Daily loss exceeds threshold
- Max consecutive losses reached
- Manual trigger via UI

### 2. Real-Time Monitoring

| Component | Description | WebSocket Channel |
|-----------|-------------|-------------------|
| Live Ticker | Real-time price updates for watchlist | `prices` |
| Live P&L | Portfolio value and unrealized P&L | `portfolio` |
| Market Status | Market hours, pre/post market | `market` |
| Service Health | IB Gateway, MCP servers status | `services` |
| Order Stream | Real-time order status updates | `orders` |

**WebSocket Endpoint:** `ws://localhost:8081/ws/stream`

### 3. Alert System

| Alert Type | Description |
|------------|-------------|
| Price Alert | Trigger when price crosses threshold |
| P&L Alert | Trigger on portfolio P&L threshold |
| Stop Alert | Monitor stop-loss levels |
| Target Alert | Monitor profit targets |

**API:** `/api/alerts/*`

### 4. Analytics Dashboard

| Component | Description | API Endpoint |
|-----------|-------------|--------------|
| Equity Curve | Cumulative P&L over time | `GET /api/analytics/equity-curve` |
| Portfolio Heatmap | Position visualization | `GET /api/analytics/position-heatmap` |
| Win Rate Dashboard | Performance by setup type | `GET /api/analytics/win-rate-by-setup` |
| Position Sizer | Risk-based position calculator | `POST /api/analytics/position-size` |
| Daily Summary | Daily trading statistics | `GET /api/analytics/daily-summary` |

### 5. Order Management

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| Open Orders | View and manage active orders | `GET /api/orders/open` |
| Bracket Orders | Entry with stop-loss and take-profit | `POST /api/orders/bracket` |
| Cancel Order | Cancel pending orders | `POST /api/orders/cancel/{id}` |
| Modify Stop | Adjust stop-loss price | `POST /api/orders/modify-stop` |

### 6. Schedule Management

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| List Schedules | View configured schedules | `GET /api/schedules` |
| Create Schedule | Add a new scheduled task | `POST /api/schedules` |
| Update Schedule | Edit schedule metadata and timing | `PATCH /api/schedules/{id}` |
| Enable Schedule | Enable a scheduled task | `POST /api/schedules/{id}/enable` |
| Disable Schedule | Disable a scheduled task | `POST /api/schedules/{id}/disable` |
| Run Now | Manually trigger scheduled task | `POST /api/schedules/{id}/run` |
| Schedule History | View recent run history by schedule | `GET /api/schedules/history/{id}` |

**UX updates:**
- Toggle actions now show explicit `Enable`/`Disable` buttons.
- Success/failure toast notifications are shown after each toggle.

**Live Execution Display (March 2026):**

When a schedule is running, the UI shows three additional fields sourced from `nexus.run_history` and `nexus.service_status`:

| Field | Source | Description |
|-------|--------|-------------|
| `active_task_label` | `service_status.current_task` (or `task_type` fallback) | Current task in progress (e.g. `schedule 2 watchlist 22/27 OWLT`) |
| `active_started_at` | `run_history.started_at` | When the current run started |
| `active_heartbeat_at` | `service_status.last_heartbeat` | Last heartbeat timestamp from the daemon |

The "Next" field shows `after current run` instead of a past-relative time while the schedule status is `running`. This is computed client-side in `getNextRunLabel()` (`schedule-manager.tsx`).

**Backend pattern:** `schedules_repository.py` uses a `LATERAL JOIN` on `nexus.run_history` (to detect `status='running'` rows) combined with a `LEFT JOIN` on `nexus.service_status id=1` to pull `current_task` and `last_heartbeat`.

### 6.1 Watchlist Entry Management

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| Create Watchlist Entry | Add an entry directly from the Watchlist page form | `POST /api/watchlist` |
| Last Analysis Date | Show most recent analysis timestamp per entry | `GET /api/watchlist/list` |
| Entry Detail | View enriched watchlist entry details | `GET /api/watchlist/detail/{id}` |

### 6.2 Analysis and Scanner Display

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| Analysis Timestamp Precision | Analysis table displays date and time for each report row | `GET /api/analyses/list` |
| Scanner Result Identity Normalization | Scanner results always include a non-null `scanner_code` resolved from run metadata | `GET /api/scanners/results` |
| Open-Trade Gate Column | The gate result column in `/analysis` is labelled **"Open-Trade Gate"** (previously "Gate") to clarify it represents the 4-condition threshold (EV >5%, Confidence >60%, R:R >2:1, setup quality) that must pass before opening a trade | `GET /api/analyses/list` |

### 7. Dashboard Customization

| Feature | Description | Storage |
|---------|-------------|---------|
| Widget Manager | Show/hide dashboard widgets | localStorage |
| Widget Ordering | Drag to reorder widgets | localStorage |

### Backend API Architecture

As of March 2026, the Agent UI API backend follows a strict layering model:

```
Route -> Service -> Repository -> Database
```

#### Layer responsibilities

| Layer | Responsibility |
|-------|----------------|
| Routes (`server/routes/`) | Request/response contracts, dependency injection, delegation |
| Services (`server/services/`) | Validation, business rules, orchestration, response shaping |
| Repositories (`server/repositories/`) | SQL and persistence access only |

#### Migration status

- Core API slices have been migrated to the layered pattern:
  - admin, alerts, auth, automation, notifications, scanners, sessions, settings, trades, users, watchlist
- Route-level direct SQL access was removed from migrated routes.

#### Hardening updates (March 11, 2026)

- GDPR delete path: all-or-nothing transactional execution.
- Session message persistence: explicit JSONB-safe adaptation for `a2ui` payloads.
- Settings actions: no fallback audit-user assignment when principal resolution fails.

---

## 8. Analysis Display System

The frontend renders stock and earnings analyses from `yaml_content` (JSONB) stored in `nexus.kb_stock_analyses` and `nexus.kb_earnings_analyses`. Because skill templates evolve, the display layer uses a **version-specific parser registry** so each schema version is handled by exactly one dedicated parser.

### Parser Registry

**Location:** `frontend/lib/parsers/`

| File | Purpose |
|------|---------|
| `registry.ts` | Dispatch — resolves `(type, version)` → correct parser |
| `types.ts` | `AnalysisParser` interface |
| `utils.ts` | Shared helpers: `get()`, `normalizeGateResult()`, `normalizeRecommendation()`, transform functions |
| `stock/v2.6.ts` | Stock schema v2.6 |
| `stock/v2.7.ts` | Stock schema v2.7 (adds alert `tag` + `derivation`) |
| `earnings/v2.3.ts` | Earnings schema v2.3 (phase1-7 structure) |
| `earnings/v2.5.ts` | Earnings schema v2.5 (flat, `decision.*`, no scoring) |
| `earnings/v2.6.ts` | Earnings schema v2.6 (flat + `scoring` section) |

**Entry point:** `lib/analysis-transformer.ts` re-exports `parseAnalysis` and `hasFullAnalysisData` from the registry under the original names — all existing call-sites remain unchanged.

### Version Resolution

The registry resolves the parser in this order:

```
response.schema_version  →  extract major.minor
  or yaml._meta.version

response.analysis_type   →  "stock-analysis" | "earnings-analysis"
  or yaml._meta.type
  or yaml.analysis_type

Registry key: "<type>:<major.minor>"   e.g. "stock-analysis:2.7"
```

If no exact match is found, the closest fallback for that type is used with a console warning.

### YAML Field Paths Per Version

**Stock analyses:**

| Field | v2.6 path | v2.7 path |
|-------|-----------|-----------|
| recommendation | `yaml.recommendation` | `yaml.recommendation` |
| confidence | `yaml.confidence.level` | `yaml.confidence.level` |
| gate result | `yaml.do_nothing_gate.gate_result` | `yaml.do_nothing_gate.gate_result` |
| alert tag | _(absent)_ | `yaml.alert_levels.price_alerts[].tag` |

**Earnings analyses:**

| Field | v2.3 path | v2.5 path | v2.6 path |
|-------|-----------|-----------|----------|
| recommendation | derived from `phase7_decision.recommendation.direction` + gate | `decision.recommendation` | `decision.recommendation` |
| confidence | `phase7_decision.do_nothing_gate.confidence_above_60pct.actual` | `do_nothing_gate.confidence_actual` | `do_nothing_gate.confidence_actual` |
| gate result | `phase7_decision.do_nothing_gate.gate_result` (`proceed_with_caution` → MARGINAL) | `do_nothing_gate.gate_result` | `do_nothing_gate.gate_result` |
| scoring | _(absent)_ | _(absent)_ | `scoring.*_score` |

### Adding a New Parser Version

1. Create `lib/parsers/stock/vX.Y.ts` (or `earnings/vX.Y.ts`) exporting a function matching `AnalysisParser`.
2. Add one line to `lib/parsers/registry.ts`:
   ```ts
   REGISTRY.set('stock-analysis:X.Y', stockParserVXY);
   ```
3. No other files need to change.
| Layout Persistence | Save dashboard configuration | localStorage |

**Available Widgets:**
- live-pnl, live-ticker, market-status, service-health
- trading-controls, open-orders, bracket-order
- equity-curve, portfolio-heatmap, win-rate, position-sizer
- schedule-manager, notification-center, daily-summary

---

## API Authentication

All API endpoints require JWT authentication:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8081/api/...
```

**Demo token mode (development/test only):**
```bash
curl -H "Authorization: Bearer demo-token-1" http://localhost:8081/api/...
```

Requirements:
- `ALLOW_DEMO_TOKENS=true`
- `APP_ENV=development` or `APP_ENV=test`

---

## Frontend Components

| Component | File | Description |
|-----------|------|-------------|
| TradingControls | `trading-controls.tsx` | Trading mode switches |
| NotificationCenter | `notification-center.tsx` | Alert notifications |
| LivePnL | `live-pnl.tsx` | Real-time portfolio value |
| LiveTicker | `live-ticker.tsx` | Price streaming |
| MarketStatus | `market-status.tsx` | Market hours display |
| ServiceHealth | `service-health.tsx` | Backend service status |
| EquityCurve | `equity-curve.tsx` | P&L chart |
| PortfolioHeatmap | `portfolio-heatmap.tsx` | Position visualization |
| WinRateDashboard | `win-rate-dashboard.tsx` | Performance metrics |
| PositionSizer | `position-sizer.tsx` | Risk calculator |
| BracketOrderForm | `bracket-order-form.tsx` | Order entry |
| OpenOrders | `open-orders.tsx` | Order management |
| ScheduleManager | `schedule-manager.tsx` | Task scheduling |
| DailySummary | `daily-summary.tsx` | Daily statistics |
| WidgetManager | `widget-manager.tsx` | Dashboard customization |
| DashboardLayout | `dashboard-layout.tsx` | Responsive grid layout |

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `nexus.alerts` | Price and P&L alerts |
| `nexus.notifications` | User notifications |
| `nexus.settings` | Trading mode, circuit breaker config |
| `nexus.order_history` | Order tracking |
| `nexus.schedules` | Scheduled tasks |

---

## Configuration

**Environment Variables:**
```bash
# Backend
AGUI_HOST=0.0.0.0
AGUI_PORT=8081
DEBUG=false
APP_ENV=development
ALLOW_DEMO_TOKENS=false

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8081
NEXT_PUBLIC_WS_URL=ws://localhost:8081
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.2 | 2026-03-13 | Added analysis timestamp precision note, documented scanner result `scanner_code` normalization, and updated API feature mapping |
| 1.1 | 2026-03-11 | Documented Route -> Service -> Repository backend architecture, corrected automation endpoint references, and recorded post-migration hardening updates |
| 1.0 | 2026-03-05 | Initial IPLAN-002 implementation |
