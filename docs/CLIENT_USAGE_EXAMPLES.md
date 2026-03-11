# Unified Client Usage Examples

Complete examples for using Tradegent's unified client in real application scenarios.

## Setup

### One-time Initialization

```typescript
// app/layout.tsx or similar root component
import { createTradegentClient } from '@/lib/unified-client';
import { SessionProvider } from 'next-auth/react';

// Create client singleton
export async function getRootLayoutProps() {
  return {
    tradegentClient: createTradegentClient(async () => {
      const session = await getSession();
      return session?.accessToken || null;
    })
  };
}

// Export for use across app
export const tradegentClient = getRootLayoutProps().tradegentClient;
```

### In Components

```typescript
import { tradegentClient } from '@/app/layout';
```

## Scenario 1: Update Schedule Settings

**Use Case**: User toggles "Enabled" on a schedule in Settings → Schedules tab.

### Component

```typescript
'use client';

import { useState } from 'react';
import { tradegentClient } from '@/app/layout';
import { TradegentClientError } from '@/lib/unified-client';

export function ScheduleToggle({ scheduleId, initialEnabled }: Props) {
  const [enabled, setEnabled] = useState(initialEnabled);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async (newValue: boolean) => {
    setLoading(true);
    setError(null);

    try {
      // Make request via unified client
      const result = await tradegentClient.request(
        'patch_schedule',
        {
          schedule_id: scheduleId,
          is_enabled: newValue
        },
        5000  // 5 second timeout
      );

      // Success
      setEnabled(result.is_enabled);
    } catch (err) {
      if (err instanceof TradegentClientError) {
        // Handle specific error codes
        switch (err.code) {
          case 'VALIDATION_ERROR':
            setError(`Invalid input: ${err.message}`);
            break;
          case 'NOT_FOUND':
            setError('Schedule not found');
            break;
          case 'TIMEOUT':
            setError('Request timed out. Please try again.');
            break;
          default:
            setError(`Error: ${err.message}`);
        }
      } else {
        setError('Unexpected error');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        type="checkbox"
        checked={enabled}
        onChange={(e) => handleToggle(e.target.checked)}
        disabled={loading}
      />
      {error && <p className="text-red-500">{error}</p>}
    </div>
  );
}
```

## Scenario 2: Real-time Price Feed

**Use Case**: Dashboard shows live prices for watched tickers, updating in real-time.

### Hook

```typescript
// hooks/use-price-feed.ts
import { useEffect, useState } from 'react';
import { tradegentClient } from '@/app/layout';
import type { TradegentMessage } from '@/lib/messages';

interface PriceData {
  [ticker: string]: {
    bid: number;
    ask: number;
    last: number;
    change: number;
    changePercent: number;
  };
}

export function usePriceFeed(tickers: string[]) {
  const [prices, setPrices] = useState<PriceData>({});
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (tickers.length === 0) return;

    let isActive = true;

    // Subscribe to price stream
    const unsubscribe = tradegentClient.subscribe(
      'subscribe_prices',
      { tickers },
      (event: TradegentMessage) => {
        // Handle incoming price events
        if (!isActive) return;

        if (event.type === 'error') {
          setError(event.error?.message || 'Unknown error');
          setConnected(false);
        } else if (event.type === 'event') {
          // Update prices on each event
          const { ticker, ...priceData } = event.payload;
          setPrices((prev) => ({
            ...prev,
            [ticker]: priceData
          }));
          setConnected(true);
          setError(null);
        }
      }
    );

    return () => {
      isActive = false;
      unsubscribe();
    };
  }, [tickers]);

  return { prices, connected, error };
}
```

### Component

```typescript
import { usePriceFeed } from '@/hooks/use-price-feed';

export function PriceDashboard() {
  const { prices, connected, error } = usePriceFeed(['NVDA', 'AAPL', 'MSFT']);

  return (
    <div>
      <div className={`status ${connected ? 'connected' : 'disconnected'}`}>
        {connected ? '🟢 Live' : '⚫ Offline'}
      </div>

      {error && <div className="error">{error}</div>}

      {Object.entries(prices).map(([ticker, data]) => (
        <div key={ticker} className="price-card">
          <h3>{ticker}</h3>
          <p>Last: ${data.last.toFixed(2)}</p>
          <p>Bid: ${data.bid.toFixed(2)} | Ask: ${data.ask.toFixed(2)}</p>
          <p className={data.change >= 0 ? 'up' : 'down'}>
            {data.change >= 0 ? '↑' : '↓'} {Math.abs(data.changePercent).toFixed(2)}%
          </p>
        </div>
      ))}
    </div>
  );
}
```

## Scenario 3: Scanner Alerts with React Query

**Use Case**: Real-time alerts for high-score scanner results, with fallback to polling.

### Hook with React Query

