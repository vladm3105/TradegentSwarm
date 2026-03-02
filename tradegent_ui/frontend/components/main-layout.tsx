'use client';

import { Sidebar } from '@/components/sidebar';
import { Header } from '@/components/header';
import { ChatPanel } from '@/components/chat-panel';
import { ChatErrorBoundary } from '@/components/error-boundary';
import { useUIStore } from '@/stores/ui-store';
import { useKeyboardShortcuts, useNavigationShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { cn } from '@/lib/utils';

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const { sidebarCollapsed, chatPanelOpen } = useUIStore();

  // Enable keyboard shortcuts
  useKeyboardShortcuts();
  useNavigationShortcuts();

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
      <Sidebar />

      {/* Header */}
      <Header />

      {/* Main content area */}
      <main
        className={cn(
          'min-h-screen pt-16 transition-all duration-300',
          sidebarCollapsed ? 'pl-16' : 'pl-64',
          chatPanelOpen && 'pr-80'
        )}
      >
        {children}
      </main>

      {/* Chat Panel */}
      <ChatErrorBoundary>
        <ChatPanel />
      </ChatErrorBoundary>
    </div>
  );
}
