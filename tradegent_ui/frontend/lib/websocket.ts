import { getSession } from 'next-auth/react';
import type { WSMessage, WSResponse } from '@/types/api';
import { generateId } from '@/lib/utils';
import { createLogger } from '@/lib/logger';

const log = createLogger('websocket');

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
  url: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8081/ws/agent',
  maxReconnectAttempts: 10,
  reconnectDelay: 1000,
  maxReconnectDelay: 30000,
};

export class TradegentWebSocket {
  private ws: WebSocket | null = null;
  private options: Required<WebSocketOptions>;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private sessionId: string;
  private state: ConnectionState = 'disconnected';
  private messageQueue: WSMessage[] = [];
  private accessToken: string | null = null;

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
   * Get access token from session
   */
  private async getAccessToken(): Promise<string | null> {
    try {
      const session = await getSession();
      return session?.accessToken || null;
    } catch (error) {
      log.error('Failed to get access token', { error: String(error) });
      return null;
    }
  }

  /**
   * Build WebSocket URL with authentication token
   */
  private buildAuthenticatedUrl(token: string | null): string {
    const url = new URL(this.options.url);

    // Add token as query parameter for WebSocket auth
    if (token) {
      url.searchParams.set('token', token);
    }

    return url.toString();
  }

  public async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      log.debug('WebSocket already connected');
      return;
    }

    // Get access token
    this.accessToken = await this.getAccessToken();

    if (!this.accessToken) {
      log.warn('No access token available, attempting connection without auth');
    }

    const authenticatedUrl = this.buildAuthenticatedUrl(this.accessToken);

    log.info('WebSocket connecting', {
      url: this.options.url,
      sessionId: this.sessionId,
      hasToken: !!this.accessToken,
    });

    this.state = 'connecting';
    this.ws = new WebSocket(authenticatedUrl);

    this.ws.onopen = () => {
      log.info('WebSocket connected', { sessionId: this.sessionId });
      this.state = 'connected';
      this.reconnectAttempts = 0;
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

    this.ws.onerror = (_event) => {
      log.error('WebSocket error');
      this.options.onError(new Error('WebSocket error'));
    };

    this.ws.onclose = (event) => {
      log.warn('WebSocket disconnected', {
        sessionId: this.sessionId,
        code: event.code,
        reason: event.reason,
      });

      this.state = 'disconnected';
      this.stopPingInterval();
      this.options.onDisconnect();

      // Handle auth-related close codes
      if (event.code === 4001 || event.code === 4003) {
        log.error('WebSocket closed due to auth error', { code: event.code });
        this.options.onAuthError();
        return; // Don't reconnect on auth errors
      }

      this.attemptReconnect();
    };
  }

  public disconnect(): void {
    this.reconnectAttempts = this.options.maxReconnectAttempts; // Prevent reconnection
    this.clearReconnectTimeout();
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

export function getWebSocket(options?: WebSocketOptions): TradegentWebSocket {
  if (!wsInstance) {
    wsInstance = new TradegentWebSocket(options);
  }
  return wsInstance;
}

export function resetWebSocket(): void {
  if (wsInstance) {
    wsInstance.disconnect();
    wsInstance = null;
  }
}