```typescript
// hooks/use-scanner-alerts.ts
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { tradegentClient } from '@/app/layout';
import type { TradegentMessage } from '@/lib/messages';

interface ScannerAlert {
  id: number;
  scan_id: number;
  symbol: string;
  trigger: string;
  score: number;
  timestamp: number;
  details: Record<string, any>;
}

export function useScannerAlerts() {
  const [alerts, setAlerts] = useState<ScannerAlert[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  // Fallback: periodic REST query if WS disconnects
  const { data: restAlerts } = useQuery({
    queryKey: ['scanner-alerts'],
    queryFn: async () => {
      // REST endpoint to fetch recent alerts
      const result = await tradegentClient.request('get_scanner_alerts', {
        limit: 50,
        since: Date.now() - 3600000 // Last hour
      });
      return result.alerts;
    },
    refetchInterval: wsConnected ? false : 10000 // Poll every 10s if WS down
  });

  useEffect(() => {
    // Subscribe to alert stream
    const unsubscribe = tradegentClient.subscribe(
      'subscribe_alerts',
      {},
      (event: TradegentMessage) => {
        if (event.type === 'error') {
          setWsConnected(false);
        } else if (event.type === 'event') {
          const alert: ScannerAlert = {
            id: Math.random(), // Client-side ID
            ...event.payload
          };

          // Add to top of list
          setAlerts((prev) => [alert, ...prev].slice(0, 50));
          setWsConnected(true);

          // Show toast for high-score alerts
          if (alert.score >= 8.0) {
            showToast(
              `🚨 High-score alert: ${alert.symbol} (${alert.score.toFixed(1)})`,
              'info'
            );
          }
        }
      }
    );

    return unsubscribe;
  }, []);

  // Use WS alerts if available, fall back to REST
  const displayAlerts = wsConnected ? alerts : (restAlerts || []);

  return {
    alerts: displayAlerts,
    wsConnected,
    isFromWebSocket: wsConnected
  };
}
```

### Component with Toast

```typescript
import { useScannerAlerts } from '@/hooks/use-scanner-alerts';

export function AlertCenter() {
  const { alerts, wsConnected } = useScannerAlerts();

  return (
    <div className="alert-center">
      <div className="header">
        <h2>Scanner Alerts</h2>
        <span className={`status ${wsConnected ? 'live' : 'polling'}`}>
          {wsConnected ? '🔴 Live' : '⏱️ Polling'}
        </span>
      </div>

      <div className="alerts-list">
        {alerts.length === 0 ? (
          <p className="empty">No recent alerts</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`alert-item score-${Math.floor(alert.score)}`}
            >
              <div className="alert-header">
                <span className="symbol">{alert.symbol}</span>
                <span className={`score ${ alert.score >= 8 ? 'high' : 'medium'}`}>
                  {alert.score.toFixed(1)}
                </span>
              </div>
              <p className="trigger">{alert.trigger}</p>
              <details>
                <summary>Details</summary>
                <pre>{JSON.stringify(alert.details, null, 2)}</pre>
              </details>
              <time>{new Date(alert.timestamp).toLocaleTimeString()}</time>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

## Scenario 4: Form Submission with Error Handling

**Use Case**: User submits settings form, with field-level error display.

### Component

```typescript
'use client';

import { useState } from 'react';
import { useForm, SubmitHandler } from 'react-hook-form';
import { tradegentClient } from '@/app/layout';
import { TradegentClientError } from '@/lib/unified-client';

interface SettingsForm {
  email: string;
  timezone: string;
  notifications_enabled: boolean;
}

