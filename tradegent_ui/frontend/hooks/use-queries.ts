'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import type {
  DashboardStats,
  DashboardPnL,
  DashboardPerformance,
  DashboardAnalysisQuality,
  DashboardServiceHealth,
  DashboardWatchlistSummary,
  ChatRequest,
} from '@/types/api';

// Query keys for cache management
export const queryKeys = {
  health: ['health'] as const,
  dashboard: {
    all: ['dashboard'] as const,
    stats: ['dashboard', 'stats'] as const,
    pnl: (period: string) => ['dashboard', 'pnl', period] as const,
    performance: (limit: number) => ['dashboard', 'performance', limit] as const,
    analysisQuality: ['dashboard', 'analysis-quality'] as const,
    serviceHealth: ['dashboard', 'service-health'] as const,
    watchlistSummary: ['dashboard', 'watchlist-summary'] as const,
  },
  task: (taskId: string) => ['task', taskId] as const,
};

// Health check query
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: api.health,
    staleTime: 10 * 1000, // Check health every 10 seconds
    refetchInterval: 30 * 1000, // Auto-refetch every 30 seconds
  });
}

// Dashboard stats query
export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboard.stats,
    queryFn: api.dashboard.stats,
    staleTime: 60 * 1000, // Stats fresh for 1 minute
  });
}

// Dashboard P&L query
export function useDashboardPnLQuery(period: '1d' | '7d' | '30d' | '90d' = '30d') {
  return useQuery({
    queryKey: queryKeys.dashboard.pnl(period),
    queryFn: () => api.dashboard.pnl(period),
    staleTime: 5 * 60 * 1000, // P&L data fresh for 5 minutes
  });
}

// Dashboard performance query
export function useDashboardPerformance(limit: number = 10) {
  return useQuery({
    queryKey: queryKeys.dashboard.performance(limit),
    queryFn: () => api.dashboard.performance(limit),
    staleTime: 5 * 60 * 1000,
  });
}

// Dashboard analysis quality query
export function useDashboardAnalysisQuality() {
  return useQuery({
    queryKey: queryKeys.dashboard.analysisQuality,
    queryFn: api.dashboard.analysisQuality,
    staleTime: 5 * 60 * 1000,
  });
}

// Dashboard service health query
export function useDashboardServiceHealth() {
  return useQuery({
    queryKey: queryKeys.dashboard.serviceHealth,
    queryFn: api.dashboard.serviceHealth,
    staleTime: 30 * 1000, // Service health checked every 30 seconds
    refetchInterval: 60 * 1000, // Auto-refetch every minute
  });
}

// Dashboard watchlist summary query
export function useDashboardWatchlistSummary() {
  return useQuery({
    queryKey: queryKeys.dashboard.watchlistSummary,
    queryFn: api.dashboard.watchlistSummary,
    staleTime: 60 * 1000,
  });
}

// Task status query
export function useTaskStatus(taskId: string | null) {
  return useQuery({
    queryKey: queryKeys.task(taskId ?? ''),
    queryFn: () => api.task.status(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      // Poll every 2 seconds while task is running
      const data = query.state.data;
      if (data && (data.status === 'pending' || data.status === 'running')) {
        return 2000;
      }
      return false;
    },
  });
}

// Send chat message mutation
export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ChatRequest) => api.chat.send(request),
    onSuccess: () => {
      // Invalidate relevant queries after sending a message
      // This will refetch dashboard data if the message triggered an action
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

// Cancel task mutation
export function useCancelTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (taskId: string) => api.task.cancel(taskId),
    onSuccess: (_data, taskId) => {
      // Invalidate the specific task query
      queryClient.invalidateQueries({ queryKey: queryKeys.task(taskId) });
    },
  });
}

// Hook to invalidate all dashboard data (useful after actions)
export function useInvalidateDashboard() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  };
}

// Prefetch dashboard data (useful for navigation)
export function usePrefetchDashboard() {
  const queryClient = useQueryClient();

  return async () => {
    await Promise.all([
      queryClient.prefetchQuery({
        queryKey: queryKeys.dashboard.stats,
        queryFn: api.dashboard.stats,
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.dashboard.pnl('30d'),
        queryFn: () => api.dashboard.pnl('30d'),
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.dashboard.serviceHealth,
        queryFn: api.dashboard.serviceHealth,
      }),
    ]);
  };
}
