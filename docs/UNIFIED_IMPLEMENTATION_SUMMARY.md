# Unified Communication Architecture - Implementation Summary

**Status**: ✅ Core infrastructure complete, ready for Phase 1 (metrics/alerts)

## What Was Implemented

### 1. Unified Message Protocol ✅

All client-server communication now uses a single `TradegentMessage` envelope:

```typescript
interface TradegentMessage {
  type: 'request' | 'response' | 'subscription' | 'event' | 'error';
  action: string;           // 'patch_schedule', 'subscribe_prices', etc.
  request_id?: string;      // UUID for correlation
  payload?: any;            // Action-specific data
  timestamp?: number;       // Milliseconds since epoch
  error?: {code, message, details};
}
```

**Benefits:**
- ✅ Single error format across REST and WebSocket
- ✅ Request-response correlation for debugging
- ✅ Standard error codes and handling
- ✅ Unified logging with request_id tracking
- ✅ Type-safe frontend/backend contract

### 2. Frontend Infrastructure ✅

#### `tradegent_ui/frontend/lib/messages.ts` (350 lines)
- `TradegentMessage` interface with all variants
- Helper functions: `createRequest()`, `createSubscription()`, `createError()`
- Request ID generation
- Action constants matching backend
- Complete JSDoc documentation

#### `tradegent_ui/frontend/lib/unified-client.ts` (450+ lines)
- `TradegentClient` facade for unified REST + WebSocket
  - Transparent transport routing (REST for request, WS for subscription)
  - Automatic connection management for WebSocket
  - Exponential backoff reconnection
  - Per-subscription listener registration
- `TradegentRESTClient` class (stateless HTTP POST)
- `TradegentWSClient` class (stateful with reconnection)
- `TradegentClientError` exception type
- Factory function: `createTradegentClient()`
- Complete JSDoc with usage examples

**Usage:**
```typescript
const client = createTradegentClient(getAuthToken);

// Request-response
const result = await client.request('patch_schedule', {schedule_id: 1});

// Push subscription
const unsubscribe = client.subscribe('subscribe_prices', {tickers: ['NVDA']}, onEvent);
```

### 3. Backend Infrastructure ✅

#### `tradegent_ui/server/messages.py` (340 lines)
- `TradegentMessage` Pydantic model with discriminated union variants
- `TradegentError` model for error details
- Helper functions: `create_response()`, `create_event()`, `create_error()`
- Request ID generation
- `TradegentActions` class with standardized action names
- Complete docstrings with examples
- Supports JSON serialization for WebSocket frames

#### `tradegent_ui/server/response.py` (180 lines)
- `wrap_response()` factory for REST responses
- `error_to_response()` for error handling
- `http_exception_to_response()` for converting FastAPI exceptions
- Plug-and-play integration with existing FastAPI routes

**Usage:**
```python
from tradegent_ui.server.response import wrap_response, error_to_response

@router.post("/api")
async def unified_api(request: TradegentRequest):
    if validation_failed:
        return error_to_response(
            action="patch_schedule",
            code="VALIDATION_ERROR",
            message="...",
            request_id=request.request_id
        )
    return wrap_response(result, action="patch_schedule", request_id=request.request_id)
```

### 4. Documentation ✅

#### [docs/architecture/UNIFIED_MESSAGES.md](docs/architecture/UNIFIED_MESSAGES.md) (500+ lines)
- Complete architecture diagram
- All four message types explained (request/response, subscription/event, error)
- Transport selection guide (REST vs WebSocket)
- Protocol specifications with ABNF examples
- Implementation patterns for frontend and backend
- Request correlation via request_id
- Standard error codes table
- Migration path (4 phases)
- Future roadmap (DevTools, monitoring)

#### [docs/COMMUNICATION_GUIDE.md](docs/COMMUNICATION_GUIDE.md) (350 lines)
- Quick reference for developers
- Setup instructions
- Common actions registry
- Error handling patterns
- Transport selection quick table
- Debugging tips
- Code snippets for common patterns
- All error codes with meanings

#### [docs/CLIENT_USAGE_EXAMPLES.md](docs/CLIENT_USAGE_EXAMPLES.md) (650+ lines)
- 6 complete real-world scenarios with code:
  1. Update schedule settings
  2. Real-time price feed (with connection status)
  3. Scanner alerts with fallback to polling
  4. Form submission with field-level errors
  5. Request retry with exponential backoff
  6. Cascading requests (fetch schedule + history)
- Patterns for:
  - Error handling with error code switching
  - React Query integration
  - Subscription hooks
  - Timeout handling
  - Correlation ID tracking

