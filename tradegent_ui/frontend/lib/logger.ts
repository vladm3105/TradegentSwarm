/**
 * Frontend logging utility with structured logging support.
 * Logs to console in development and can be extended to send to backend.
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  [key: string]: unknown;
}

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: LogContext;
  component?: string;
  correlationId?: string;
}

class Logger {
  private static instance: Logger;
  private correlationId: string | null = null;
  private component: string = 'frontend';
  private isDebugEnabled: boolean;
  private a2uiDebugEnabled: boolean;

  private constructor() {
    this.isDebugEnabled =
      typeof window !== 'undefined' &&
      (process.env.NEXT_PUBLIC_DEBUG === 'true' ||
        localStorage.getItem('debug') === 'true');

    // Initialize A2UI debug from localStorage
    this.a2uiDebugEnabled =
      typeof window !== 'undefined' &&
      localStorage.getItem('a2ui_debug') === 'true';
  }

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  setCorrelationId(id: string): void {
    this.correlationId = id;
  }

  setComponent(name: string): void {
    this.component = name;
  }

  enableDebug(): void {
    this.isDebugEnabled = true;
    if (typeof window !== 'undefined') {
      localStorage.setItem('debug', 'true');
    }
  }

  disableDebug(): void {
    this.isDebugEnabled = false;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('debug');
    }
  }

  private formatEntry(level: LogLevel, message: string, context?: LogContext): LogEntry {
    return {
      timestamp: new Date().toISOString(),
      level,
      message,
      context,
      component: this.component,
      correlationId: this.correlationId || undefined,
    };
  }

  // Core emit — accepts explicit component so createLogger() can bind its own
  // component name without touching shared singleton state.
  logForComponent(component: string, level: LogLevel, message: string, context?: LogContext): void {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      context,
      component,
      correlationId: this.correlationId || undefined,
    };

    const prefix = `[${entry.timestamp}] [${level.toUpperCase()}]`;
    const componentPrefix = component ? `[${component}]` : '';
    const correlationPrefix = entry.correlationId ? `[${entry.correlationId.slice(0, 8)}]` : '';
    const fullPrefix = `${prefix}${componentPrefix}${correlationPrefix}`;

    switch (level) {
      case 'debug':
        if (this.isDebugEnabled) {
          console.debug(fullPrefix, message, context || '');
        }
        break;
      case 'info':
        console.info(fullPrefix, message, context || '');
        break;
      case 'warn':
        console.warn(fullPrefix, message, context || '');
        break;
      case 'error':
        console.error(fullPrefix, message, context || '');
        break;
    }

    // Store in session for debugging (last 100 entries)
    if (typeof window !== 'undefined') {
      try {
        const logs = JSON.parse(sessionStorage.getItem('app_logs') || '[]');
        logs.push(entry);
        if (logs.length > 100) {
          logs.shift();
        }
        sessionStorage.setItem('app_logs', JSON.stringify(logs));
      } catch {
        // Ignore storage errors
      }
    }
  }

  private log(level: LogLevel, message: string, context?: LogContext): void {
    this.logForComponent(this.component, level, message, context);
  }

  debug(message: string, context?: LogContext): void {
    this.log('debug', message, context);
  }

  info(message: string, context?: LogContext): void {
    this.log('info', message, context);
  }

  warn(message: string, context?: LogContext): void {
    this.log('warn', message, context);
  }

  error(message: string, context?: LogContext): void {
    this.log('error', message, context);
  }

  // Convenience method for logging API calls
  api(method: string, url: string, context?: LogContext): void {
    this.debug(`API ${method} ${url}`, context);
  }

  // Convenience method for logging WebSocket events
  ws(event: string, context?: LogContext): void {
    this.debug(`WS ${event}`, context);
  }

  // Convenience method for logging user actions
  action(action: string, context?: LogContext): void {
    this.info(`Action: ${action}`, context);
  }

  // ============ A2UI Logging Methods ============

  /** Log A2UI response received from backend */
  a2uiReceived(response: unknown, context?: LogContext): void {
    const a2ui = response as { type?: string; text?: string; components?: unknown[] };
    this.debug('A2UI response received', {
      type: a2ui?.type,
      hasText: !!a2ui?.text,
      textLength: a2ui?.text?.length ?? 0,
      componentCount: a2ui?.components?.length ?? 0,
      componentTypes: a2ui?.components?.map((c: unknown) => (c as { type?: string })?.type) ?? [],
      ...context,
    });
  }

  /** Log A2UI validation result */
  a2uiValidated(valid: boolean, error?: string, context?: LogContext): void {
    if (valid) {
      this.debug('A2UI validation passed', context);
    } else {
      this.warn('A2UI validation failed', { error, ...context });
    }
  }

  /** Log A2UI component render with timing */
  a2uiRender(componentType: string, success: boolean, renderMs?: number, error?: string, context?: LogContext): void {
    if (success) {
      this.debug(`A2UI render: ${componentType}`, { renderMs, ...context });
    } else {
      this.error(`A2UI render failed: ${componentType}`, { error, renderMs, ...context });
    }
  }

  /** Enable A2UI debug mode for full payload logging */
  enableA2UIDebug(): void {
    this.a2uiDebugEnabled = true;
    if (typeof window !== 'undefined') {
      localStorage.setItem('a2ui_debug', 'true');
    }
    this.info('A2UI debug mode enabled');
  }

  /** Disable A2UI debug mode */
  disableA2UIDebug(): void {
    this.a2uiDebugEnabled = false;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('a2ui_debug');
    }
    this.info('A2UI debug mode disabled');
  }

  /** Log full A2UI payload (only in A2UI debug mode) */
  a2uiPayload(label: string, payload: unknown): void {
    if (this.a2uiDebugEnabled) {
      this.debug(`A2UI payload: ${label}`, { payload });
    }
  }

  /** Check if A2UI debug is enabled */
  isA2UIDebugEnabled(): boolean {
    return this.a2uiDebugEnabled;
  }

  // Get stored logs for debugging
  getLogs(): LogEntry[] {
    if (typeof window === 'undefined') return [];
    try {
      return JSON.parse(sessionStorage.getItem('app_logs') || '[]');
    } catch {
      return [];
    }
  }

  // Clear stored logs
  clearLogs(): void {
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('app_logs');
    }
  }
}

