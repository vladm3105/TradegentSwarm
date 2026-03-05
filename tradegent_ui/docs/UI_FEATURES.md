# Tradegent Agent UI Features

## Overview

The Tradegent Agent UI provides a comprehensive trading dashboard with real-time monitoring, analytics, and automation controls.

---

## Feature Categories

### 1. Safety & Trading Controls

| Feature | Description | API Endpoint |
|---------|-------------|--------------|
| Trading Mode | Switch between dry-run, paper, analysis-only | `POST /api/automation/trading-mode` |
| Circuit Breaker | Auto-halt trading on loss thresholds | `GET/POST /api/automation/circuit-breaker` |
| Auto-Execute Toggle | Enable/disable automated order placement | `POST /api/automation/auto-execute` |
| Max Daily Loss | Configure daily loss limit | `POST /api/automation/settings` |

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
| Toggle Schedule | Enable/disable scheduled tasks | `PATCH /api/schedules/{id}` |
| Run Now | Manually trigger scheduled task | `POST /api/schedules/{id}/run` |

### 7. Dashboard Customization

| Feature | Description | Storage |
|---------|-------------|---------|
| Widget Manager | Show/hide dashboard widgets | localStorage |
| Widget Ordering | Drag to reorder widgets | localStorage |
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

**Demo mode (DEBUG=true):**
```bash
curl -H "Authorization: Bearer demo-token-1" http://localhost:8081/api/...
```

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
DEBUG=true  # Enable demo tokens

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8081
NEXT_PUBLIC_WS_URL=ws://localhost:8081
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-05 | Initial IPLAN-002 implementation |