#### [docs/IMPLEMENTATION_CHECKLIST.md](docs/IMPLEMENTATION_CHECKLIST.md) (400+ lines)
- What's completed ✅
- 4 implementation phases with timelines
- Phase 1: Real-time metrics + alerts (in progress)
- Phase 2: Schedule notifications
- Phase 3: Retrofit existing routes
- Phase 4: DevTools and monitoring
- Migration patterns with before/after code
- Action registry tracking status
- Testing checklist
- Rollout timeline

### 5. Migration Guides ✅

#### `tradegent_ui/frontend/lib/api.ts`
- Added deprecation notice for legacy client
- Links to migration guide

#### `tradegent_ui/server/routes/schedules.py`
- Migration example showing before/after code
- Explains unified envelope integration

#### `tradegent_ui/server/websocket/price_stream.py`
- Protocol documentation
- Shows TradegentMessage payload structure
- Links to full spec

### 6. README Updates ✅

- Added "Communication Architecture" section to [README.md](README.md)
- Architecture diagram showing REST + WebSocket layers
- Quick reference table
- Links to detailed documentation

## Transport Strategy

### REST (HTTP POST to /api)
**For:** User-initiated actions, configuration, queries with no real-time pressure

**Pattern:** Request-Response
```
Client → TradegentRequest → Server → TradegentResponse (with data or error)
```

**Use Cases:**
- Update schedule settings
- Fetch schedule history
- User configuration changes
- One-time data retrieval

**Features:**
- Stateless (scales with load balancers)
- Browser DevTools support
- Standard HTTP semantics (timeout, cache)
- Uses Bearer token in Authorization header

### WebSocket (/ws/stream)
**For:** Real-time data streams, high-frequency updates, push notifications

**Pattern:** Subscription → Event Stream
```
Client → TradegentSubscription → Server
                                 ↓
                         TradegentEvent (repeated)
                         TradegentEvent
                         TradegentEvent
```

**Use Cases:**
- Live prices (real-time bid/ask)
- Portfolio P&L updates
- Order fill notifications
- Dashboard metrics (proposed)
- Scanner alerts (proposed)

**Features:**
- Real-time updates (sub-second latency)
- Multiplexed (one connection, many subscriptions)
- Automatic reconnection with exponential backoff
- Request-id correlation for subscription identification

## Standard Error Codes

| Code | HTTP | Meaning | When to Retry |
|------|------|---------|---------------|
| VALIDATION_ERROR | 400 | Invalid input (bad field) | Never |
| UNAUTHORIZED | 401 | Auth token missing/invalid | Maybe (after re-auth) |
| FORBIDDEN | 403 | Auth valid but insufficient permission | Never |
| NOT_FOUND | 404 | Resource doesn't exist | Never |
| CONFLICT | 409 | State mismatch (e.g., duplicate) | Never |
| TIMEOUT | 504 | Request took too long | Always (exponential backoff) |
| SERVER_ERROR | 500 | Unexpected error | Always (exponential backoff) |
| NETWORK_ERROR | - | Client-side network issue | Always (exponential backoff) |

## Next Steps

### Phase 1: Real-Time Dashboard (Week 1-2)
1. Create `use-dashboard-metrics.ts` hook (WS subscription)
2. Create `use-scanner-alerts.ts` hook (WS subscription)
3. Update `/ws/stream` backend to support `subscribe_metrics` and `subscribe_alerts`
4. Update dashboard component to use new hooks
5. Add connection status indicator

### Phase 2: Schedule Notifications (Week 2-3)
1. Add `subscribe_schedule_events` channel
2. Create schedule event hook
3. Update Settings → Schedules tab with live updates

### Phase 3: Audit & Retrofit (Week 3-4)
1. Identify all existing REST routes
2. Wrap responses with `wrap_response()` / `error_to_response()`
3. Use standardized action names
4. Update WebSocket handlers (portfolio, orders)

### Phase 4: DevTools & Monitoring (Future)
1. Browser DevTools extension for message inspection
2. Prometheus metrics for message volume/latency
3. Correlation-based log aggregation

## File Structure

