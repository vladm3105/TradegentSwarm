'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  Bell,
  Moon,
  Sun,
  Menu,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { UserMenu } from '@/components/user-menu';
import { WebSocketStatus } from '@/components/websocket-status';
import { useUIStore } from '@/stores/ui-store';
import { useSessionStore } from '@/stores/session-store';
import { cn } from '@/lib/utils';

export function Header() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const { theme, setTheme, sidebarCollapsed, toggleSidebar } = useUIStore();
  const { recentTickers, addRecentTicker, clearRecentTickers } = useSessionStore();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Check if it looks like a ticker symbol
      const ticker = searchQuery.trim().toUpperCase();
      if (/^[A-Z]{1,5}$/.test(ticker)) {
        addRecentTicker(ticker);
        // Navigate to analysis page with ticker (client-side navigation)
        router.push(`/analysis?ticker=${ticker}`);
        setSearchQuery(''); // Clear search after navigation
      }
    }
  };

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
  };

  return (
    <header
      className={cn(
        'fixed top-0 right-0 z-40 h-16 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 transition-all duration-300',
        sidebarCollapsed ? 'left-16' : 'left-64'
      )}
    >
      <div className="flex h-full items-center justify-between px-4">
        {/* Mobile menu button */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={toggleSidebar}
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-md mx-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search ticker (e.g., NVDA)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-9 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                &times;
              </button>
            )}
          </div>
        </form>

        {/* Right side actions */}
        <div className="flex items-center gap-2">
          {/* Recent tickers */}
          {recentTickers.length > 0 && (
            <div className="hidden lg:flex items-center gap-1 mr-2">
              {recentTickers.slice(0, 3).map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => router.push(`/analysis?ticker=${ticker}`)}
                  className="px-2 py-1 text-xs font-mono rounded-md bg-muted hover:bg-accent transition-colors"
                >
                  {ticker}
                </button>
              ))}
              <button
                onClick={clearRecentTickers}
                title="Clear recent tickers"
                className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Connection status */}
          <WebSocketStatus />

          {/* Notifications */}
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-5 w-5" />
            <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-loss text-[10px] font-medium text-white flex items-center justify-center">
              3
            </span>
          </Button>

          {/* Theme toggle */}
          <Button variant="ghost" size="icon" onClick={toggleTheme}>
            {theme === 'dark' ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
          </Button>

          {/* User menu with separator */}
          <div className="hidden sm:flex items-center gap-2 ml-2 pl-3 border-l">
            <UserMenu />
          </div>
        </div>
      </div>
    </header>
  );
}
