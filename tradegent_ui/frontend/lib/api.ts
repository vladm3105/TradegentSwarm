import { getSession } from 'next-auth/react';
import type {
  HealthResponse,
  ChatRequest,
  ChatResponse,
  TaskStatus,
  DashboardStats,
  DashboardPnL,
  DashboardPerformance,
  DashboardAnalysisQuality,
  DashboardServiceHealth,
  DashboardWatchlistSummary,
} from '@/types/api';
import type { GraphStats, GraphContext, GraphData } from '@/types/graph';

// Re-export types for consumers
export type {
  DashboardStats,
  DashboardPnL,
  DashboardPerformance,
  DashboardAnalysisQuality,
  DashboardServiceHealth,
  DashboardWatchlistSummary,
};
import { createLogger } from '@/lib/logger';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';
const log = createLogger('api');
let sessionLookupCount = 0;
const TRACE_BACKEND_INTERACTIONS = process.env.NODE_ENV === 'development' || process.env.NEXT_PUBLIC_DEBUG === 'true';

function createRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `api-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function buildApiUrl(endpoint: string): string {
  // In the browser, always use the Next.js proxy route to avoid
  // direct localhost calls failing in remote/forwarded sessions.
  if (typeof window !== 'undefined') {
    return `/api/orchestrator?path=${encodeURIComponent(endpoint)}`;
  }
  return `${API_URL}${endpoint}`;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Get authorization headers with Bearer token
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // Get session with access token - wrap in try/catch to prevent redirect issues
  try {
    sessionLookupCount += 1;
    const startedAt = performance.now();
    const session = await getSession();
    const duration = Math.round(performance.now() - startedAt);
    if (sessionLookupCount <= 10 || sessionLookupCount % 25 === 0) {
      const logPayload = {
        sessionLookupCount,
        hasSession: !!session,
        hasAccessToken: !!session?.accessToken,
        duration,
      };
      if (TRACE_BACKEND_INTERACTIONS) {
        log.info('Session lookup for API auth headers', logPayload);
      } else {
        log.debug('Session lookup for API auth headers', logPayload);
      }
    }
    if (session?.accessToken) {
      headers['Authorization'] = `Bearer ${session.accessToken}`;
    }
  } catch (error) {
    // Log but don't throw - allow request to proceed without auth header
    // The backend will return 401 if auth is required
    log.warn('Failed to get session for auth headers', { error: String(error) });
  }

  return headers;
}

/**
 * Fetch API with authentication
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = buildApiUrl(endpoint);
  const method = options?.method || 'GET';
  const startTime = performance.now();
  const requestId = createRequestId();

  log.api(method, endpoint, { requestId, url });

  try {
    // Get auth headers
    const authHeaders = await getAuthHeaders();

    const response = await fetch(url, {
      ...options,
      headers: {
        ...authHeaders,
        'X-Client-Request-ID': requestId,
        ...options?.headers,
      },
    });

    const duration = Math.round(performance.now() - startTime);

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));

      // Handle specific auth errors
      if (response.status === 401) {
        log.error(`API ${method} ${endpoint} unauthorized`, { duration, requestId });
        // Session might be expired, trigger re-auth
        if (typeof window !== 'undefined') {
          window.location.href = '/login?error=SessionExpired';
        }
        throw new ApiError('Session expired. Please sign in again.', 401, 'UNAUTHORIZED');
      }

      if (response.status === 403) {
        log.error(`API ${method} ${endpoint} forbidden`, { duration, requestId });
        throw new ApiError(
          errorBody.detail || 'You do not have permission to perform this action.',
          403,
          'FORBIDDEN'
        );
      }

      log.error(`API ${method} ${endpoint} failed`, {
        status: response.status,
        duration,
        requestId,
        error: errorBody.detail || errorBody.message,
      });
      throw new ApiError(
        errorBody.detail || errorBody.message || `HTTP ${response.status}`,
        response.status,
        errorBody.code
      );
    }

    log.debug(`API ${method} ${endpoint} completed`, {
      status: response.status,
      duration,
      requestId,
    });

    return response.json();
  } catch (error) {
    const duration = Math.round(performance.now() - startTime);

    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof TypeError) {
      log.error(`API ${method} ${endpoint} network error`, { duration, requestId });
      throw new ApiError('Network error - is the backend running?', 0);
    }
    log.error(`API ${method} ${endpoint} unexpected error`, {
      duration,
      requestId,
      error: String(error),
    });
    throw new ApiError(String(error), 500);
  }
}

/**
 * Fetch API without authentication (for public endpoints)
 */
async function fetchPublicApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = buildApiUrl(endpoint);
  const method = options?.method || 'GET';
  const startTime = performance.now();
  const requestId = createRequestId();

  log.api(method, endpoint, { requestId, url });

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-Client-Request-ID': requestId,
        ...options?.headers,
      },
    });

    const duration = Math.round(performance.now() - startTime);

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      log.error(`API ${method} ${endpoint} failed`, {
        status: response.status,
        duration,
        requestId,
        error: errorBody.detail || errorBody.message,
      });
      throw new ApiError(
        errorBody.detail || errorBody.message || `HTTP ${response.status}`,
        response.status,
        errorBody.code
      );
    }

    log.debug(`API ${method} ${endpoint} completed`, {
      status: response.status,
      duration,
      requestId,
    });

    return response.json();
  } catch (error) {
    const duration = Math.round(performance.now() - startTime);

    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof TypeError) {
      log.error(`API ${method} ${endpoint} network error`, { duration, requestId });
      throw new ApiError('Network error - is the backend running?', 0);
    }
    log.error(`API ${method} ${endpoint} unexpected error`, {
      duration,
      requestId,
      error: String(error),
    });
    throw new ApiError(String(error), 500);
  }
}

// Health check (public endpoint)
export async function getHealth(): Promise<HealthResponse> {
  return fetchPublicApi<HealthResponse>('/health');
}

// Chat API
export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  return fetchApi<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// Task API
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  return fetchApi<TaskStatus>(`/api/task/${taskId}`);
}

export async function cancelTask(taskId: string): Promise<void> {
  return fetchApi<void>(`/api/task/${taskId}`, {
    method: 'DELETE',
  });
}

// Dashboard API
export async function getDashboardStats(): Promise<DashboardStats> {
  return fetchApi<DashboardStats>('/api/dashboard/stats');
}

export async function getDashboardPnL(
  period: '1d' | '7d' | '30d' | '90d' = '30d'
): Promise<DashboardPnL> {
  return fetchApi<DashboardPnL>(`/api/dashboard/pnl?period=${period}`);
}

export async function getDashboardPerformance(
  limit: number = 10
): Promise<DashboardPerformance> {
  return fetchApi<DashboardPerformance>(
    `/api/dashboard/performance?limit=${limit}`
  );
}

export async function getDashboardAnalysisQuality(): Promise<DashboardAnalysisQuality> {
  return fetchApi<DashboardAnalysisQuality>('/api/dashboard/analysis-quality');
}

export async function getDashboardServiceHealth(): Promise<DashboardServiceHealth> {
  return fetchApi<DashboardServiceHealth>('/api/dashboard/service-health');
}

export async function getDashboardWatchlistSummary(): Promise<DashboardWatchlistSummary> {
  return fetchApi<DashboardWatchlistSummary>(
    '/api/dashboard/watchlist-summary'
  );
}

// User API (new)
export interface UserProfile {
  id: number;
  email: string;
  name: string;
  picture?: string;
  roles: string[];
  permissions: string[];
  ib_account_id?: string;
  ib_trading_mode?: 'paper' | 'live';
  preferences: Record<string, unknown>;
}

export async function getCurrentUser(): Promise<UserProfile> {
  return fetchApi<UserProfile>('/api/auth/me');
}

export async function updateUserProfile(data: Partial<UserProfile>): Promise<UserProfile> {
  return fetchApi<UserProfile>('/api/users/me/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateIBAccount(data: {
  ib_account_id: string;
  ib_trading_mode: 'paper' | 'live';
  ib_gateway_port?: number | null;
}): Promise<UserProfile> {
  return fetchApi<UserProfile>('/api/users/me/ib-account', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export interface IBAccountSettings {
  ib_account_id: string | null;
  ib_trading_mode: 'paper' | 'live';
  ib_gateway_port: number | null;
}

export async function getIBAccount(): Promise<IBAccountSettings> {
  return fetchApi<IBAccountSettings>('/api/users/me/ib-account');
}

// Auth API (new)
export async function completeOnboarding(): Promise<{ success: boolean }> {
  return fetchApi<{ success: boolean }>('/api/auth/complete-onboarding', {
    method: 'POST',
  });
}

export async function syncUser(data: {
  sub: string;
  email: string;
  name?: string;
  picture?: string;
  email_verified?: boolean;
  roles?: string[];
}): Promise<{ success: boolean; user_id: number }> {
  return fetchPublicApi<{ success: boolean; user_id: number }>('/api/auth/sync-user', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// API Keys (new)
export interface ApiKey {
  id: number;
  key_prefix: string;
  name: string;
  permissions: string[];
  last_used_at?: string;
  expires_at?: string;
  created_at: string;
}

export interface CreateApiKeyResponse {
  key: string;  // Full key, only shown once
  api_key: ApiKey;
}

export async function listApiKeys(): Promise<ApiKey[]> {
  return fetchApi<ApiKey[]>('/api/users/me/api-keys');
}

export async function createApiKey(data: {
  name: string;
  permissions?: string[];
  expires_in_days?: number;
}): Promise<CreateApiKeyResponse> {
  return fetchApi<CreateApiKeyResponse>('/api/users/me/api-keys', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function revokeApiKey(keyId: number): Promise<void> {
  return fetchApi<void>(`/api/users/me/api-keys/${keyId}`, {
    method: 'DELETE',
  });
}

// Admin API (new)
export interface AdminUser {
  id: number;
  auth0_sub: string;
  email: string;
  name: string;
  picture?: string;
  is_active: boolean;
  is_admin: boolean;
  roles: string[];
  last_login_at?: string;
  created_at: string;
}

export async function listUsers(params?: {
  page?: number;
  limit?: number;
  search?: string;
}): Promise<{ users: AdminUser[]; total: number }> {
  const query = new URLSearchParams();
  if (params?.page) query.set('page', String(params.page));
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.search) query.set('search', params.search);

  return fetchApi(`/api/admin/users?${query.toString()}`);
}

export async function updateUserRoles(userId: number, roles: string[]): Promise<AdminUser> {
  return fetchApi<AdminUser>(`/api/admin/users/${userId}/roles`, {
    method: 'PUT',
    body: JSON.stringify({ roles }),
  });
}

export async function setUserActive(userId: number, isActive: boolean): Promise<AdminUser> {
  return fetchApi<AdminUser>(`/api/admin/users/${userId}/status`, {
    method: 'PUT',
    body: JSON.stringify({ is_active: isActive }),
  });
}

export interface Role {
  id: number;
  name: string;
  display_name: string;
  description: string;
  is_system: boolean;
  permissions: string[];
}

export async function listRoles(): Promise<Role[]> {
  return fetchApi<Role[]>('/api/admin/roles');
}

export async function listPermissions(): Promise<Array<{
  code: string;
  display_name: string;
  description: string;
  resource_type: string;
  action: string;
}>> {
  return fetchApi('/api/admin/permissions');
}

export async function deleteUserData(userId: number): Promise<{
  success: boolean;
  user_id: number;
  tables_cleared: string[];
}> {
  return fetchApi(`/api/admin/users/${userId}/data`, {
    method: 'DELETE',
  });
}

// System Settings API
export interface SystemSettings {
  auth_enabled: boolean;
  auth0_configured: boolean;
  auth0_domain: string;
  auth0_audience: string;
  rate_limit_enabled: boolean;
  rate_limit_requests_per_minute: number;
  max_sessions_per_user: number;
  admin_email: string;
  debug: boolean;
}

export interface Auth0Config {
  auth0_domain: string;
  auth0_client_id: string;
  auth0_client_secret_masked: string;
  auth0_audience: string;
  is_configured: boolean;
}

export async function getSystemSettings(): Promise<SystemSettings> {
  return fetchApi<SystemSettings>('/api/settings/system');
}

export async function getAuth0Config(): Promise<Auth0Config> {
  return fetchApi<Auth0Config>('/api/settings/auth0');
}

export async function updateAuth0Config(config: {
  auth0_domain: string;
  auth0_client_id: string;
  auth0_client_secret: string;
  auth0_audience?: string;
}): Promise<Auth0Config> {
  return fetchApi<Auth0Config>('/api/settings/auth0', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export async function requestServerRestart(): Promise<{
  success: boolean;
  message: string;
  restart_required: boolean;
}> {
  return fetchApi('/api/settings/restart-server', {
    method: 'POST',
  });
}

// Analysis API
export interface AnalysisSummary {
  id: number;
  ticker: string;
  type: string;
  recommendation: string | null;
  confidence: number | null;
  gate_result: string | null;
  expected_value: number | null;
  analysis_date: string;
  status: string;
  schema_version: string;
}

export interface AnalysisListResponse {
  analyses: AnalysisSummary[];
  total: number;
}

export interface AnalysisDetailResponse {
  id: number;
  ticker: string;
  analysis_date: string;
  schema_version: string;
  file_path: string;
  recommendation: string | null;
  confidence: number | null;
  gate_result: string | null;
  expected_value: number | null;
  current_price: number | null;
  status: string;
  yaml_content: Record<string, unknown>;
}

export async function listAnalyses(params?: {
  status?: 'all' | 'completed' | 'expired' | 'declined' | 'error';
  limit?: number;
  offset?: number;
}): Promise<AnalysisListResponse> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== 'all') query.set('status', params.status);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));

  const queryStr = query.toString();
  return fetchApi<AnalysisListResponse>(`/api/analyses/list${queryStr ? `?${queryStr}` : ''}`);
}

export async function getAnalysisDetail(id: number): Promise<AnalysisDetailResponse> {
  return fetchApi<AnalysisDetailResponse>(`/api/analyses/detail/${id}`);
}

export async function getAnalysisByTicker(ticker: string): Promise<AnalysisDetailResponse> {
  return fetchApi<AnalysisDetailResponse>(`/api/analyses/by-ticker/${ticker}`);
}

// Trades API
export interface TradeSummary {
  id: number;
  ticker: string;
  direction: string | null;
  entry_date: string;
  entry_price: number;
  entry_size: number;
  status: string;
  exit_date: string | null;
  exit_price: number | null;
  pnl_dollars: number | null;
  pnl_pct: number | null;
  thesis: string | null;
  source_type: string | null;
}

export interface TradeStats {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  total_pnl: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number;
  worst_trade: number;
}

export interface TradeListResponse {
  trades: TradeSummary[];
  total: number;
  stats: TradeStats;
}

export interface TradeDetail extends TradeSummary {
  entry_type: string | null;
  current_size: number | null;
  exit_reason: string | null;
  source_analysis: string | null;
  review_status: string | null;
  stop_loss: number | null;
  target_price: number | null;
  full_symbol: string | null;
  option_underlying: string | null;
  option_expiration: string | null;
  option_strike: number | null;
  option_type: string | null;
}

export async function listTrades(params?: {
  status?: 'open' | 'closed' | 'cancelled' | 'all';
  ticker?: string;
  limit?: number;
  offset?: number;
}): Promise<TradeListResponse> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== 'all') query.set('status', params.status);
  if (params?.ticker) query.set('ticker', params.ticker);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));

  return fetchApi<TradeListResponse>(`/api/trades/list?${query.toString()}`);
}

export async function getTradeDetail(id: number): Promise<TradeDetail> {
  return fetchApi<TradeDetail>(`/api/trades/detail/${id}`);
}

export async function getTradeStats(): Promise<TradeStats> {
  return fetchApi<TradeStats>('/api/trades/stats');
}

// Watchlist API
export interface WatchlistSummary {
  id: number;
  name: string;
  description: string | null;
  source_type: 'manual' | 'scanner' | 'auto';
  source_ref: string | null;
  color: string | null;
  is_default: boolean;
  is_pinned: boolean;
  total_entries: number;
  active_entries: number;
  created_at: string;
  updated_at: string;
}

export interface WatchlistsResponse {
  watchlists: WatchlistSummary[];
}

export interface CreateWatchlistPayload {
  name: string;
  description?: string | null;
  color?: string;
  is_pinned?: boolean;
}

export interface WatchlistEntry {
  id: number;
  watchlist_id: number | null;
  watchlist_name: string | null;
  watchlist_source_type: 'manual' | 'scanner' | 'auto' | null;
  watchlist_color: string | null;
  ticker: string;
  entry_trigger: string | null;
  entry_price: number | null;
  invalidation: string | null;
  invalidation_price: number | null;
  expires_at: string | null;
  priority: string;
  status: string;
  source: string | null;
  source_analysis: string | null;
  notes: string | null;
  created_at: string;
  days_until_expiry: number | null;
}

export interface WatchlistStats {
  total: number;
  active: number;
  triggered: number;
  expired: number;
  invalidated: number;
  by_priority: Record<string, number>;
}

export interface WatchlistListResponse {
  entries: WatchlistEntry[];
  total: number;
  stats: WatchlistStats;
}

export async function listWatchlists(): Promise<WatchlistsResponse> {
  return fetchApi<WatchlistsResponse>('/api/watchlists');
}

export async function createWatchlist(payload: CreateWatchlistPayload): Promise<WatchlistSummary> {
  return fetchApi<WatchlistSummary>('/api/watchlists', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function listWatchlist(params?: {
  status?: 'active' | 'triggered' | 'expired' | 'invalidated' | 'all';
  priority?: 'high' | 'medium' | 'low';
  watchlistId?: number;
  limit?: number;
  offset?: number;
}): Promise<WatchlistListResponse> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== 'all') query.set('status', params.status);
  if (params?.priority) query.set('priority', params.priority);
  if (params?.watchlistId) query.set('watchlist_id', String(params.watchlistId));
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));

  return fetchApi<WatchlistListResponse>(`/api/watchlist/list?${query.toString()}`);
}

export async function getWatchlistDetail(id: number): Promise<WatchlistEntry> {
  return fetchApi<WatchlistEntry>(`/api/watchlist/detail/${id}`);
}

export async function getWatchlistStats(watchlistId?: number): Promise<WatchlistStats> {
  const query = watchlistId ? `?watchlist_id=${watchlistId}` : '';
  return fetchApi<WatchlistStats>(`/api/watchlist/stats${query}`);
}

// Scanners API
export interface ScannerConfig {
  id: number;
  scanner_code: string;
  name: string;
  description: string | null;
  scanner_type: string;
  is_enabled: boolean;
  schedule: string | null;
  last_run: string | null;
  last_run_status: string | null;
  candidates_count: number | null;
}

export interface ScannerCandidate {
  ticker: string;
  score: number | null;
  price: number | null;
  notes: string | null;
}

export interface ScannerResult {
  id: number;
  scanner_code: string;
  scan_time: string;
  status: string;
  duration_seconds: number | null;
  candidates_found: number;
  candidates: ScannerCandidate[];
}

export interface ScannerListResponse {
  scanners: ScannerConfig[];
  total: number;
}

export interface ScannerResultsResponse {
  results: ScannerResult[];
  total: number;
}

export async function listScanners(params?: {
  scanner_type?: string;
  enabled_only?: boolean;
}): Promise<ScannerListResponse> {
  const query = new URLSearchParams();
  if (params?.scanner_type) query.set('scanner_type', params.scanner_type);
  if (params?.enabled_only) query.set('enabled_only', 'true');

  return fetchApi<ScannerListResponse>(`/api/scanners/list?${query.toString()}`);
}

export async function getScannerResults(params?: {
  scanner_code?: string;
  limit?: number;
}): Promise<ScannerResultsResponse> {
  const query = new URLSearchParams();
  if (params?.scanner_code) query.set('scanner_code', params.scanner_code);
  if (params?.limit) query.set('limit', String(params.limit));

  return fetchApi<ScannerResultsResponse>(`/api/scanners/results?${query.toString()}`);
}

export async function getLatestCandidates(limit: number = 10): Promise<ScannerCandidate[]> {
  return fetchApi<ScannerCandidate[]>(`/api/scanners/latest?limit=${limit}`);
}

// Agent Sessions API
export interface SessionSummary {
  id: number;
  session_id: string;
  title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export interface SessionMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  status: 'pending' | 'streaming' | 'complete' | 'error';
  error?: string;
  a2ui?: Record<string, unknown>;
  taskId?: string;
  timestamp: string;
}

export interface SessionDetail extends SessionSummary {
  messages: SessionMessage[];
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
}

export async function listSessions(params?: {
  limit?: number;
  offset?: number;
  include_archived?: boolean;
}): Promise<SessionListResponse> {
  const query = new URLSearchParams();
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  if (params?.include_archived) query.set('include_archived', 'true');

  return fetchApi<SessionListResponse>(`/api/sessions/list?${query.toString()}`);
}

export async function getAgentSession(sessionId: string): Promise<SessionDetail> {
  return fetchApi<SessionDetail>(`/api/sessions/detail/${sessionId}`);
}

export async function createSession(title?: string): Promise<{
  id: number;
  session_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}> {
  return fetchApi('/api/sessions/create', {
    method: 'POST',
    body: JSON.stringify({ title: title || null }),
  });
}

export async function saveSessionMessages(
  sessionId: string,
  messages: Array<{
    message_id: string;
    role: string;
    content: string;
    status: string;
    error?: string;
    a2ui?: Record<string, unknown>;
    task_id?: string;
  }>
): Promise<{ success: boolean; messages_saved: number }> {
  return fetchApi(`/api/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify(messages),
  });
}

