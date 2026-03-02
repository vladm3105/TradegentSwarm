'use client';

import { ReactNode, useEffect, useState } from 'react';
import { SessionProvider } from 'next-auth/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { getQueryClient } from '@/lib/query-client';
import { Toaster } from '@/components/ui/toaster';
import { createLogger } from '@/lib/logger';

const log = createLogger('app');

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [mounted, setMounted] = useState(false);
  const queryClient = getQueryClient();

  // Handle hydration mismatch for theme
  useEffect(() => {
    setMounted(true);

    log.info('App mounted', {
      env: process.env.NODE_ENV,
      apiUrl: process.env.NEXT_PUBLIC_API_URL,
      wsUrl: process.env.NEXT_PUBLIC_WS_URL,
    });

    // Apply dark mode from localStorage or system preference
    const stored = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (stored === 'dark' || (!stored && prefersDark)) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }

    log.debug('Theme initialized', { stored, prefersDark });
  }, []);

  // Always wrap with providers - SessionProvider handles SSR/SSG gracefully
  // The mounted check is only for theme flash prevention
  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>
        {!mounted ? (
          <div className="min-h-screen bg-background">
            {children}
          </div>
        ) : (
          <>
            {children}
            <Toaster />
            {process.env.NODE_ENV === 'development' && (
              <ReactQueryDevtools initialIsOpen={false} />
            )}
          </>
        )}
      </QueryClientProvider>
    </SessionProvider>
  );
}

/**
 * Theme toggle hook for use in components
 */
export function useTheme() {
  const [theme, setThemeState] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    const stored = localStorage.getItem('theme') as 'light' | 'dark' | null;
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setThemeState(stored ?? (prefersDark ? 'dark' : 'light'));
  }, []);

  const setTheme = (newTheme: 'light' | 'dark') => {
    setThemeState(newTheme);
    localStorage.setItem('theme', newTheme);

    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return { theme, setTheme, toggleTheme };
}
