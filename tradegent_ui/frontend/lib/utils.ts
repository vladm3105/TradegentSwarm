import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format currency with sign
 */
export function formatCurrency(
  value: number,
  options?: { showSign?: boolean; decimals?: number }
): string {
  const { showSign = false, decimals = 2 } = options ?? {};
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(value));

  if (showSign && value !== 0) {
    return value > 0 ? `+${formatted}` : `-${formatted}`;
  }
  return value < 0 ? `-${formatted}` : formatted;
}

/**
 * Format percentage with sign
 */
export function formatPercent(
  value: number,
  options?: { showSign?: boolean; decimals?: number }
): string {
  const { showSign = true, decimals = 2 } = options ?? {};
  const formatted = `${Math.abs(value).toFixed(decimals)}%`;

  if (showSign && value !== 0) {
    return value > 0 ? `+${formatted}` : `-${formatted}`;
  }
  return value < 0 ? `-${formatted}` : formatted;
}

/**
 * Format large numbers with abbreviations (K, M, B)
 */
export function formatCompact(value: number): string {
  if (Math.abs(value) >= 1e9) {
    return `${(value / 1e9).toFixed(1)}B`;
  }
  if (Math.abs(value) >= 1e6) {
    return `${(value / 1e6).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1e3) {
    return `${(value / 1e3).toFixed(1)}K`;
  }
  return value.toString();
}

/**
 * Format date for display
 */
export function formatDate(
  date: Date | string,
  options?: { includeTime?: boolean }
): string {
  const { includeTime = false } = options ?? {};
  const d = typeof date === 'string' ? new Date(date) : date;

  if (includeTime) {
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(d);
}

/**
 * Get P&L color class based on value
 */
export function getPnlColor(value: number): string {
  if (value > 0) return 'pnl-positive';
  if (value < 0) return 'pnl-negative';
  return 'text-muted-foreground';
}

/**
 * Get recommendation badge class
 */
export function getRecommendationClass(
  recommendation: string
): string {
  const normalized = recommendation.toLowerCase().replace(/_/g, '-');
  const map: Record<string, string> = {
    'strong-buy': 'rec-strong-buy',
    'strong_buy': 'rec-strong-buy',
    buy: 'rec-buy',
    watch: 'rec-watch',
    'no-position': 'rec-no-position',
    'no_position': 'rec-no-position',
    avoid: 'rec-avoid',
  };
  return map[normalized] ?? 'rec-no-position';
}

/**
 * Get gate result badge class
 */
export function getGateClass(result: string): string {
  const normalized = result.toLowerCase();
  const map: Record<string, string> = {
    pass: 'gate-pass',
    marginal: 'gate-marginal',
    fail: 'gate-fail',
  };
  return map[normalized] ?? 'gate-fail';
}

/**
 * Get analysis status badge class
 */
export function getStatusClass(status: unknown): string {
  if (typeof status !== 'string' || !status.trim()) {
    return 'text-muted-foreground border-muted';
  }

  const normalized = status.toLowerCase();
  if (normalized.startsWith('inactive_')) {
    return 'text-red-700 border-red-300 bg-red-50 dark:text-red-400 dark:border-red-800 dark:bg-red-950/30';
  }

  switch (normalized) {
    case 'completed':
    case 'active':   return 'text-green-700 border-green-300 bg-green-50 dark:text-green-400 dark:border-green-800 dark:bg-green-950/30';
    case 'expired':  return 'text-muted-foreground border-muted';
    case 'declined': return 'text-red-700 border-red-300 bg-red-50 dark:text-red-400 dark:border-red-800 dark:bg-red-950/30';
    case 'error':    return 'text-orange-700 border-orange-300 bg-orange-50 dark:text-orange-400 dark:border-orange-800 dark:bg-orange-950/30';
    default:         return 'text-muted-foreground border-muted';
  }
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
    }, wait);
  };
}

/**
 * Generate a unique ID
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * Sleep utility for async operations
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Safely parse JSON with fallback
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}

/**
 * Check if running on client side
 */
export function isClient(): boolean {
  return typeof window !== 'undefined';
}

/**
 * Get trading hours status
 */
export function getMarketStatus(): {
  isOpen: boolean;
  status: 'pre-market' | 'open' | 'after-hours' | 'closed';
  nextOpen?: Date;
} {
  const now = new Date();
  const et = new Date(
    now.toLocaleString('en-US', { timeZone: 'America/New_York' })
  );
  const day = et.getDay();
  const hour = et.getHours();
  const minute = et.getMinutes();
  const time = hour * 60 + minute;

  // Weekend
  if (day === 0 || day === 6) {
    return { isOpen: false, status: 'closed' };
  }

  // Pre-market: 4:00 AM - 9:30 AM ET
  if (time >= 240 && time < 570) {
    return { isOpen: false, status: 'pre-market' };
  }

  // Regular hours: 9:30 AM - 4:00 PM ET
  if (time >= 570 && time < 960) {
    return { isOpen: true, status: 'open' };
  }

  // After hours: 4:00 PM - 8:00 PM ET
  if (time >= 960 && time < 1200) {
    return { isOpen: false, status: 'after-hours' };
  }

  // Closed (8:00 PM - 4:00 AM ET)
  return { isOpen: false, status: 'closed' };
}
