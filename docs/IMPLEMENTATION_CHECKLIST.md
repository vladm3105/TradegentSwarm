# Unified Messages Implementation Checklist

**Status**: Core infrastructure implemented ✅ | Phase 1 (Real-time Metrics) scheduled

## Overview

Tradegent has implemented a unified `TradegentMessage` envelope for all client-server communication. This document tracks the rollout across the existing codebase.

## Completed ✅

### Core Infrastructure
- ✅ TypeScript message types (`tradegent_ui/frontend/lib/messages.ts`)
- ✅ Python message models (`tradegent_ui/server/messages.py`)
- ✅ Unified frontend client (`tradegent_ui/frontend/lib/unified-client.ts`)
- ✅ FastAPI response wrappers (`tradegent_ui/server/response.py`)
- ✅ Documentation (`docs/architecture/UNIFIED_MESSAGES.md`)
- ✅ Quick reference (`docs/COMMUNICATION_GUIDE.md`)

### Comments & Migration Guides
- ✅ Legacy API client notice (tradegent_ui/frontend/lib/api.ts)
- ✅ Schedule routes migration note (tradegent_ui/server/routes/schedules.py)
- ✅ WebSocket protocol documentation (tradegent_ui/server/websocket/price_stream.py)
- ✅ README section on unified architecture

## Phase 1: Real-Time Dashboard (🔄 In Progress)

### Frontend Hooks
- [ ] Create `useDashboardMetrics()` hook
  - Subscribe to `subscribe_metrics` channel
  - Handle daily_pnl, win_rate, trade_duration updates
  - Real-time update of dashboard cards
  - File: `tradegent_ui/frontend/hooks/use-dashboard-metrics.ts`

- [ ] Create `useScannerAlerts()` hook
  - Subscribe to `subscribe_alerts` channel
  - Handle alert events with timestamp, score, details
  - Toast notification on high-score alerts
  - File: `tradegent_ui/frontend/hooks/use-scanner-alerts.ts`

- [ ] Update `use-dashboard.ts`
  - Remove polling-based metrics queries (refetchInterval)
  - Replace with WS subscriptions where applicable
  - Keep REST queries for historical data

### Backend WebSocket Handler
- [ ] Update `/ws/stream` endpoint to support `subscribe_metrics`
  - Calculate daily P&L from trades
  - Calculate win rate (wins / total trades)
  - Stream updates every 5 seconds during active trading
  - Cache last known values for new subscribers

- [ ] Update `/ws/stream` endpoint to support `subscribe_alerts`
  - Connect to scanner results queue
  - Stream high-score alerts (>7.5) immediately
  - Include scan details, timestamp, symbol

### Dashboard Screen
- [ ] Update dashboard component to use new hooks
  - Replace polling UI spinners with live update indicators
  - Add connection status indicator (WS connected/disconnected)
  - Add alert notification center with recent alerts

## Phase 2: Schedule Notifications (Not Started)

### Backend WebSocket Handler
- [ ] Add `subscribe_schedule_events` channel to `/ws/stream`
  - Events: schedule_started, schedule_completed, schedule_failed
  - Payload: schedule_id, event, status, timestamp

### Frontend Hook
- [ ] Create `useScheduleEvents()` hook
  - Subscribe to schedule events
  - Update schedule list in real-time
  - Toast notifications for failed schedules

### Settings → Schedules Tab
- [ ] Update ScheduleManager component
  - Replace poll-based history with push notifications
  - Show "running now" indicator for active schedules
  - Auto-refresh history on completion event

## Phase 3: Audit & Retrofit (Not Started)

### Route Migration
- [ ] Identifies all existing REST routes
  - [ ] tradegent_ui/server/routes/schedules.py
  - [ ] tradegent_ui/server/routes/trades.py
  - [ ] tradegent_ui/server/routes/watchlist.py
  - [ ] tradegent_ui/server/routes/settings.py
  - [ ] tradegent_ui/server/routes/orders.py
  - [ ] tradegent_ui/server/routes/alerts.py
  - [ ] tradegent_ui/server/routes/analytics.py
  - [ ] (add others as needed)

- [ ] Wrap all responses with `wrap_response()` or `error_to_response()`
  - Use consistent action names from `TradegentActions`
  - Include request_id in response for correlation
  - Standardize error codes across routes

### WebSocket Handler Retrofit
- [ ] Update `tradegent_ui/server/websocket/portfolio_stream.py`
  - Wrap messages in TradegentEvent envelope
  - Include request_id for subscription correlation
  - Use unified error responses

- [ ] Update `tradegent_ui/server/websocket/order_stream.py`
  - Same as portfolio_stream

## Phase 4: DevTools & Monitoring (Future)

