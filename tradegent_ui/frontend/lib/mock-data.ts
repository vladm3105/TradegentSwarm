/**
 * Mock data for development and fallback when API is unavailable.
 * Centralized location for all mock data used across the application.
 */

import type { DashboardStats } from '@/types/api';
import type { PnLDataPoint, PerformanceDataPoint, ScenarioDataPoint } from '@/types/recharts';

// ============================================================================
// Dashboard Mock Data
// ============================================================================

export const mockDashboardStats: DashboardStats = {
  total_pnl: 12547.82,
  total_pnl_pct: 8.32,
  open_positions: 5,
  total_market_value: 163250.0,
  today_pnl: 342.15,
  today_pnl_pct: 0.45,
  win_rate: 68.5,
  total_trades: 127,
  active_analyses: 3,
  watchlist_count: 8,
};

export const mockDailyPnL: PnLDataPoint[] = [
  { date: '2026-02-20', pnl: 450, cumulative: 850 },
  { date: '2026-02-21', pnl: -120, cumulative: 730 },
  { date: '2026-02-22', pnl: 280, cumulative: 1010 },
  { date: '2026-02-23', pnl: 0, cumulative: 1010 },
  { date: '2026-02-24', pnl: 250, cumulative: 1260 },
  { date: '2026-02-25', pnl: -80, cumulative: 1180 },
  { date: '2026-02-26', pnl: 340, cumulative: 1520 },
  { date: '2026-02-27', pnl: 180, cumulative: 1700 },
  { date: '2026-02-28', pnl: -50, cumulative: 1650 },
  { date: '2026-03-01', pnl: 120, cumulative: 1770 },
];

export const mockTopPerformers: PerformanceDataPoint[] = [
  { ticker: 'NVDA', pnl: 2340, pnl_pct: 12.5, trades: 5, win_rate: 80 },
  { ticker: 'AMD', pnl: 1250, pnl_pct: 8.3, trades: 4, win_rate: 75 },
  { ticker: 'AAPL', pnl: 890, pnl_pct: 5.2, trades: 8, win_rate: 62.5 },
  { ticker: 'MSFT', pnl: 650, pnl_pct: 4.1, trades: 6, win_rate: 66.7 },
  { ticker: 'META', pnl: 420, pnl_pct: 3.2, trades: 3, win_rate: 100 },
];

export const mockAnalysisQuality = {
  gate_pass_rate: 72,
  recommendation_distribution: {
    BUY: 35,
    WATCH: 40,
    NO_POSITION: 20,
    AVOID: 5,
  },
};

// ============================================================================
// Analysis Page Mock Data
// ============================================================================

export interface MockAnalysis {
  id: string;
  ticker: string;
  type: 'stock' | 'earnings';
  recommendation: 'STRONG_BUY' | 'BUY' | 'WATCH' | 'NO_POSITION' | 'AVOID';
  confidence: number;
  gate_result: 'PASS' | 'MARGINAL' | 'FAIL';
  expected_value: number;
  analysis_date: string;
  status: 'active' | 'expired';
}

export const mockAnalyses: MockAnalysis[] = [
  {
    id: '1',
    ticker: 'NVDA',
    type: 'stock',
    recommendation: 'BUY',
    confidence: 75,
    gate_result: 'PASS',
    expected_value: 12.5,
    analysis_date: '2026-02-28T10:00:00',
    status: 'active',
  },
  {
    id: '2',
    ticker: 'AAPL',
    type: 'earnings',
    recommendation: 'WATCH',
    confidence: 65,
    gate_result: 'MARGINAL',
    expected_value: 6.2,
    analysis_date: '2026-02-27T14:30:00',
    status: 'active',
  },
  {
    id: '3',
    ticker: 'MSFT',
    type: 'stock',
    recommendation: 'NO_POSITION',
    confidence: 55,
    gate_result: 'FAIL',
    expected_value: 2.1,
    analysis_date: '2026-02-26T09:00:00',
    status: 'expired',
  },
];

// ============================================================================
// Trades Page Mock Data
// ============================================================================

export interface MockTrade {
  id: string;
  ticker: string;
  direction: 'LONG' | 'SHORT';
  entry_price: number;
  exit_price: number | null;
  size: number;
  pnl: number;
  pnl_pct: number;
  status: 'OPEN' | 'CLOSED';
  entry_date: string;
  exit_date: string | null;
}

export const mockTrades: MockTrade[] = [
  {
    id: '1',
    ticker: 'NVDA',
    direction: 'LONG',
    entry_price: 875.5,
    exit_price: 920.25,
    size: 10,
    pnl: 447.5,
    pnl_pct: 5.11,
    status: 'CLOSED',
    entry_date: '2026-02-15T10:30:00',
    exit_date: '2026-02-25T14:15:00',
  },
  {
    id: '2',
    ticker: 'AAPL',
    direction: 'LONG',
    entry_price: 182.3,
    exit_price: null,
    size: 50,
    pnl: -125.0,
    pnl_pct: -1.37,
    status: 'OPEN',
    entry_date: '2026-02-20T09:45:00',
    exit_date: null,
  },
  {
    id: '3',
    ticker: 'TSLA',
    direction: 'SHORT',
    entry_price: 245.0,
    exit_price: 238.5,
    size: 20,
    pnl: 130.0,
    pnl_pct: 2.65,
    status: 'CLOSED',
    entry_date: '2026-02-18T11:00:00',
    exit_date: '2026-02-22T15:30:00',
  },
];

