import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  // Sidebar state
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;

  // Chat panel state
  chatPanelOpen: boolean;
  chatPanelWidth: number;

  // Theme
  theme: 'light' | 'dark' | 'system';

  // Actions
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setChatPanelOpen: (open: boolean) => void;
  setChatPanelWidth: (width: number) => void;
  toggleChatPanel: () => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      // Initial state
      sidebarOpen: true,
      sidebarCollapsed: false,
      chatPanelOpen: false,
      chatPanelWidth: 320,
      theme: 'system',

      // Actions
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setChatPanelOpen: (open) => set({ chatPanelOpen: open }),
      setChatPanelWidth: (width) => set({ chatPanelWidth: width }),
      toggleChatPanel: () =>
        set((state) => ({ chatPanelOpen: !state.chatPanelOpen })),
      setTheme: (theme) => {
        set({ theme });
        // Apply theme to document
        if (typeof window !== 'undefined') {
          const isDark =
            theme === 'dark' ||
            (theme === 'system' &&
              window.matchMedia('(prefers-color-scheme: dark)').matches);
          document.documentElement.classList.toggle('dark', isDark);
          localStorage.setItem('theme', theme);
        }
      },
    }),
    {
      name: 'tradegent-ui-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        chatPanelWidth: state.chatPanelWidth,
        theme: state.theme,
      }),
    }
  )
);
