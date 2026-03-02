'use client';

import { useQueries } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  useDashboardStats as useStatsQuery,
  useDashboardPnLQuery,
  useDashboardPerformance,
  useDashboardAnalysisQuality,
  useDashboardServiceHealth,
  useDashboardWatchlistSummary,
  queryKeys,
} from '@/hooks/use-queries';
import type {
  DashboardStats,
  DashboardPnL,
  DashboardPerformance,
  DashboardAnalysisQuality,
  DashboardServiceHealth,
  DashboardWatchlistSummary,
} from '@/types/api';

interface DashboardData {
  stats: DashboardStats | null;
  pnl: DashboardPnL | null;
  performance: DashboardPerformance | null;
  analysisQuality: DashboardAnalysisQuality | null;
  serviceHealth: DashboardServiceHealth | null;
  watchlistSummary: DashboardWatchlistSummary | null;
}

interface UseDashboardOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseDashboardResult {
  data: DashboardData;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Fetch all dashboard data at once using React Query.
 * Uses parallel queries with automatic caching and refetching.
 */
export function useDashboard(
  options: UseDashboardOptions = {}
): UseDashboardResult {
  const { autoRefresh = true, refreshInterval = 60000 } = options;

  const results = useQueries({
    queries: [
      {
        queryKey: queryKeys.dashboard.stats,
        queryFn: api.dashboard.stats,
        staleTime: 60 * 1000,
        refetchInterval: autoRefresh ? refreshInterval : false,
      },
      {
        queryKey: queryKeys.dashboard.pnl('30d'),
        queryFn: () => api.dashboard.pnl('30d'),
        staleTime: 5 * 60 * 1000,
        refetchInterval: autoRefresh ? refreshInterval : false,
      },
      {
        queryKey: queryKeys.dashboard.performance(10),
        queryFn: () => api.dashboard.performance(10),
        staleTime: 5 * 60 * 1000,
        refetchInterval: autoRefresh ? refreshInterval : false,
      },
      {
        queryKey: queryKeys.dashboard.analysisQuality,
        queryFn: api.dashboard.analysisQuality,
        staleTime: 5 * 60 * 1000,
        refetchInterval: autoRefresh ? refreshInterval : false,
      },
      {
        queryKey: queryKeys.dashboard.serviceHealth,
        queryFn: api.dashboard.serviceHealth,
        staleTime: 30 * 1000,
        refetchInterval: autoRefresh ? Math.min(refreshInterval, 60000) : false,
      },
      {
        queryKey: queryKeys.dashboard.watchlistSummary,
        queryFn: api.dashboard.watchlistSummary,
        staleTime: 60 * 1000,
        refetchInterval: autoRefresh ? refreshInterval : false,
      },
    ],
  });

  const [statsQuery, pnlQuery, performanceQuery, analysisQualityQuery, serviceHealthQuery, watchlistQuery] = results;

  const isLoading = results.some((r) => r.isLoading);
  const allFailed = results.every((r) => r.isError);
  const firstError = results.find((r) => r.error);

  const refetch = async () => {
    await Promise.all(results.map((r) => r.refetch()));
  };

  return {
    data: {
      stats: statsQuery.data ?? null,
      pnl: pnlQuery.data ?? null,
      performance: performanceQuery.data ?? null,
      analysisQuality: analysisQualityQuery.data ?? null,
      serviceHealth: serviceHealthQuery.data ?? null,
      watchlistSummary: watchlistQuery.data ?? null,
    },
    isLoading,
    error: allFailed && firstError?.error ? String(firstError.error) : null,
    refetch,
  };
}

/**
 * Fetch dashboard stats using React Query.
 */
export function useDashboardStats() {
  const { data, isLoading, error, refetch } = useStatsQuery();

  return {
    stats: data ?? null,
    isLoading,
    error: error ? String(error) : null,
    refetch,
  };
}

/**
 * Fetch P&L data using React Query.
 */
export function useDashboardPnL(period: '1d' | '7d' | '30d' | '90d' = '30d') {
  const { data, isLoading, error, refetch } = useDashboardPnLQuery(period);

  return {
    pnl: data ?? null,
    isLoading,
    error: error ? String(error) : null,
    refetch,
  };
}

// Re-export the query hooks for direct access
export {
  useDashboardPerformance,
  useDashboardAnalysisQuality,
  useDashboardServiceHealth,
  useDashboardWatchlistSummary,
} from '@/hooks/use-queries';
