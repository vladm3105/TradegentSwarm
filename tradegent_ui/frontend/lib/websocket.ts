import { getSession } from 'next-auth/react';
import type { WSMessage, WSResponse } from '@/types/api';
import { generateId } from '@/lib/utils';
import { createLogger } from '@/lib/logger';
import {
  createAuthenticatedWebSocket,
  resolveWebSocketEndpoint,
} from '@/lib/websocket-auth';

const log = createLogger('websocket');
const TRACE_BACKEND_INTERACTIONS = process.env.NODE_ENV === 'development' || process.env.NEXT_PUBLIC_DEBUG === 'true';

export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnecting';

export interface WebSocketOptions {
  url?: string;
  onMessage?: (data: WSResponse) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  onAuthError?: () => void;
  maxReconnectAttempts?: number;
  reconnectDelay?: number;
  maxReconnectDelay?: number;
}

const DEFAULT_OPTIONS: Required<
  Omit<WebSocketOptions, 'onMessage' | 'onConnect' | 'onDisconnect' | 'onError' | 'onAuthError'>
> = {
  // URL is intentionally left empty here; resolveWebSocketEndpoint() is called
  // lazily inside connectInternal() so it can read window.location in the browser.
  url: '',
  maxReconnectAttempts: 10,
  reconnectDelay: 1000,
  maxReconnectDelay: 30000,
};

export class TradegentWebSocket {
  private ws: WebSocket | null = null;
  private options: Required<WebSocketOptions>;
  private reconnectAttempts = 0;
  private tokenRetries = 0; // separate counter for "no session token" retries
  // Set by disconnect() and checked at key points in connectInternal() to abort
  // a connect attempt that was superseded by a disconnect call.
  private _disconnectCalled = false;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private connectTimeout: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private connectPromise: Promise<void> | null = null;
  private sessionId: string;
  private state: ConnectionState = 'disconnected';
  private messageQueue: WSMessage[] = [];
  private accessToken: string | null = null;

  private resolveConnectionCandidates(): string[] {
    // Resolve lazily so window.location is available in the browser.
    const url = this.options.url || resolveWebSocketEndpoint(process.env.NEXT_PUBLIC_WS_URL, '/ws/agent');
    try {
      const parsed = new URL(url);
      const primary = parsed.toString();
      const candidates = [primary];

      if (parsed.hostname === 'localhost') {
        const ipv4 = new URL(primary);
        ipv4.hostname = '127.0.0.1';
        candidates.push(ipv4.toString());
      } else if (parsed.hostname === '127.0.0.1') {
        const local = new URL(primary);
        local.hostname = 'localhost';
        candidates.push(local.toString());
      }

      return candidates;
    } catch {
      return [url];
    }
  }

  private clearConnectTimeout(): void {
    if (this.connectTimeout) {
      clearTimeout(this.connectTimeout);
      this.connectTimeout = null;
    }
  }

  constructor(options: WebSocketOptions = {}) {
    this.options = {
      ...DEFAULT_OPTIONS,
      onMessage: options.onMessage ?? (() => {}),
      onConnect: options.onConnect ?? (() => {}),
      onDisconnect: options.onDisconnect ?? (() => {}),
      onError: options.onError ?? (() => {}),
      onAuthError: options.onAuthError ?? (() => {}),
      ...options,
    };
    this.sessionId = generateId();
  }

  /**
   * Replace event callbacks on an existing instance without touching other options.
   *
   * The singleton is sometimes created by WebSocketStatus (rendered in <Header>,
   * which mounts before <ChatPanel>) with no callbacks. When use-websocket.ts
   * later calls getWebSocket(options), this method is invoked so the real
   * onConnect / onAuthError / onDisconnect handlers are wired in before any
   * connection attempt is made.
   */
  public updateCallbacks(options: WebSocketOptions): void {
    if (options.onMessage !== undefined) this.options.onMessage = options.onMessage;
    if (options.onConnect !== undefined) this.options.onConnect = options.onConnect;
    if (options.onDisconnect !== undefined) this.options.onDisconnect = options.onDisconnect;
    if (options.onError !== undefined) this.options.onError = options.onError;
    if (options.onAuthError !== undefined) this.options.onAuthError = options.onAuthError;
  }

  /**
   * Get access token from current NextAuth session.
   * Returns null if no session is available (triggers retry logic).
   */
  private async getAccessToken(): Promise<string | null> {
    const session = await getSession();
    return (session?.accessToken as string | undefined) ?? null;
  }

