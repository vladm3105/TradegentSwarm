// API response types

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  mcp_servers: {
    [key: string]: {
      status: 'healthy' | 'unhealthy';
      latency_ms?: number;
      error?: string;
    };
  };
}

export interface ChatRequest {
  content: string;
  session_id?: string;
  async?: boolean;
}

export interface ChatResponse {
  type: 'a2ui';
  text: string;
  components: unknown[];
  session_id: string;
  correlation_id: string;
}

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress?: number;
  result?: unknown;
  error?: string;
  started_at: string;
  completed_at?: string;
}

export interface DashboardPnL {
  daily: Array<{
    date: string;
    pnl: number;
    cumulative: number;
  }>;
  weekly: Array<{
    week: string;
    pnl: number;
    trades: number;
    win_rate: number;
  }>;
  monthly: Array<{
    month: string;
    pnl: number;
    trades: number;
    win_rate: number;
  }>;
}

export interface DashboardPerformance {
  top_performers: Array<{
    ticker: string;
    pnl: number;
    pnl_pct: number;
    trades: number;
    win_rate: number;
  }>;
  worst_performers: Array<{
    ticker: string;
    pnl: number;
    pnl_pct: number;
    trades: number;
    win_rate: number;
  }>;
}

export interface DashboardAnalysisQuality {
  gate_pass_rate: number;
  recommendation_distribution: {
    [key: string]: number;
  };
  accuracy_by_confidence: Array<{
    confidence_bucket: string;
    accuracy: number;
    count: number;
  }>;
}

export interface DashboardServiceHealth {
  services: Array<{
    name: string;
    status: 'healthy' | 'degraded' | 'unhealthy';
    latency_ms?: number;
    uptime_pct?: number;
  }>;
  rag_stats: {
    document_count: number;
    chunk_count: number;
  };
  graph_stats: {
    node_count: number;
    edge_count: number;
  };
  error_rates: {
    last_hour: number;
    last_day: number;
  };
}

export interface DashboardWatchlistSummary {
  total: number;
  by_status: {
    active: number;
    triggered: number;
    expired: number;
    invalidated: number;
  };
  by_priority: {
    high: number;
    medium: number;
    low: number;
  };
  expiring_soon: Array<{
    ticker: string;
    expires: string;
    trigger_type: string;
  }>;
}

export interface DashboardStats {
  total_pnl: number;
  total_pnl_pct: number;
  open_positions: number;
  total_market_value: number;
  today_pnl: number;
  today_pnl_pct: number;
  win_rate: number;
  total_trades: number;
  active_analyses: number;
  watchlist_count: number;
}

// WebSocket message types
export interface WSMessage {
  type: 'message' | 'subscribe' | 'unsubscribe' | 'ping' | 'pong';
  content?: string;
  task_id?: string;
  session_id?: string;
  async?: boolean;
}

export interface WSResponse {
  type: 'response' | 'progress' | 'complete' | 'task_created' | 'error' | 'pong';
  // Response fields (type: 'response')
  success?: boolean;
  text?: string;
  a2ui?: unknown;  // A2UIResponse object
  // Progress fields (type: 'progress')
  task_id?: string;
  progress?: number;
  message?: string;
  state?: string;
  // Completion fields (type: 'complete')
  result?: {
    success?: boolean;
    text?: string;
    a2ui?: unknown;
    error?: string | null;
  };
  // Error fields (type: 'error')
  error?: string;
  code?: string;  // Error code for specific error types (e.g., AUTH_ERROR)
  // Deprecated - kept for backwards compatibility
  data?: unknown;
}