// Interface returned by createLogger — component is bound via closure,
// so multiple modules each get their own component label without interfering.
export interface ComponentLogger {
  debug(message: string, context?: LogContext): void;
  info(message: string, context?: LogContext): void;
  warn(message: string, context?: LogContext): void;
  error(message: string, context?: LogContext): void;
  ws(event: string, context?: LogContext): void;
  api(method: string, url: string, context?: LogContext): void;
  action(action: string, context?: LogContext): void;
}

// Export singleton instance
export const logger = Logger.getInstance();

// Export function to create component-specific logger.
// Returns a plain object that binds the component name via closure — does NOT
// mutate the shared Logger singleton, so multiple callers with different
// component names are fully isolated from each other.
export function createLogger(component: string): ComponentLogger {
  const singleton = Logger.getInstance();
  return {
    debug: (msg, ctx) => singleton.logForComponent(component, 'debug', msg, ctx),
    info:  (msg, ctx) => singleton.logForComponent(component, 'info',  msg, ctx),
    warn:  (msg, ctx) => singleton.logForComponent(component, 'warn',  msg, ctx),
    error: (msg, ctx) => singleton.logForComponent(component, 'error', msg, ctx),
    ws:     (event, ctx) => singleton.logForComponent(component, 'debug', `WS ${event}`, ctx),
    api:    (method, url, ctx) => singleton.logForComponent(component, 'debug', `API ${method} ${url}`, ctx),
    action: (action, ctx) => singleton.logForComponent(component, 'info', `Action: ${action}`, ctx),
  };
}

// Type declaration for window extensions
interface WindowWithDebug {
  __logger: Logger;
  __a2uiDebug: {
    enable: () => void;
    disable: () => void;
    isEnabled: () => boolean;
    getLogs: () => LogEntry[];
  };
}

// Make logger available globally for debugging
if (typeof window !== 'undefined') {
  const win = window as unknown as WindowWithDebug;
  win.__logger = logger;
  win.__a2uiDebug = {
    enable: () => logger.enableA2UIDebug(),
    disable: () => logger.disableA2UIDebug(),
    isEnabled: () => logger.isA2UIDebugEnabled(),
    getLogs: () => logger.getLogs().filter(l => l.message.includes('A2UI')),
  };
}