export const mockTradeStats = {
  total_pnl: 452.5,
  total_pnl_pct: 3.2,
  win_rate: 66.7,
  total_trades: 3,
  open_trades: 1,
  avg_win: 288.75,
  avg_loss: -125.0,
};

// ============================================================================
// Watchlist Page Mock Data
// ============================================================================

export interface MockWatchlistEntry {
  id: string;
  ticker: string;
  trigger_type: 'PRICE_ABOVE' | 'PRICE_BELOW' | 'EVENT' | 'COMBINED';
  trigger_value: number | null;
  current_price: number;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  expires: string;
  notes: string;
  status: 'active' | 'triggered' | 'expired';
}

export const mockWatchlist: MockWatchlistEntry[] = [
  {
    id: '1',
    ticker: 'AMD',
    trigger_type: 'PRICE_BELOW',
    trigger_value: 155.0,
    current_price: 162.5,
    priority: 'HIGH',
    expires: '2026-03-10',
    notes: 'Waiting for pullback to support',
    status: 'active',
  },
  {
    id: '2',
    ticker: 'META',
    trigger_type: 'EVENT',
    trigger_value: null,
    current_price: 485.3,
    priority: 'MEDIUM',
    expires: '2026-03-05',
    notes: 'Earnings on March 3rd',
    status: 'active',
  },
  {
    id: '3',
    ticker: 'GOOGL',
    trigger_type: 'PRICE_ABOVE',
    trigger_value: 175.0,
    current_price: 168.75,
    priority: 'LOW',
    expires: '2026-03-15',
    notes: 'Breakout above resistance',
    status: 'active',
  },
];

export const mockWatchlistStats = {
  total: 3,
  active: 3,
  expiring_soon: 1,
  high_priority: 1,
};

// ============================================================================
// Scanner Page Mock Data
// ============================================================================

export interface MockScanner {
  id: string;
  name: string;
  type: 'daily' | 'intraday' | 'weekly';
  lastRun: string;
  results: number;
}

export interface MockScannerResult {
  ticker: string;
  score: number;
  catalyst: string;
  scanner: string;
}

export const mockScanners: MockScanner[] = [
  { id: 'premarket-gap', name: 'Pre-Market Gap', type: 'daily', lastRun: '2026-03-01T07:00:00', results: 5 },
  { id: 'earnings-momentum', name: 'Earnings Momentum', type: 'daily', lastRun: '2026-03-01T09:45:00', results: 3 },
  { id: 'unusual-volume', name: 'Unusual Volume', type: 'intraday', lastRun: '2026-03-01T10:30:00', results: 8 },
  { id: '52w-extremes', name: '52-Week Extremes', type: 'daily', lastRun: '2026-03-01T15:45:00', results: 2 },
];

export const mockScannerResults: MockScannerResult[] = [
  { ticker: 'NVDA', score: 8.5, catalyst: 'Post-earnings momentum', scanner: 'earnings-momentum' },
  { ticker: 'AMD', score: 7.8, catalyst: 'Sector strength', scanner: 'unusual-volume' },
  { ticker: 'SMCI', score: 7.5, catalyst: 'Gap up on news', scanner: 'premarket-gap' },
  { ticker: 'AVGO', score: 7.2, catalyst: 'Breakout', scanner: '52w-extremes' },
  { ticker: 'MRVL', score: 6.8, catalyst: 'Volume spike', scanner: 'unusual-volume' },
];

// ============================================================================
// Settings Page Mock Data
// ============================================================================

export interface MockService {
  name: string;
  status: 'healthy' | 'unhealthy' | 'unknown';
  url: string;
}

export const mockServices: MockService[] = [
  { name: 'FastAPI Backend', status: 'healthy', url: 'localhost:8081' },
  { name: 'PostgreSQL', status: 'healthy', url: 'localhost:5433' },
  { name: 'Neo4j', status: 'healthy', url: 'localhost:7688' },
  { name: 'IB MCP', status: 'healthy', url: 'localhost:8100' },
  { name: 'Trading RAG', status: 'healthy', url: 'stdio' },
  { name: 'Trading Graph', status: 'healthy', url: 'stdio' },
];

// ============================================================================
// Scenario Chart Mock Data
// ============================================================================

export const mockScenarios: ScenarioDataPoint[] = [
  { name: 'Bull', probability: 35, return_pct: 15.5, description: 'Strong beat + guidance raise' },
  { name: 'Base', probability: 40, return_pct: 5.0, description: 'In-line results' },
  { name: 'Bear', probability: 20, return_pct: -8.0, description: 'Miss or weak guidance' },
  { name: 'Disaster', probability: 5, return_pct: -25.0, description: 'Major negative surprise' },
];

// ============================================================================
// Knowledge Page Mock Data
// ============================================================================

export interface MockKnowledgeResult {
  id: string;
  type: 'analysis' | 'trade' | 'learning' | 'pattern';
  ticker: string;
  title: string;
  date: string;
  relevance: number;
}

export const mockKnowledgeResults: MockKnowledgeResult[] = [
  {
    id: '1',
    type: 'analysis',
    ticker: 'NVDA',
    title: 'Stock Analysis - AI chip demand thesis',
    date: '2026-02-28',
    relevance: 0.95,
  },
  {
    id: '2',
    type: 'trade',
    ticker: 'NVDA',
    title: 'Trade Journal - Long position closed',
    date: '2026-02-25',
    relevance: 0.88,
  },
  {
    id: '3',
    type: 'learning',
    ticker: 'NVDA',
    title: 'Pattern: Sell-the-news on beat',
    date: '2026-02-20',
    relevance: 0.82,
  },
];
