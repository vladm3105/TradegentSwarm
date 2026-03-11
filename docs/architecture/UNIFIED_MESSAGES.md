# Unified Communication Architecture

## Overview

Tradegent uses a **unified message envelope** across all client-server communication, enabling consistent handling of both real-time push (WebSocket) and request-response (REST) patterns with a single protocol.

### Core Principle

All communication—whether REST or WebSocket—uses the same `TradegentMessage` structure:

```typescript
interface TradegentMessage<T = any> {
  type: 'request' | 'response' | 'subscription' | 'event' | 'error';
  action: string;
  request_id?: string;
  payload?: T;      // Response data lives here (not in a separate .response field)
  timestamp?: number;
  error?: { code: string; message: string; details?: Record<string, any> };
}
```

`TradegentRESTClient` checks `data.type === 'error'` before accessing `data.payload`,
so error responses are handled before the success path in all cases.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                 TRADEGENT UNIFIED PROTOCOL                   │
│              (TradegentMessage Envelope)                      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────┐          ┌──────────────────────┐   │
│  │  REST/HTTP Layer    │          │  WebSocket Layer     │   │
│  │  (Stateless)        │          │  (Stateful)          │   │
│  ├─────────────────────┤          ├──────────────────────┤   │
│  │ POST /api           │          │ /ws/stream           │   │
│  │                     │          │ /ws/agent            │   │
│  │ TradegentRequest    │          │                      │   │
│  │    ↓                │          │ TradegentSubscription│   │
│  │ TradegentResponse   │          │    ↓                │   │
│  │    ↓                │          │ TradegentEvent      │   │
│  │ TradegentError      │          │ TradegentError      │   │
│  └─────────────────────┘          └──────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │       Shared Error Handling & Correlation               │ │
│  │  - request_id for request-response matching             │ │
│  │  - Unified error codes and formats                      │ │
│  │  - Consistent logging across both transports            │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Message Types

### 1. Request → Response (REST / HTTP)

**When to use:** User-initiated actions (create, update, read), non-urgent queries.

**Flow:**
```
Client                          Server
  │                              │
  ├─ TradegentRequest            │
  │  (type: 'request')           │
  │  (action: 'patch_schedule')  │
  │  (payload: {...})            │
  ├──────────────────────────────→
  │                              ├─ Validate
  │                              ├─ Process
  │                              ├─ Generate response
  │  ← TradegentResponse         │
  │    (type: 'response')        │
  │    (payload: {...})          │
  │←──────────────────────────────
```

**Example:**
```typescript
// Client
const response = await client.request('patch_schedule', {
  schedule_id: 1,
  enabled: false
});

// Server
@router.post("/api")
async def unified_api(request: TradegentRequest):
    if request.action == "patch_schedule":
        result = db.update_schedule(request.payload)
        return wrap_response(result, action="patch_schedule", request_id=request.request_id)
```

### 2. Subscription → Event Stream (WebSocket)

**When to use:** Real-time data streams, push notifications, live updates.

**Flow:**
```
Client                              Server
  │                                  │
  ├─ TradegentSubscription           │
  │  (type: 'subscription')          │
  │  (action: 'subscribe_prices')    │
  │  (payload: {tickers: [...]})     │
  ├─────────────────────────────────→
  │                                  ├─ Register subscription
  │  ← TradegentEvent                │
  │    (type: 'event')               │
  │    (payload: {ticker, bid, ask}) │
  │←─────────────────────────────────
  │  ← TradegentEvent                │
  │    (type: 'event')               │
  │    (payload: {ticker, bid, ask}) │
  │←─────────────────────────────────
  │  [stream continues...]           │
```

**Example:**
```typescript
// Client
const unsubscribe = client.subscribe(
  'subscribe_prices',
  { tickers: ['NVDA', 'AAPL'] },
  (event) => {
    console.log('New price:', event.payload);
  }
);

// Server
@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        message = TradegentMessage.parse_raw(data)
        if message.type == "subscription" and message.action == "subscribe_prices":
            # Register subscription
            while True:
                price_event = create_event(
                    action="subscribe_prices",
                    payload={"ticker": "NVDA", "bid": 950.20, "ask": 950.30},
                    request_id=message.request_id
                )
                await websocket.send_text(price_event.json())
```

### 3. Error Response (Either Transport)

**When to use:** Any operation fails validation or encounters an error.

**Flow (can occur in request-response or push):**
```
Client                           Server
  │ (request)                      │
  ├─────────────────────────────→
  │                              ├─ Validation error
  │  ← TradegentMessage (error)  │
  │    (type: 'error')           │
  │    (error: {code, message})  │
  │←─────────────────────────────
```