export function SettingsForm() {
  const { register, handleSubmit, formState: { errors }, setError } =
    useForm<SettingsForm>();
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const onSubmit: SubmitHandler<SettingsForm> = async (data) => {
    setSubmitting(true);
    setSuccess(false);

    try {
      await tradegentClient.request(
        'update_settings',
        data,
        10000  // 10s timeout for form submission
      );

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      if (error instanceof TradegentClientError) {
        // Handle field-level errors from server
        if (error.details?.field) {
          setError(error.details.field as any, {
            message: error.message
          });
        } else if (error.code === 'VALIDATION_ERROR') {
          // Generic validation error
          setError('root', { message: error.message });
        } else {
          setError('root', { message: `Error: ${error.message}` });
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div>
        <label>Email</label>
        <input {...register('email', { required: 'Email is required' })} />
        {errors.email && <span className="error">{errors.email.message}</span>}
      </div>

      <div>
        <label>Timezone</label>
        <select {...register('timezone', { required: true })}>
          <option value="America/New_York">Eastern</option>
          <option value="America/Chicago">Central</option>
          <option value="America/Denver">Mountain</option>
          <option value="America/Los_Angeles">Pacific</option>
        </select>
      </div>

      <div>
        <label>
          <input type="checkbox" {...register('notifications_enabled')} />
          Enable Notifications
        </label>
      </div>

      {errors.root && (
        <div className="error" role="alert">
          {errors.root.message}
        </div>
      )}

      {success && (
        <div className="success" role="status">
          Settings saved successfully!
        </div>
      )}

      <button type="submit" disabled={submitting}>
        {submitting ? 'Saving...' : 'Save Settings'}
      </button>
    </form>
  );
}
```

## Scenario 5: Retry with Exponential Backoff

**Use Case**: Critical operation (trade execution) with automatic retry.

### Utility Function

```typescript
// lib/request-utils.ts
import { tradegentClient } from '@/app/layout';
import { TradegentClientError } from '@/lib/unified-client';

interface RetryOptions {
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  retryableErrors?: string[];  // Error codes to retry on
}

export async function requestWithRetry<T>(
  action: string,
  payload: any,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxRetries = 3,
    baseDelayMs = 500,
    maxDelayMs = 10000,
    retryableErrors = ['TIMEOUT', 'NETWORK_ERROR', 'SERVER_ERROR']
  } = options;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await tradegentClient.request<any, T>(action, payload);
    } catch (error) {
      lastError = error;

      // Don't retry if error is not retryable
      if (
        error instanceof TradegentClientError &&
        !retryableErrors.includes(error.code)
      ) {
        throw error;
      }

      // Don't retry on last attempt
      if (attempt === maxRetries) {
        break;
      }

      // Calculate backoff with jitter
      const delayMs = Math.min(
        baseDelayMs * Math.pow(2, attempt) + Math.random() * 1000,
        maxDelayMs
      );

      console.warn(
        `Request failed (attempt ${attempt + 1}/${maxRetries + 1}), ` +
        `retrying in ${delayMs}ms:`,
        lastError
      );

      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  throw lastError || new Error(`Request failed after ${maxRetries} retries`);
}
```

### Usage

```typescript
import { requestWithRetry } from '@/lib/request-utils';

// Critical trade execution
try {
  const result = await requestWithRetry(
    'place_order',
    {
      symbol: 'NVDA',
      quantity: 100,
      price: 950.00
    },
    {
      maxRetries: 5,
      baseDelayMs: 100,  // More aggressive for trading
      retryableErrors: ['TIMEOUT', 'NETWORK_ERROR']  // Don't retry validation errors
    }
  );

  console.log('Order placed:', result);
} catch (error) {
  console.error('Critical: Order placement failed:', error);
  // Handle failure (e.g., alert user, emit event, etc.)
}
```

## Scenario 6: Dependencies Between Requests

**Use Case**: Fetch schedule, then load its history.

### Cascading Requests

```typescript
// lib/schedule-utils.ts
import { tradegentClient } from '@/app/layout';

export async function loadScheduleWithHistory(scheduleId: number) {
  // First request: get schedule
  const schedule = await tradegentClient.request('get_schedule', {
    schedule_id: scheduleId
  });

  // Second request: get history for this schedule
  const history = await tradegentClient.request('get_schedule_history', {
    schedule_id: scheduleId,
    limit: 10
  });

  return { schedule, history };
}
```

### React Query (Recommended for Complex Dependencies)

```typescript
import { useQueries } from '@tanstack/react-query';

export function useScheduleWithHistory(scheduleId: number) {
  const [schedule, history] = useQueries({
    queries: [
      {
        queryKey: ['schedule', scheduleId],
        queryFn: () =>
          tradegentClient.request('get_schedule', { schedule_id: scheduleId })
      },
      {
        queryKey: ['schedule-history', scheduleId],
        queryFn: () =>
          tradegentClient.request('get_schedule_history', {
            schedule_id: scheduleId,
            limit: 10
          }),
        enabled: !!scheduleId  // Only fetch after schedule loads
      }
    ]
  });

  return {
    schedule: schedule.data,
    history: history.data,
    isLoading: schedule.isLoading || history.isLoading,
    error: schedule.error || history.error
  };
}
```

## Error Handling Patterns

### Pattern: Specific Error Recovery

```typescript
try {
  const result = await tradegentClient.request('patch_schedule', data);
} catch (error) {
  if (error instanceof TradegentClientError) {
    switch (error.code) {
      case 'VALIDATION_ERROR':
        // Show field-level errors
        showFieldErrors(error.details);
        break;

      case 'NOT_FOUND':
        // Navigate to list view
        router.push('/schedules');
        break;

      case 'UNAUTHORIZED':
        // Re-authenticate
        await signIn();
        break;

      case 'TIMEOUT':
        // Suggest manual retry
        showToast('Request timed out. Please try again.');
        break;

      case 'NETWORK_ERROR':
        // Check connection
        showToast('Network error. Please check your connection.');
        break;

      default:
        // Generic error
        showToast(`Error: ${error.message}`);
    }
  }
}
```

## Files

| File | Purpose |
|------|---------|
| `lib/messages.ts` | Message type definitions |
| `lib/unified-client.ts` | Client implementation |
| `lib/request-utils.ts` | Utility functions (retry, etc.) |
| `hooks/use-price-feed.ts` | Real-time price subscription hook |
| `hooks/use-scanner-alerts.ts` | Alert subscription hook |
| `app/layout.tsx` | Client initialization |

## See Also

- [Unified Messages Architecture](../architecture/UNIFIED_MESSAGES.md)
- [Communication Quick Reference](../COMMUNICATION_GUIDE.md)
- [Implementation Checklist](../IMPLEMENTATION_CHECKLIST.md)
