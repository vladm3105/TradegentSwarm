import { describe, it, expect, beforeEach } from 'vitest';
import { useUIStore } from '@/stores/ui-store';

describe('UI Store', () => {
  beforeEach(() => {
    // Reset store state
    useUIStore.setState({
      sidebarOpen: true,
      sidebarCollapsed: false,
      chatPanelOpen: false,
      theme: 'system',
    });
  });

  describe('sidebar', () => {
    it('toggles sidebar open state', () => {
      const store = useUIStore.getState();
      expect(store.sidebarOpen).toBe(true);

      store.toggleSidebar();
      expect(useUIStore.getState().sidebarOpen).toBe(false);

      store.toggleSidebar();
      expect(useUIStore.getState().sidebarOpen).toBe(true);
    });

    it('sets sidebar collapsed state directly', () => {
      const store = useUIStore.getState();
      store.setSidebarCollapsed(true);
      expect(useUIStore.getState().sidebarCollapsed).toBe(true);
    });
  });

  describe('chat panel', () => {
    it('toggles chat panel open state', () => {
      const store = useUIStore.getState();
      expect(store.chatPanelOpen).toBe(false);

      store.toggleChatPanel();
      expect(useUIStore.getState().chatPanelOpen).toBe(true);
    });

    it('sets chat panel state directly', () => {
      const store = useUIStore.getState();
      store.setChatPanelOpen(true);
      expect(useUIStore.getState().chatPanelOpen).toBe(true);
    });
  });

  describe('theme', () => {
    it('sets theme to dark', () => {
      const store = useUIStore.getState();
      store.setTheme('dark');
      expect(useUIStore.getState().theme).toBe('dark');
    });

    it('sets theme to light', () => {
      const store = useUIStore.getState();
      store.setTheme('light');
      expect(useUIStore.getState().theme).toBe('light');
    });

    it('sets theme to system', () => {
      const store = useUIStore.getState();
      store.setTheme('light');
      store.setTheme('system');
      expect(useUIStore.getState().theme).toBe('system');
    });
  });
});
