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

  private constructor() {
    this.isDebugEnabled =
      typeof window !== 'undefined' &&
      (process.env.NEXT_PUBLIC_DEBUG === 'true' ||
        localStorage.getItem('debug') === 'true');
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

  private log(level: LogLevel, message: string, context?: LogContext): void {
    const entry = this.formatEntry(level, message, context);

    // Format for console
    const prefix = `[${entry.timestamp}] [${level.toUpperCase()}]`;
    const componentPrefix = entry.component ? `[${entry.component}]` : '';
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

// Export singleton instance
export const logger = Logger.getInstance();

// Export function to create component-specific logger
export function createLogger(component: string): Logger {
  const log = Logger.getInstance();
  log.setComponent(component);
  return log;
}

// Make logger available globally for debugging
if (typeof window !== 'undefined') {
  (window as unknown as { __logger: Logger }).__logger = logger;
}