### Developer Tools
- [ ] Browser DevTools extension
  - Inspect all TradegentMessages in real-time
  - Filter by action, type, request_id
  - Show request-response waterfall
  - Export trace for debugging

- [ ] Unified Message Inspector
  - CLI tool to replay request-response sequences
  - Validate messages against schema
  - Lint for common mistakes

### Metrics & Monitoring
- [ ] Prometheus metrics
  - `tradegent_messages_total` (by action, type)
  - `tradegent_message_latency` (REST vs WS)
  - `tradegent_errors_total` (by code)

- [ ] Correlation-based logging
  - All logs for a request_id grouped together
  - Trace request from client through server
  - Identify async processing delays

## Migration Patterns

### Pattern 1: Traditional REST Route → Unified Response

```python
# BEFORE
@router.patch("/schedules/{id}")
async def update_schedule(id: int, data: dict):
    return {"schedule_id": id, "enabled": data.enabled}

# AFTER
from ..response import wrap_response, error_to_response

@router.patch("/schedules/{id}")
async def update_schedule(id: int, data: dict, request: TradegentRequest):
    if id <= 0:
        return error_to_response(
            action="patch_schedule",
            code="VALIDATION_ERROR",
            message="ID must be positive",
            request_id=request.request_id
        )
    result = {"schedule_id": id, "enabled": data.enabled}
    return wrap_response(result, action="patch_schedule", request_id=request.request_id)
```

### Pattern 2: Polling Hook → Unified Subscription

```typescript
// BEFORE (polling every 30s)
const { data: prices } = useQuery({
  queryKey: ['prices'],
  queryFn: fetch('/api/prices'),
  refetchInterval: 30000
});

// AFTER (real-time push)
const [prices, setPrices] = useState({});

useEffect(() => {
  const unsubscribe = client.subscribe(
    'subscribe_prices',
    {},
    (event) => {
      setPrices(p => ({ ...p, [event.payload.ticker]: event.payload }));
    }
  );
  return unsubscribe;
}, []);
```

## Action Registry

All supported actions should be documented in `TradegentActions` (Python) and `TRADEGENT_ACTIONS` (TypeScript):

| Action | Type | Endpoint | Status |
|--------|------|----------|--------|
| get_schedules | request | GET /api/schedules | ⚠️ Needs wrapping |
| patch_schedule | request | PATCH /api/schedules/{id} | ⚠️ Needs wrapping |
| run_schedule_now | request | POST /api/schedules/{id}/run | ⚠️ Needs wrapping |
| get_schedule_history | request | GET /api/schedules/{id}/history | ⚠️ Needs wrapping |
| subscribe_prices | subscription | /ws/stream | ✅ Ready |
| subscribe_portfolio | subscription | /ws/stream | ⚠️ Needs update |
| subscribe_orders | subscription | /ws/stream | ⚠️ Needs update |
| subscribe_metrics | subscription | /ws/stream | ❌ Not started |
| subscribe_alerts | subscription | /ws/stream | ❌ Not started |
| subscribe_schedule_events | subscription | /ws/stream | ❌ Not started |

(Add more as routes are created)

## Testing

### Unit Tests
- [ ] `test_messages.py` - Message creation and serialization
- [ ] `test_response.py` - Response wrapper functions
- [ ] `test_unified_client.ts` - Client request/subscribe methods

### Integration Tests
- [ ] REST request-response cycle
- [ ] WebSocket subscription and event streaming
- [ ] Error response handling
- [ ] Connection recovery/reconnect

### E2E Tests
- [ ] Full dashboard update via metrics subscription
- [ ] Alert notification flow
- [ ] Trade execution and event push

## Rollout Timeline

| Phase | Timeline | Owner | Status |
|-------|----------|-------|--------|
| Core Infrastructure | ✅ Complete | Both | Done |
| Phase 1 (Metrics/Alerts) | Week 1-2 | Frontend + Backend | In Progress |
| Phase 2 (Schedules) | Week 2-3 | Frontend + Backend | Not Started |
| Phase 3 (Retrofit) | Week 3-4 | Both | Not Started |
| Phase 4 (DevTools) | Week 5+ | DevOps/Infra | Future |

## Notes

- **Backward Compatibility**: Legacy API client (lib/api.ts) remains functional. New code should use unified-client.
- **Gradual Migration**: Routes don't need to be migrated atomically. Mix old and new code during transition.
- **Error Codes**: When migrating, use standard error codes from TradegentError definition. Don't invent new ones.
- **Request IDs**: All responses should echo the request_id from the request for correlation.
- **Timestamps**: All messages should include timestamp in milliseconds since epoch.

## Questions?

See [Communication Guide](../COMMUNICATION_GUIDE.md) or [Unified Messages Architecture](../architecture/UNIFIED_MESSAGES.md).