**Example:**
```typescript
// Client catches error
try {
  const result = await client.request('patch_schedule', {
    schedule_id: -1  // Invalid!
  });
} catch (error) {
  if (error instanceof TradegentClientError) {
    console.error(`${error.code}: ${error.message}`);
  }
}

// Server returns error
@router.post("/api")
async def unified_api(request: TradegentRequest):
    if request.payload.schedule_id <= 0:
        return error_to_response(
            action="patch_schedule",
            code="VALIDATION_ERROR",
            message="Schedule ID must be positive",
            request_id=request.request_id,
            details={"field": "schedule_id", "reason": "must be > 0"}
        )
```

## Transport Selection Guide

| Feature | Transport | Reasoning |
|---------|-----------|-----------|
| **Real-time Prices** | WebSocket | Microsecond update frequency, continuous stream |
| **Portfolio P&L** | WebSocket | Changes on every fill, trader watches live |
| **Order Fills** | WebSocket | Unpredictable timing, critical to know instantly |
| **Dashboard Metrics** | **WebSocket (proposed)** | Should update every 5-10 seconds, live view |
| **Scanner Alerts** | **WebSocket (proposed)** | High-priority, should pop immediately |
| **Schedules Config** | REST | User edits occasionally, no time pressure |
| **Trade Journal** | REST | Historical, append-only, no real-time demands |
| **Watchlist** | REST | Manual setup, occasional price checks (can poll) |
| **Settings/Auth** | REST | One-shot, user-initiated, standard form pattern |
| **Post-Trade Reviews** | REST | Analyzed after trade complete, not live |

## Implementation: Frontend

### Option A: Use Unified Client (Recommended)

```typescript
// Once at app initialization
import { createTradegentClient } from '@/lib/unified-client';

const tradegentClient = createTradegentClient(async () => {
  const session = await getSession();
  return session?.accessToken || null;
});

// Usage: request-response
const schedule = await tradegentClient.request('patch_schedule', {
  schedule_id: 1,
  enabled: false
});

// Usage: push subscription
const unsubscribe = tradegentClient.subscribe(
  'subscribe_prices',
  { tickers: ['NVDA'] },
  (event) => { /* handle price update */ }
);
```

### Option B: Traditional Hooks (React Query + Custom WS)

```typescript
// Request-response queries
const { data: schedule } = useQuery({
  queryKey: ['schedule', id],
  queryFn: () => tradegentClient.request('get_schedule', { id })
});

// Push subscriptions
const [prices, setPrices] = useState({});

useEffect(() => {
  const unsubscribe = tradegentClient.subscribe(
    'subscribe_prices',
    { tickers: ['NVDA'] },
    (event) => { setPrices(p => ({ ...p, [event.payload.ticker]: event.payload })); }
  );
  return unsubscribe;
}, []);
```

## Implementation: Backend

### All Routes Return TradegentMessage Envelope

**Before (inconsistent):**
```python
@router.patch("/schedules/{id}")
async def update(id: int, data: dict):
    return {"schedule_id": id, "enabled": data.enabled}  # Raw dict
```

**After (consistent):**
```python
from tradegent_ui.server.response import wrap_response, error_to_response

@router.patch("/schedules/{id}")
async def update(id: int, data: dict):
    if id <= 0:
        return error_to_response(
            action="patch_schedule",
            code="VALIDATION_ERROR",
            message="ID must be positive",
            details={"field": "id"}
        )
    result = {"schedule_id": id, "enabled": data.enabled}
    return wrap_response(result, action="patch_schedule")
```

### WebSocket Handler Using Unified Messages

```python
from tradegent_ui.server.messages import (
    TradegentMessage,
    TradegentActions,
    create_event,
    create_error
)

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    subscriptions = {}  # request_id → subscription details
    
    while True:
        try:
            data = await websocket.receive_text()
            message = TradegentMessage.model_validate_json(data)
            
            if message.action == TradegentActions.SUBSCRIBE_PRICES:
                # Store subscription
                subscriptions[message.request_id] = {
                    "action": "subscribe_prices",
                    "tickers": message.payload["tickers"]
                }
                
                # Start pushing events
                while message.request_id in subscriptions:
                    prices = fetch_latest_prices(subscriptions[message.request_id]["tickers"])
                    for ticker, price_data in prices.items():
                        event = create_event(
                            action="subscribe_prices",
                            payload=price_data,
                            request_id=message.request_id
                        )
                        await websocket.send_text(event.model_dump_json())
                    await asyncio.sleep(1)
                    
            elif message.action == TradegentActions.UNSUBSCRIBE:
                subscriptions.pop(message.request_id, None)
                
        except Exception as e:
            error = create_error(
                action="unknown",
                code="SERVER_ERROR",
                message=str(e)
            )
            await websocket.send_text(error.model_dump_json())
```

