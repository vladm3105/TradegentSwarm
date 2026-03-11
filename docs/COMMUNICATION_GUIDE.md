# Unified Communication Quick Reference

**TL;DR**: All Tradegent messages use the same `TradegentMessage` envelope across REST and WebSocket to enable consistent error handling, correlation, and logging.

## Quick Start

### Frontend (React/TypeScript)

```typescript
import { createTradegentClient } from '@/lib/unified-client';
import { getSession } from 'next-auth/react';

// Initialize once
const client = createTradegentClient(async () => {
  const session = await getSession();
  return session?.accessToken || null;
});

// Make requests (REST)
const schedule = await client.request('patch_schedule', {
  schedule_id: 1,
  enabled: false
});

// Subscribe to push (WebSocket)
const unsubscribe = client.subscribe(
  'subscribe_prices',
  { tickers: ['NVDA', 'AAPL'] },
  (event) => {
    console.log('Price update:', event.payload);
  }
);
```

### Backend (FastAPI)

```python
from fastapi import APIRouter, HTTPException
from tradegent_ui.server.messages import TradegentRequest, TradegentActions
from tradegent_ui.server.response import wrap_response, error_to_response

router = APIRouter()

@router.post("/api")
async def unified_api(request: TradegentRequest):
    """Single endpoint for all request-response operations."""
    
    if request.action == TradegentActions.PATCH_SCHEDULE:
        try:
            if request.payload.schedule_id <= 0:
                return error_to_response(
                    action=request.action,
                    code="VALIDATION_ERROR",
                    message="Schedule ID must be positive",
                    request_id=request.request_id
                )
            
            # ... business logic ...
            result = db.update_schedule(request.payload)
            
            return wrap_response(
                result,
                action=request.action,
                request_id=request.request_id
            )
        except Exception as e:
            return error_to_response(
                action=request.action,
                code="SERVER_ERROR",
                message=str(e),
                request_id=request.request_id
            )
    
    return error_to_response(
        action="unknown",
        code="NOT_FOUND",
        message=f"Unknown action: {request.action}",
        request_id=request.request_id
    )
```

## Message Types

### Request/Response (HTTP REST)

```typescript
// Client sends
{
  type: 'request',
  action: 'patch_schedule',
  request_id: 'uuid',
  payload: { schedule_id: 1, enabled: false },
  timestamp: 1694520000000
}

// Server responds
{
  type: 'response',
  action: 'patch_schedule',
  request_id: 'uuid',  // Same ID for correlation
  payload: { schedule_id: 1, enabled: false, updated_at: '...' },
  timestamp: 1694520001000
}
```

### Subscription/Event (WebSocket)

```typescript
// Client sends
{
  type: 'subscription',
  action: 'subscribe_prices',
  request_id: 'uuid',
  payload: { tickers: ['NVDA'] },
  timestamp: 1694520000000
}

// Server pushes (multiple times)
{
  type: 'event',
  action: 'subscribe_prices',
  request_id: 'uuid',  // Same ID links to subscription
  payload: { ticker: 'NVDA', bid: 950.25, ask: 950.30 },
  timestamp: 1694520001000
}
```

### Error (Any Transport)

```typescript
{
  type: 'error',
  action: 'patch_schedule',
  request_id: 'uuid',
  error: {
    code: 'VALIDATION_ERROR',
    message: 'Schedule ID must be positive',
    details: { field: 'schedule_id' }
  },
  timestamp: 1694520001000
}
```

## Common Actions

| Action | Type | Use |
|--------|------|-----|
| `get_schedules` | request | Fetch all schedules |
| `patch_schedule` | request | Update schedule |
| `run_schedule_now` | request | Trigger immediate run |
| `get_schedule_history` | request | Fetch run history |
| `subscribe_prices` | subscription | Real-time prices |
| `subscribe_portfolio` | subscription | Portfolio updates |
| `subscribe_orders` | subscription | Order fills |
| `subscribe_metrics` | subscription | Dashboard metrics |
| `subscribe_alerts` | subscription | Scanner alerts |
| `unsubscribe` | subscription | Cancel subscription |

(See `tradegent_ui/server/messages.py::TradegentActions` for complete list)

## Error Handling

### Frontend

```typescript
try {
  const result = await client.request('patch_schedule', payload);
} catch (error) {
  if (error instanceof TradegentClientError) {
    // Has .code, .message, .details, .action, .request_id
    console.error(`[${error.code}] ${error.message}`);
  }
}
```

### Backend

```python
from tradegent_ui.server.response import error_to_response

return error_to_response(
    action="patch_schedule",
    code="VALIDATION_ERROR",  # See error code table below
    message="User-friendly message",
    request_id=request.request_id,
    details={"field": "schedule_id", "reason": "must be positive"}  # Optional
)
```

## Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| VALIDATION_ERROR | 400 | Invalid input (check `details`) |
| UNAUTHORIZED | 401 | Missing/invalid auth token |
| FORBIDDEN | 403 | Auth valid but not allowed |
| NOT_FOUND | 404 | Resource doesn't exist |
| CONFLICT | 409 | State mismatch (e.g., duplicate) |
| TIMEOUT | 504 | Request took too long |
| SERVER_ERROR | 500 | Unexpected error |
| NETWORK_ERROR | - | Client-side network issue |

## Transport Selection

| Situation | Transport |
|-----------|-----------|
| User clicks a button → update | **REST** |
| Need data immediately (urgency × 10/sec) | **WebSocket** |
| Historical/archived data | **REST** |
| Frequently-changing values (>once/sec) | **WebSocket** |
| User hasn't actively opened the screen | **REST** |
| Trader is watching intently | **WebSocket** |

## Transport Decision Table

| Surface | Primary Transport | Secondary | Notes |
|---------|-------------------|-----------|-------|
| A2UI command/query actions | REST | WebSocket (events only) | Keep request-response on REST; use WS for progress and live state changes |
| Grafana-style dashboards | REST | WebSocket (refresh hints) | Pull metrics/query APIs via REST; add WS only for active live updates |
| Neo4j graph exploration | REST | WebSocket (incremental updates) | Use REST for graph query/layout payloads; WS only for live graph deltas |
| Market/portfolio/order streams | WebSocket | REST (fallback snapshots) | WS is the default for high-frequency updates |

Policy guardrails:
- Keep exactly two primary browser interaction gates: REST + WebSocket
- Do not adopt WS-only architecture
- Add SSE only for one-way high-fanout notifications when WS overhead is proven by metrics

## Debugging

### Log a Request

```python
# Backend logs include request_id for correlation
log.info("schedule_updated", 
    request_id="550e8400-e29b-41d4-a716-446655440000",
    action="patch_schedule"
)

# Find all related logs
# $ grep "550e8400-e29b-41d4-a716-446655440000" trading_ui.log
```

### Inspect Messages in Browser

Add to frontend console:
```javascript
// Intercept all requests
const originalRequest = TradegentClient.prototype.request;
TradegentClient.prototype.request = async function(action, payload) {
  console.log(`→ ${action}`, payload);
  const result = await originalRequest.call(this, action, payload);
  console.log(`← ${action}`, result);
  return result;
};

// Or use Network tab to see REST POST /api bodies
// Or use DevTools to inspect WebSocket frames
```

## Patterns

### Request Timeout

```typescript
const timeout = 5000;  // 5 seconds
try {
  const result = await client.request('patch_schedule', payload, timeout);
} catch (error) {
  if (error.code === 'TIMEOUT') {
    console.warn('Request timed out');
  }
}
```

### Retry with Exponential Backoff

```typescript
async function requestWithRetry(action, payload, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await client.request(action, payload);
    } catch (error) {
      if (i < maxRetries - 1) {
        const delay = 1000 * Math.pow(2, i);  // 1s, 2s, 4s
        await new Promise(resolve => setTimeout(resolve, delay));
      } else {
        throw error;
      }
    }
  }
}
```

### React Query Integration

```typescript
const { data: schedule } = useQuery({
  queryKey: ['schedule', id],
  queryFn: async () => {
    try {
      return await client.request('get_schedule', { id });
    } catch (error) {
      if (error.code === 'NOT_FOUND') {
        // Return empty or null
      }
      throw error;
    }
  }
});
```

### React Hook for Subscriptions

```typescript
export function usePriceStream(tickers) {
  const [prices, setPrices] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!tickers?.length) return;

    const unsubscribe = client.subscribe(
      'subscribe_prices',
      { tickers },
      (event) => {
        if (event.type === 'error') {
          setError(event.error);
        } else {
          const { ticker, ...price } = event.payload;
          setPrices(p => ({ ...p, [ticker]: price }));
        }
      }
    );

    return unsubscribe;
  }, [tickers]);

  return { prices, error };
}

// Usage
const { prices } = usePriceStream(['NVDA', 'AAPL']);
```

## Files

| Path | Purpose |
|------|---------|
| `tradegent_ui/frontend/lib/messages.ts` | Type definitions |
| `tradegent_ui/frontend/lib/unified-client.ts` | Client facade |
| `tradegent_ui/server/messages.py` | Pydantic models |
| `tradegent_ui/server/response.py` | Response wrappers |
| `docs/architecture/UNIFIED_MESSAGES.md` | Full reference |

## See Also

- [Full Architecture](UNIFIED_MESSAGES.md)
- [API Reference](../api-reference.md)
- [Frontend Setup](../../tradegent_ui/frontend/README.md)
- [Backend Setup](../../tradegent_ui/server/README.md)
