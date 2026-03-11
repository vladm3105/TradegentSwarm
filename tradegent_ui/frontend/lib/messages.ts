/**
 * Unified message envelope for all Tradegent client-server communication.
 *
 * This module defines the common message format used across both WebSocket
 * (push/subscribe) and REST (request/response) transports. A single envelope
 * type enables:
 * - Consistent error handling across transports
 * - Shared request/response correlation
 * - Type-safe payloads with discriminated unions
 * - Easy serialization/deserialization
 *
 * Architecture:
 * - REST (stateless): HTTP request → TradegentMessage (request) → HTTP response (wrapped)
 * - WS (stateful): Send TradegentMessage (subscribe/request) → Receive events as TradegentMessage
 */

export type MessageType = 'request' | 'response' | 'subscription' | 'event' | 'error';

/**
 * Unified message envelope for all client-server communication.
 * Works across both REST and WebSocket transports.
 *
 * Usage:
 * ```typescript
 * // REST request
 * const req: TradegentMessage = {
 *   type: 'request',
 *   action: 'patch_schedule',
 *   request_id: generateUUID(),
 *   payload: { schedule_id: 1, enabled: false }
 * };
 *
 * // WS subscription
 * const sub: TradegentMessage = {
 *   type: 'subscription',
 *   action: 'subscribe_prices',
 *   request_id: generateUUID(),
 *   payload: { tickers: ['NVDA', 'AAPL'] }
 * };
 * ```
 */
export interface TradegentMessage<T = any> {
  /** Message type: request response/response for request-response, subscription/event for push */
  type: MessageType;

  /** Action identifier: specific operation (e.g., 'get_schedules', 'patch_schedule', 'subscribe_prices') */
  action: string;

  /** Optional unique request ID for correlation (UUID recommended) */
  request_id?: string;

  /** Message payload: action-specific data */
  payload?: T;

  /** ISO 8601 timestamp of message creation */
  timestamp?: number;

  /** Error details if type === 'error' */
  error?: TradegentError;
}

/**
 * Unified error response for all transports.
 *
 * Usage:
 * ```typescript
 * {
 *   type: 'error',
 *   action: 'patch_schedule',
 *   request_id: '123',
 *   error: {
 *     code: 'VALIDATION_ERROR',
 *     message: 'Schedule ID must be positive',
 *     details: { field: 'schedule_id', reason: 'positive' }
 *   }
 * }
 * ```
 */
export interface TradegentError {
  /** Machine-readable error code (VALIDATION_ERROR, NOT_FOUND, UNAUTHORIZED, SERVER_ERROR, etc.) */
  code: string;

  /** Human-readable error message */
  message: string;

  /** Optional action-specific error details */
  details?: Record<string, any>;
}

/**
 * Type-safe response marker for REST endpoints.
 *
 * Constrains the `type` discriminant to `'response'` so callers can narrow the
 * union returned by the server.  Response data lives in the inherited `payload`
 * field — not a separate property — so access it as `message.payload`.
 *
 * Error responses are represented as `TradegentMessage` with `type === 'error'`
 * and are handled before this type is applied in TradegentRESTClient.
 */
export interface TradegentResponse<T = any> extends TradegentMessage<T> {
  type: 'response';
}

/**
 * Type-safe event message for WebSocket push.
 * Server pushes these to subscribed clients.
 */
export interface TradegentEvent<T = any> extends TradegentMessage<T> {
  type: 'event';
}

/**
 * Type-safe subscription request for WebSocket.
 * Client sends these to subscribe to event streams.
 */
export interface TradegentSubscription<T = any> extends TradegentMessage<T> {
  type: 'subscription';
}

/**
 * Type-safe request message for REST or WS RPC.
 * Client sends these for request-response operations.
 */
export interface TradegentRequest<T = any> extends TradegentMessage<T> {
  type: 'request';
}

/**
 * Common actions across all screens.
 * Actions map to API endpoints or subscription channels.
 */
export const TRADEGENT_ACTIONS = {
  // Schedule management
  GET_SCHEDULES: 'get_schedules',
  PATCH_SCHEDULE: 'patch_schedule',
  RUN_SCHEDULE_NOW: 'run_schedule_now',
  GET_SCHEDULE_HISTORY: 'get_schedule_history',

  // Price/portfolio streaming
  SUBSCRIBE_PRICES: 'subscribe_prices',
  SUBSCRIBE_PORTFOLIO: 'subscribe_portfolio',
  SUBSCRIBE_ORDERS: 'subscribe_orders',

  // Dashboard metrics
  SUBSCRIBE_METRICS: 'subscribe_metrics',
  SUBSCRIBE_ALERTS: 'subscribe_alerts',

  // Generic operations
  UNSUBSCRIBE: 'unsubscribe',
} as const;

/**
 * Create a request message with correlation ID and timestamp.
 *
 * @param action Action identifier (e.g., 'get_schedules')
 * @param payload Action-specific payload
 * @param requestId Optional correlation ID (generated if not provided)
 * @returns TradegentRequest message
 */
export function createRequest<T = any>(
  action: string,
  payload?: T,
  requestId?: string
): TradegentRequest<T> {
  return {
    type: 'request',
    action,
    request_id: requestId || generateRequestId(),
    payload,
    timestamp: Date.now(),
  };
}

/**
 * Create a subscription message for WebSocket push.
 *
 * @param action Subscription action (e.g., 'subscribe_prices')
 * @param payload Subscription parameters (e.g., { tickers: [...] })
 * @param requestId Optional correlation ID
 * @returns TradegentSubscription message
 */
export function createSubscription<T = any>(
  action: string,
  payload?: T,
  requestId?: string
): TradegentSubscription<T> {
  return {
    type: 'subscription',
    action,
    request_id: requestId || generateRequestId(),
    payload,
    timestamp: Date.now(),
  };
}

/**
 * Create an error response message.
 *
 * @param action Related action
 * @param code Error code (VALIDATION_ERROR, NOT_FOUND, etc.)
 * @param message Human-readable message
 * @param requestId Correlation ID
 * @param details Optional action-specific details
 * @returns TradegentMessage with error
 */
export function createError(
  action: string,
  code: string,
  message: string,
  requestId?: string,
  details?: Record<string, any>
): TradegentMessage {
  return {
    type: 'error',
    action,
    request_id: requestId,
    error: {
      code,
      message,
      details,
    },
    timestamp: Date.now(),
  };
}

/**
 * Generate a unique request ID for correlation.
 * Uses crypto.randomUUID if available, falls back to timestamp-based ID.
 *
 * @returns UUID-like string
 */
export function generateRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