```
tradegent_ui/
├── frontend/
│   └── lib/
│       ├── messages.ts          # 🆕 Message types
│       ├── unified-client.ts    # 🆕 Client facade
│       └── api.ts               # Updated with deprecation notice
│
├── server/
│   ├── messages.py              # 🆕 Pydantic models
│   ├── response.py              # 🆕 Response wrappers
│   ├── routes/
│   │   └── schedules.py         # Updated with migration guide
│   └── websocket/
│       └── price_stream.py      # Updated with protocol docs
│
└── docs/
    ├── COMMUNICATION_GUIDE.md   # 🆕 Quick reference
    ├── CLIENT_USAGE_EXAMPLES.md # 🆕 Code examples
    ├── IMPLEMENTATION_CHECKLIST.md # 🆕 Rollout tracking
    └── architecture/
        └── UNIFIED_MESSAGES.md  # 🆕 Full architecture spec
```

## Key Design Decisions

### 1. Single Envelope vs Dual Protocol
**Decision:** Keep both REST and WebSocket, wrap both in TradegentMessage

**Rationale:**
- REST for stateless operations (better scalability)
- WebSocket for real-time streams (lower latency)
- Single envelope provides consistency without forcing one transport for all use cases

### 2. Request ID for Correlation
**Decision:** Optional `request_id` (UUID) in all messages

**Rationale:**
- Enables request-response matching even with async flows
- Helps correlate logs across client and server
- Used for subscription-to-event correlation in WebSocket
- Standard pattern in distributed systems

### 3. Unified Error Format
**Decision:** Same error structure in TradegentMessage for both transports

**Rationale:**
- Single error handling code path in client
- Consistent error codes across API
- Enables standard monitoring/alerting based on error codes

### 4. Gradual Migration
**Decision:** Keep legacy API client, migrate new code and retrofit gradually

**Rationale:**
- No breaking changes to existing code
- Can convert routes one at a time
- Low risk of regression
- Enables parallel feature work

## Testing Recommendations

### Unit Tests
- `test_messages.py` — Pydantic model serialization
- `test_response.py` — Response wrapper functions
- `test_unified_client.ts` — Client request/subscribe logic
- `test_error_handling.ts` — Error status handling

### Integration Tests
- REST request-response cycle with real database
- WebSocket subscription and event streaming
- Connection recovery and reconnection
- Error responses on both transports

### E2E Tests
- Full dashboard update via metrics subscription
- Alert notification end-to-end
- Trade execution with event push

## Backward Compatibility

✅ **No breaking changes**
- Legacy API client (lib/api.ts) remains functional
- Existing routes continue to work
- New code can use unified-client without affecting old code
- Mix old and new during transition

## Performance Considerations

| Aspect | Details |
|--------|---------|
| **REST Latency** | ~50-100ms round-trip (stateless) |
| **WebSocket Latency** | ~1-10ms for push events (stateful) |
| **Connection Overhead** | One WS per client (reused for all subscriptions) |
| **Memory** | ~1-2KB per subscription (listener registration) |
| **Message Size** | 200-500 bytes typical, <1KB with full payload |
| **Reconnection** | Exponential backoff (1s → 2s → 4s → ...up to configured max) |

## Security Notes

- Bearer token authentication via WebSocket subprotocol `['bearer', token]`
- REST uses standard Authorization header
- All messages can be encrypted in transit (TLS for HTTPS, WSS for WebSocket)
- Request IDs help audit/trace operations
- Error details (in `details` field) don't expose sensitive info

## Monitoring & Observability

### Logging
- All messages logged with request_id for correlation
- Actions tracked per request
- Error codes aggregated for dashboards

### Metrics (Future)
- `tradegent_messages_total` (by action, type, status)
- `tradegent_message_latency` (REST vs WebSocket)
- `tradegent_errors_total` (by code)
- `tradegent_ws_connections` (active subscriptions)

### Tracing
- Correlation IDs enable request tracing
- Can follow request through entire system
- Helps debug async issues

## Community & Contribution

See [CONTRIBUTION_GUIDE.md](CONTRIBUTING.md) for how to:
- Add new actions
- Create custom hooks
- Propose architecture changes

## Links

- [Quick Start Guide](docs/COMMUNICATION_GUIDE.md)
- [Full Architecture Spec](docs/architecture/UNIFIED_MESSAGES.md)
- [Usage Examples](docs/CLIENT_USAGE_EXAMPLES.md)
- [Implementation Checklist](docs/IMPLEMENTATION_CHECKLIST.md)
- [Frontend Message Types](tradegent_ui/frontend/lib/messages.ts)
- [Frontend Client](tradegent_ui/frontend/lib/unified-client.ts)
- [Backend Models](tradegent_ui/server/messages.py)
- [Backend Wrappers](tradegent_ui/server/response.py)

---

**Implemented by**: AI Development Assistant  
**Date**: 2026-03-11  
**Status**: ✅ Ready for Phase 1
