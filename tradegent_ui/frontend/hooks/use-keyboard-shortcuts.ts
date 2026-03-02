import { useEffect, useCallback } from 'react';
import { useUIStore } from '@/stores/ui-store';

interface KeyboardShortcut {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
  action: () => void;
  description: string;
}

export function useKeyboardShortcuts() {
  const { toggleChatPanel, toggleSidebar } = useUIStore();

  const shortcuts: KeyboardShortcut[] = [
    {
      key: 'k',
      ctrl: true,
      action: () => {
        // Focus search input
        const searchInput = document.querySelector<HTMLInputElement>(
          'input[placeholder*="Search ticker"]'
        );
        searchInput?.focus();
      },
      description: 'Open search',
    },
    {
      key: 'k',
      meta: true,
      action: () => {
        const searchInput = document.querySelector<HTMLInputElement>(
          'input[placeholder*="Search ticker"]'
        );
        searchInput?.focus();
      },
      description: 'Open search (Mac)',
    },
    {
      key: '/',
      ctrl: true,
      action: () => toggleChatPanel(),
      description: 'Toggle chat panel',
    },
    {
      key: 'b',
      ctrl: true,
      action: () => toggleSidebar(),
      description: 'Toggle sidebar',
    },
    {
      key: 'Escape',
      action: () => {
        // Close any open modals or panels
        const chatOpen = useUIStore.getState().chatPanelOpen;
        if (chatOpen) {
          toggleChatPanel();
        }
        // Blur focused input
        if (document.activeElement instanceof HTMLElement) {
          document.activeElement.blur();
        }
      },
      description: 'Close modals/panels',
    },
  ];

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Skip if user is typing in an input
      const target = event.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        // Only allow Escape in inputs
        if (event.key !== 'Escape') {
          return;
        }
      }

      for (const shortcut of shortcuts) {
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatch = shortcut.ctrl ? event.ctrlKey : !event.ctrlKey;
        const metaMatch = shortcut.meta ? event.metaKey : !event.metaKey;
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
        const altMatch = shortcut.alt ? event.altKey : !event.altKey;

        // For shortcuts that need either ctrl or meta (cross-platform)
        const modifierMatch =
          (shortcut.ctrl && !shortcut.meta && (event.ctrlKey || event.metaKey)) ||
          (ctrlMatch && metaMatch);

        if (keyMatch && modifierMatch && shiftMatch && altMatch) {
          event.preventDefault();
          shortcut.action();
          return;
        }
      }
    },
    [shortcuts, toggleChatPanel, toggleSidebar]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return shortcuts;
}

// Navigation shortcuts
export function useNavigationShortcuts() {
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Only activate with Alt key
    if (!event.altKey) return;

    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
      return;
    }

    const routes: Record<string, string> = {
      '1': '/',
      '2': '/analysis',
      '3': '/trades',
      '4': '/watchlist',
      '5': '/charts',
      '6': '/scanner',
      '7': '/knowledge',
      '8': '/settings',
    };

    if (routes[event.key]) {
      event.preventDefault();
      window.location.href = routes[event.key];
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