export async function updateSession(
  sessionId: string,
  updates: { title?: string; is_archived?: boolean }
): Promise<{ success: boolean }> {
  const query = new URLSearchParams();
  if (updates.title !== undefined) query.set('title', updates.title);
  if (updates.is_archived !== undefined) query.set('is_archived', String(updates.is_archived));

  return fetchApi(`/api/sessions/${sessionId}?${query.toString()}`, {
    method: 'PUT',
  });
}

export async function deleteSession(sessionId: string): Promise<{ success: boolean }> {
  return fetchApi(`/api/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Graph API
// ============================================================================

export async function getGraphStats(): Promise<GraphStats> {
  return fetchApi<GraphStats>('/api/graph/stats');
}

export async function getGraphContext(ticker: string): Promise<GraphContext> {
  return fetchApi<GraphContext>(`/api/graph/context/${ticker.toUpperCase()}`);
}

export async function getGraphSearch(
  ticker: string,
  depth: number = 2
): Promise<GraphData> {
  const response = await fetchApi<{ ticker: string; nodes: any[]; links: any[]; depth: number }>(
    `/api/graph/search/${ticker.toUpperCase()}?depth=${depth}`
  );
  return {
    nodes: response.nodes,
    links: response.links,
  };
}

// API client singleton for hook usage
export const api = {
  health: getHealth,
  chat: {
    send: sendMessage,
  },
  task: {
    status: getTaskStatus,
    cancel: cancelTask,
  },
  dashboard: {
    stats: getDashboardStats,
    pnl: getDashboardPnL,
    performance: getDashboardPerformance,
    analysisQuality: getDashboardAnalysisQuality,
    serviceHealth: getDashboardServiceHealth,
    watchlistSummary: getDashboardWatchlistSummary,
  },
  auth: {
    me: getCurrentUser,
    completeOnboarding,
    syncUser,
  },
  user: {
    current: getCurrentUser,
    updateProfile: updateUserProfile,
    getIbAccount: getIBAccount,
    updateIbAccount: updateIBAccount,
  },
  apiKeys: {
    list: listApiKeys,
    create: createApiKey,
    revoke: revokeApiKey,
  },
  admin: {
    listUsers: (page?: number, limit?: number, search?: string) =>
      listUsers({ page, limit, search }),
    listRoles,
    listPermissions,
    updateUserRoles,
    updateUserStatus: setUserActive,
    deleteUserData,
  },
  settings: {
    getSystem: getSystemSettings,
    getAuth0: getAuth0Config,
    updateAuth0: updateAuth0Config,
    requestRestart: requestServerRestart,
  },
  analyses: {
    list: listAnalyses,
    detail: getAnalysisDetail,
    byTicker: getAnalysisByTicker,
  },
  trades: {
    list: listTrades,
    detail: getTradeDetail,
    stats: getTradeStats,
  },
  watchlist: {
    list: listWatchlist,
    detail: getWatchlistDetail,
    stats: getWatchlistStats,
  },
  scanners: {
    list: listScanners,
    results: getScannerResults,
    latestCandidates: getLatestCandidates,
  },
  sessions: {
    list: listSessions,
    get: getAgentSession,
    create: createSession,
    saveMessages: saveSessionMessages,
    update: updateSession,
    delete: deleteSession,
  },
  graph: {
    stats: getGraphStats,
    context: getGraphContext,
    search: getGraphSearch,
  },
};
