import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SessionState {
  // User preferences
  defaultTicker: string | null;
  recentTickers: string[];

  // Dashboard settings
  dashboardTimeframe: '1d' | '7d' | '30d' | '90d';

  // Last viewed pages
  lastPage: string;

  // Actions
  setDefaultTicker: (ticker: string | null) => void;
  addRecentTicker: (ticker: string) => void;
  setDashboardTimeframe: (timeframe: '1d' | '7d' | '30d' | '90d') => void;
  setLastPage: (page: string) => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      // Initial state
      defaultTicker: null,
      recentTickers: [],
      dashboardTimeframe: '30d',
      lastPage: '/',

      // Actions
      setDefaultTicker: (ticker) => set({ defaultTicker: ticker }),

      addRecentTicker: (ticker) => {
        const current = get().recentTickers;
        const filtered = current.filter((t) => t !== ticker);
        const updated = [ticker, ...filtered].slice(0, 10); // Keep last 10
        set({ recentTickers: updated });
      },

      setDashboardTimeframe: (timeframe) =>
        set({ dashboardTimeframe: timeframe }),

      setLastPage: (page) => set({ lastPage: page }),
    }),
    {
      name: 'tradegent-session-storage',
    }
  )
);
