/**
 * Unified client abstraction for Tradegent communication.
 *
 * Provides a single interface for both REST and WebSocket transports,
 * handling authentication, correlation IDs, and message envelope
 * serialization/deserialization transparently.
 *
 * This allows calling code to be transport-agnostic:
 * ```typescript
 * const response = await client.request('patch_schedule', { schedule_id: 1 });
 * client.subscribe('subscribe_prices', { tickers: ['NVDA'] }, onEvent);
 * ```
 *
 * Architecture:
 * - TradegentClient: Main facade
 * - TradegentRESTClient: Implementation for REST POST to /api
 * - TradegentWSClient: Implementation for WebSocket push
 * - Both use TradegentMessage envelope internally
 */

import { createLogger } from './logger';
import {
  TradegentMessage,
  TradegentRequest,
  TradegentResponse,
  TradegentSubscription,
  TradegentError,
  createRequest,
  createSubscription,
  createError,
  generateRequestId,
} from './messages';

const log = createLogger('unified-client');

/**
 * Error thrown when a request gets an error response.
 */
export class TradegentClientError extends Error {
  constructor(
    public action: string,
    public code: string,
    message: string,
    public details?: Record<string, any>,
    public request_id?: string
  ) {
    super(message);
    this.name = 'TradegentClientError';
  }
}

/**
 * Event listener for WebSocket subscription events.
 * Called each time the server pushes an event for the subscription.
 */
export type EventListener<T = any> = (event: TradegentMessage<T>) => void;

/**
 * Configuration for REST client.
 */
interface RESTClientConfig {
  apiUrl: string;
  getAuthToken: () => Promise<string | null>;
}

/**
 * Configuration for WebSocket client.
 */
interface WSClientConfig {
  wsEndpoint: string;
  getAuthToken: () => Promise<string | null>;
  reconnectAttempts?: number;
  reconnectDelayMs?: number;
}

/**
 * REST client implementation using traditional HTTP POST requests.
 *
 * Each request:
 * 1. Wraps payload in a `TradegentRequest` message envelope
 * 2. POSTs to `/api` with the `TradegentMessage` body
 * 3. Server wraps its reply in a `TradegentMessage` envelope
 * 4. Client checks `type === 'error'` first, then returns `data.payload`
 *
 * Benefits:
 * - Stateless (no connection lifecycle)
 * - Browser DevTools support
 * - Standard HTTP semantics (timeout, retry, cache)
 * - Scalable (any load balancer works)
 */
class TradegentRESTClient {
  private config: RESTClientConfig;

  constructor(config: RESTClientConfig) {
    this.config = config;
  }

  /**
   * Send a request-response message via HTTP POST.
   *
   * @param action Action identifier
   * @param payload Request payload
   * @param timeout Optional request timeout in milliseconds
   * @returns Parsed response payload
   * @throws TradegentClientError if error response received
   */
  async request<T = any, R = any>(
    action: string,
    payload?: T,
    timeout?: number
  ): Promise<R> {
    const requestId = generateRequestId();
    const request = createRequest(action, payload, requestId);

    log.debug('REST request', { action, requestId });

    try {
      const token = await this.config.getAuthToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const controller = new AbortController();
      let timeoutId: ReturnType<typeof setTimeout> | null = null;
      if (timeout) {
        timeoutId = setTimeout(() => controller.abort(), timeout);
      }

      const url = `${this.config.apiUrl}/api`;
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (timeoutId) {
        clearTimeout(timeoutId);
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        if (errorData.error) {
          const err = errorData.error as TradegentError;
          throw new TradegentClientError(
            action,
            err.code,
            err.message,
            err.details,
            errorData.request_id
          );
        }

        throw new TradegentClientError(
          action,
          `HTTP_${response.status}`,
          `HTTP ${response.status}: ${response.statusText}`,
          {},
          requestId
        );
      }

      const data = (await response.json()) as TradegentMessage<R>;

      if (data.type === 'error') {
        const err = data.error!;
        throw new TradegentClientError(
          action,
          err.code,
          err.message,
          err.details,
          data.request_id
        );
      }

      log.debug('REST response', { action, requestId });
      return data.payload as R;
    } catch (error) {
      if (error instanceof TradegentClientError) {
        throw error;
      }

      if (error instanceof Error && error.name === 'AbortError') {
        throw new TradegentClientError(action, 'TIMEOUT', 'Request timeout', {}, requestId);
      }

      const message = error instanceof Error ? error.message : String(error);
      throw new TradegentClientError(action, 'NETWORK_ERROR', message, {}, requestId);
    }
  }
}