## Request Correlation

All messages include an optional `request_id` field (UUID recommended) for correlation:

```typescript
// Client generates request_id
const requestId = crypto.randomUUID();
const response = await client.request('patch_schedule', payload, requestId);

// Server echoes request_id in response
// → Enables request-response matching in async scenarios
// → Enables grouping log entries across both client and server
```

**Logging correlation:**
```python
# Server logs
log.info("schedule_updated", 
    request_id="550e8400-e29b-41d4-a716-446655440000",
    action="patch_schedule",
    schedule_id=1
)

# Client logs
log.debug("REST response",
    request_id="550e8400-e29b-41d4-a716-446655440000",
    action="patch_schedule"
)
```

## Error Codes (Standardized)

| Code | HTTP Status | Meaning | Example |
|------|-------------|---------|---------|
| VALIDATION_ERROR | 400 | Invalid request data | Schedule ID < 0 |
| UNAUTHORIZED | 401 | Auth required or token invalid | Missing Bearer token |
| FORBIDDEN | 403 | Auth valid but insufficient permissions | User not admin |
| NOT_FOUND | 404 | Resource doesn't exist | Schedule ID not in DB |
| CONFLICT | 409 | State conflict (e.g., already exists) | Can't create duplicate |
| TIMEOUT | 504 | Request took too long | Network slow |
| SERVER_ERROR | 500 | Unexpected server error | Crash in business logic |
| NETWORK_ERROR | - | Client-side network issue | Connection refused |

## Benefits of Unified Envelope

### For Clients
- **Single protocol** — Same code paths for REST and WS
- **Type-safe** — TypeScript interfaces match server Pydantic models
- **Correlation** — request_id links requests to responses even in async code
- **Consistent error handling** — Same error structure across transports

### For Servers
- **Unified error handling** — Same error codes/structure for all endpoints
- **Logging** — Standard fields (request_id, action, timestamp) for all messages
- **Debugging** — Can grep logs by request_id to trace request flows
- **Extensibility** — Easy to add message-level auth, versioning, etc.

### For Operations
- **Monitoring** — Count errors by code, action, response time
- **Tracing** — Follow request through system using request_id
- **Auditing** — All operations logged in consistent format

## Migration Path (Incremental)

### Phase 1: Add Unified Layer ✅ Complete
- ✅ Define TradegentMessage schema (TypeScript + Python)
- ✅ Create unified client abstraction (`unified-client.ts`)
- ✅ Create response wrapper utilities (`messages.py`)
- ✅ Full TypeScript strict-mode compliance (zero `tsc --noEmit` errors)
- ✅ NextAuth v5 integration with Auth0 + built-in credentials

### Phase 2: Expose Metrics/Alerts (Near Term)
- Add dashboard metrics to `/ws/stream` push
- Add scanner alerts to `/ws/stream` push  
- Update dashboard hooks to use new streams

### Phase 3: Audit & Retrofit (Next Sprint)
- Update existing REST routes to use response wrappers
- Update WebSocket handlers to standardize message format
- Document all actions in action registry

### Phase 4: DevTools & Monitoring (Future)
- Add Tradegent DevTools browser extension
- Add unified message inspector/debugger
- Add metrics collector for message volume/latency

## Files

| File | Purpose |
|------|---------|
| `tradegent_ui/frontend/lib/messages.ts` | TypeScript envelope types, factory helpers, action constants |
| `tradegent_ui/frontend/lib/unified-client.ts` | REST + WS facade (`TradegentClient`) |
| `tradegent_ui/frontend/lib/websocket.ts` | Low-level WebSocket client |
| `tradegent_ui/frontend/lib/websocket-auth.ts` | Auth-aware WebSocket helpers |
| `tradegent_ui/server/messages.py` | Python message models (Pydantic) |
| `tradegent_ui/server/response.py` | FastAPI response wrappers |
| `docs/COMMUNICATION_GUIDE.md` | Developer guide (quick reference) |
| `docs/architecture/UNIFIED_MESSAGES.md` | This document |

## Links

- [Communication Guide](COMMUNICATION_GUIDE.md) — Quick reference for using unified messages
- [API Reference](../api-reference.md) — Endpoint documentation
- [TypeScript Types](../../frontend/lib/messages.ts) — Client-side types
- [Python Models](../../server/messages.py) — Server-side models