  public async connect(): Promise<void> {
    // Reset disconnect flag — caller wants a fresh connection.
    this._disconnectCalled = false;

    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      log.debug('WebSocket already connected');
      return;
    }

    if (this.connectPromise) {
      return this.connectPromise;
    }

    this.connectPromise = this.connectInternal();
    try {
      await this.connectPromise;
    } finally {
      this.connectPromise = null;
    }
  }

  private async connectInternal(): Promise<void> {

    // Get access token
    this.accessToken = await this.getAccessToken();
    const preflightContext = {
      hasAccessToken: !!this.accessToken,
      reconnectAttempts: this.reconnectAttempts,
      state: this.state,
    };
    if (TRACE_BACKEND_INTERACTIONS) {
      log.info('WebSocket connect preflight', preflightContext);
    } else {
      log.debug('WebSocket connect preflight', preflightContext);
    }

    if (!this.accessToken) {
      // Token may be temporarily unavailable (e.g. session cookie race on first
      // load). Allow up to 3 retries with back-off before forcing auth recovery.
      // Uses tokenRetries (not reconnectAttempts) so the network reconnect
      // counter is not polluted and URL rotation stays predictable.
      if (this.tokenRetries < 3) {
        log.warn('No access token available, will retry after back-off', {
          tokenRetries: this.tokenRetries,
        });
        this.state = 'reconnecting';
        this.tokenRetries++;
        const delay = 1000 * this.tokenRetries;
        this.reconnectTimeout = setTimeout(() => {
          void this.connectInternal();
        }, delay);
        return;
      }
      log.warn('No access token after retries, forcing auth recovery');
      this.state = 'disconnected';
      this.clearReconnectTimeout();
      this.options.onAuthError();
      return;
    }

    // Token is available — reset any attempt counter that was accumulated
    // during the "no token" retry path so that URL rotation and backoff delays
    // start fresh for this real connection attempt.
    this.tokenRetries = 0;

    // Abort if disconnect() was called while we were awaiting the token.
    if (this._disconnectCalled) {
      log.warn('WebSocket connect aborted — disconnect was requested during token fetch');
      this.state = 'disconnected';
      return;
    }

    const connectionCandidates = this.resolveConnectionCandidates();
    const connectionUrl = connectionCandidates[this.reconnectAttempts % connectionCandidates.length];

    log.info('WebSocket connecting', {
      url: connectionUrl,
      candidates: connectionCandidates,
      sessionId: this.sessionId,
      hasToken: !!this.accessToken,
      reconnectAttempts: this.reconnectAttempts,
    });

    this.state = 'connecting';
    this.clearConnectTimeout();
    this.ws = createAuthenticatedWebSocket(connectionUrl, this.accessToken);
    this.connectTimeout = setTimeout(() => {
      if (this.ws?.readyState === WebSocket.CONNECTING) {
        log.warn('WebSocket connect timeout', {
          sessionId: this.sessionId,
          url: connectionUrl,
        });
        this.ws.close();
      }
    }, 8000);

    this.ws.onopen = () => {
      this.clearConnectTimeout();

      // If disconnect() was called while the WS was still connecting, close the
      // connection immediately rather than letting it run with stale state.
      if (this._disconnectCalled) {
        log.warn('WebSocket opened but disconnect was requested — closing immediately');
        this.ws?.close();
        this.ws = null;
        this.state = 'disconnected';
        return;
      }

      log.info('WebSocket connected', { sessionId: this.sessionId });
      this.state = 'connected';
      this.reconnectAttempts = 0;
      this.tokenRetries = 0;
      this.options.onConnect();
      this.startPingInterval();
      this.flushMessageQueue();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSResponse;

        // Handle auth errors
        if (data.type === 'error' && data.code === 'AUTH_ERROR') {
          log.error('WebSocket auth error', { error: data.error });
          this.options.onAuthError();
          return;
        }

        if (data.type === 'pong') {
          return; // Ignore pong responses
        }

        log.debug('WebSocket message received', { type: data.type });
        this.options.onMessage(data);
      } catch (error) {
        log.error('Failed to parse WebSocket message', { error: String(error) });
      }
    };

    this.ws.onerror = (event) => {
      // ErrorEvent.message is often empty for WS errors in browsers; log what's
      // available so the console shows the URL and session at minimum.
      const detail = event instanceof ErrorEvent ? event.message : undefined;
      log.error('WebSocket error', {
        sessionId: this.sessionId,
        url: connectionUrl,
        detail: detail || '(no message — check network tab for close frame)',
      });
      this.options.onError(new Error(detail || 'WebSocket error'));
    };

    this.ws.onclose = (event) => {
      log.warn('WebSocket disconnected', {
        sessionId: this.sessionId,
        code: event.code,
        reason: event.reason,
      });

      this.clearConnectTimeout();
      this.state = 'disconnected';
      this.stopPingInterval();
      this.options.onDisconnect();

      // Handle auth-related close codes
      if (event.code === 4001 || event.code === 4003 || event.code === 4401 || event.code === 4403 || event.code === 1008) {
        log.error('WebSocket closed due to auth error', {
          code: event.code,
          reason: event.reason,
          reconnectAttempts: this.reconnectAttempts,
        });
        this.clearReconnectTimeout();
        this.options.onAuthError();
        return; // Don't reconnect on auth errors
      }

      this.attemptReconnect();
    };
  }

  public disconnect(): void {
    this._disconnectCalled = true;
    this.reconnectAttempts = this.options.maxReconnectAttempts; // Prevent reconnection
    this.tokenRetries = 0;
    this.clearReconnectTimeout();
    this.clearConnectTimeout();
    this.stopPingInterval();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.state = 'disconnected';
  }

  public send(message: WSMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      // Queue message for when connection is restored
      this.messageQueue.push(message);
      if (this.state === 'disconnected') {
        this.connect();
      }
    }
  }

  public sendChatMessage(content: string, async = false): void {
    this.send({
      type: 'message',
      content,
      session_id: this.sessionId,
      async,
    });
  }

  public subscribeToTask(taskId: string): void {
    this.send({
      type: 'subscribe',
      task_id: taskId,
    });
  }

  public unsubscribeFromTask(taskId: string): void {
    this.send({
      type: 'unsubscribe',
      task_id: taskId,
    });
  }

  public getState(): ConnectionState {
    return this.state;
  }

  public getSessionId(): string {
    return this.sessionId;
  }

  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Refresh the access token and reconnect
   */
  public async refreshToken(): Promise<void> {
    log.info('Refreshing WebSocket token');
    this.disconnect();
    this.reconnectAttempts = 0;
    await this.connect();
  }

  private attemptReconnect(): void {
    this.clearReconnectTimeout();

    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      log.error('Max reconnect attempts reached', {
        attempts: this.reconnectAttempts,
        max: this.options.maxReconnectAttempts,
      });
      return;
    }

    this.state = 'reconnecting';
    this.reconnectAttempts++;

    // Exponential backoff with jitter
    const delay = Math.min(
      this.options.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1) +
        Math.random() * 1000,
      this.options.maxReconnectDelay
    );

    log.info('WebSocket reconnecting', {
      attempt: this.reconnectAttempts,
      max: this.options.maxReconnectAttempts,
      delayMs: Math.round(delay),
      sessionId: this.sessionId,
    });

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  private startPingInterval(): void {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' });
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0 && this.isConnected()) {
      const message = this.messageQueue.shift();
      if (message) {
        this.send(message);
      }
    }
  }
}

// Singleton instance
let wsInstance: TradegentWebSocket | null = null;

/**
 * Get (or create) the WebSocket singleton.
 *
 * When called WITHOUT options the first time (e.g. from WebSocketStatus in
 * <Header>), a bare instance with no-op callbacks is created.  When called
 * WITH options later (e.g. from use-websocket.ts after ChatPanel mounts), the
 * real callbacks are applied via updateCallbacks() so no handlers are lost.
 */
export function getWebSocket(options?: WebSocketOptions): TradegentWebSocket {
  if (!wsInstance) {
    wsInstance = new TradegentWebSocket(options);
  } else if (options) {
    // Singleton already exists — update callbacks so the later caller's
    // handlers (onConnect, onAuthError, …) overwrite the no-op defaults.
    wsInstance.updateCallbacks(options);
  }
  return wsInstance;
}

/**
 * Returns the existing singleton if it has been created, or null.
 * Safe to call before use-websocket.ts has mounted; does NOT create a bare
 * singleton the way getWebSocket() does.
 */
export function getWebSocketIfExists(): TradegentWebSocket | null {
  return wsInstance;
}

export function resetWebSocket(): void {
  if (wsInstance) {
    wsInstance.disconnect();
    wsInstance = null;
  }
}
