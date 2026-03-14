'use client';

import { usePathname } from 'next/navigation';
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
  const pathname = usePathname();
  const { sidebarCollapsed, chatPanelOpen, chatPanelWidth } = useUIStore();
  const isAuthRoute = pathname === '/login' || pathname.startsWith('/verify-email');

  // Enable keyboard shortcuts
  useKeyboardShortcuts();
  useNavigationShortcuts();

  if (isAuthRoute) {
    return <div className="min-h-screen bg-background">{children}</div>;
  }

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
          sidebarCollapsed ? 'pl-16' : 'pl-64'
        )}
        style={{ paddingRight: chatPanelOpen ? `${chatPanelWidth}px` : undefined }}
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