/**
 * WebSocket client implementation for real-time push events.
 *
 * Each subscription:
 * 1. Establishes a shared WebSocket connection (reused across subscriptions)
 * 2. Sends a `TradegentSubscription` message to the server
 * 3. Receives `TradegentEvent` messages keyed by `request_id`
 * 4. Routes events to registered listeners by request_id
 *
 * Benefits:
 * - Real-time push for frequently changing data
 * - Multiplexed transport (one connection for many subscriptions)
 * - Bidirectional unsubscribe support
 */
class TradegentWSClient {
  private config: WSClientConfig;
  private ws: WebSocket | null = null;
  private listeners = new Map<string, EventListener[]>();
  private pendingSubscriptions = new Map<string, TradegentSubscription>();
  private reconnectAttempts = 0;
  private reconnectScheduled = false;

  constructor(config: WSClientConfig) {
    this.config = {
      reconnectAttempts: 5,
      reconnectDelayMs: 1000,
      ...config,
    };
  }

  /**
   * Connect to WebSocket endpoint.
   * Called automatically when first subscription is made.
   *
   * @throws Error if connection fails after max retries
   */
  private async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    // Resolve token before entering Promise executor (executor is not async)
    const token = await this.config.getAuthToken();

    return new Promise((resolve, reject) => {
      try {
        const url = this.config.wsEndpoint;

        this.ws = token
          ? new WebSocket(url, ['bearer', token])
          : new WebSocket(url);

        this.ws.onmessage = (event) => this.handleMessage(event);
        this.ws.onerror = (error) => {
          log.error('WS error', { error });
          this.scheduleReconnect();
        };
        this.ws.onclose = () => {
          log.info('WS closed');
          this.ws = null;
          this.scheduleReconnect();
        };
        this.ws.onopen = () => {
          log.info('WS connected');
          this.reconnectAttempts = 0;
          this.resubscribeAll();
          resolve();
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Subscribe to server push events.
   * Connection established automatically if not already connected.
   *
   * @param action Subscription action (e.g., 'subscribe_prices')
   * @param payload Subscription parameters
   * @param listener Event handler called for each pushed event
   * @returns Unsubscribe function
   */
  subscribe<T = any, E = any>(
    action: string,
    payload?: T,
    listener?: EventListener<E>
  ): () => Promise<void> {
    const requestId = generateRequestId();
    const subscription = createSubscription(action, payload, requestId);

    // Store subscription for reconnect
    this.pendingSubscriptions.set(requestId, subscription);

    // Register listener
    if (listener) {
      const listeners = this.listeners.get(requestId) || [];
      listeners.push(listener);
      this.listeners.set(requestId, listeners);
    }

    // Ensure connection and send subscription
    this.connect()
      .then(() => {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws!.send(JSON.stringify(subscription));
          log.debug('WS subscription sent', { action, requestId });
        }
      })
      .catch((error) => {
        log.error('WS subscription failed', { action, requestId, error });
      });

    // Return unsubscribe function
    return async () => {
      this.pendingSubscriptions.delete(requestId);
      this.listeners.delete(requestId);

      if (this.ws?.readyState === WebSocket.OPEN) {
        const unsubMessage = createSubscription('unsubscribe', { request_id: requestId }, requestId);
        this.ws.send(JSON.stringify(unsubMessage));
        log.debug('WS unsubscription sent', { action, requestId });
      }
    };
  }

  /**
   * Handle incoming WebSocket messages.
   * Routes events to registered listeners by request_id.
   *
   * @param event WebSocket message event
   */
  private handleMessage(event: MessageEvent<string>): void {
    try {
      const message = JSON.parse(event.data) as TradegentMessage;

      if (message.type === 'error') {
        const err = message.error!;
        log.error('WS error event', {
          action: message.action,
          code: err.code,
          requestId: message.request_id,
        });

        if (message.request_id) {
          const listeners = this.listeners.get(message.request_id) || [];
          listeners.forEach((listener) => listener(message));
        }
        return;
      }

      if (message.type === 'event' && message.request_id) {
        const listeners = this.listeners.get(message.request_id) || [];
        listeners.forEach((listener) => listener(message));
      }
    } catch (error) {
      log.error('WS message parse error', { error });
    }
  }

  /**
   * Schedule automatic reconnection with exponential backoff.
   *
   * @private
   */
  private scheduleReconnect(): void {
    if (this.reconnectScheduled || this.reconnectAttempts >= this.config.reconnectAttempts!) {
      return;
    }

    this.reconnectScheduled = true;
    const delay = this.config.reconnectDelayMs! * Math.pow(2, this.reconnectAttempts);

    setTimeout(() => {
      this.reconnectScheduled = false;
      this.reconnectAttempts++;
      log.info('WS reconnecting', { attempt: this.reconnectAttempts });
      this.connect().catch((error) => {
        log.error('WS reconnection failed', { error });
      });
    }, delay);
  }

  /**
   * Resubscribe to all stored subscriptions after reconnect.
   *
   * @private
   */
  private resubscribeAll(): void {
    this.pendingSubscriptions.forEach((subscription, requestId) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws!.send(JSON.stringify(subscription));
        log.debug('WS resubscribed', { action: subscription.action, requestId });
      }
    });
  }

  /**
   * Close WebSocket connection and clear all subscriptions.
   */
  async close(): Promise<void> {
    this.pendingSubscriptions.clear();
    this.listeners.clear();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

/**
 * Unified Tradegent client for both REST and WebSocket communication.
 *
 * Transparent facade that:
 * - Routes requests to appropriate transport (REST for request/response, WS for push)
 * - Handles message envelope serialization/deserialization
 * - Manages authentication and correlation IDs
 * - Enables transport-agnostic calling code
 *
 * Usage:
 * ```typescript
 * const client = new TradegentClient({
 *   restConfig: { apiUrl, getAuthToken },
 *   wsConfig: { wsEndpoint, getAuthToken }
 * });
 *
 * // Request/response (REST)
 * const schedule = await client.request('patch_schedule', { id: 1, enabled: true });
 *
 * // Push subscription (WebSocket)
 * const unsubscribe = client.subscribe(
 *   'subscribe_prices',
 *   { tickers: ['NVDA'] },
 *   (event) => console.log(event.payload)
 * );
 * ```
 */
export class TradegentClient {
  private rest: TradegentRESTClient;
  private ws: TradegentWSClient;

  constructor(config: {
    restConfig: RESTClientConfig;
    wsConfig: WSClientConfig;
  }) {
    this.rest = new TradegentRESTClient(config.restConfig);
    this.ws = new TradegentWSClient(config.wsConfig);
  }

  /**
   * Send a request-response message via REST transport.
   * Use for user-initiated actions (create, update, read) and non-real-time queries.
   *
   * @param action Action identifier (e.g., 'patch_schedule')
   * @param payload Request payload
   * @param timeout Optional timeout in milliseconds
   * @returns Parsed response payload
   * @throws TradegentClientError if error response or network error
   *
   * Example:
   * ```typescript
   * const schedule = await client.request('patch_schedule', {
   *   schedule_id: 1,
   *   enabled: false
   * });
   * ```
   */
  async request<T = any, R = any>(
    action: string,
    payload?: T,
    timeout?: number
  ): Promise<R> {
    return this.rest.request<T, R>(action, payload, timeout);
  }

  /**
   * Subscribe to server push events via WebSocket transport.
   * Use for real-time or frequently-updated data streams.
   *
   * @param action Subscription action (e.g., 'subscribe_prices')
   * @param payload Subscription parameters
   * @param listener Event handler called for each pushed event
   * @returns Unsubscribe function to cancel subscription
   *
   * Example:
   * ```typescript
   * const unsubscribe = client.subscribe(
   *   'subscribe_prices',
   *   { tickers: ['NVDA', 'AAPL'] },
   *   (event) => {
   *     console.log('New price:', event.payload);
   *   }
   * );
   * // Later...
   * await unsubscribe();
   * ```
   */
  subscribe<T = any, E = any>(
    action: string,
    payload?: T,
    listener?: EventListener<E>
  ): () => Promise<void> {
    return this.ws.subscribe<T, E>(action, payload, listener);
  }

  /**
   * Close all connections and clean up resources.
   */
  async close(): Promise<void> {
    await this.ws.close();
  }
}

/**
 * Factory function to create a configured Tradegent client
 * using the browser's current environment.
 *
 * @param getAuthToken Function to retrieve current auth token
 * @returns Configured TradegentClient instance
 */
export function createTradegentClient(
  getAuthToken: () => Promise<string | null>
): TradegentClient {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';
  const wsEndpoint =
    typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/stream`
      : 'ws://localhost:8081/ws/stream';

  return new TradegentClient({
    restConfig: { apiUrl, getAuthToken },
    wsConfig: { wsEndpoint, getAuthToken },
  });
}
