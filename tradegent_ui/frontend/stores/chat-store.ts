import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { A2UIResponse } from '@/types/a2ui';
import type { ConnectionState } from '@/lib/websocket';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  a2ui?: A2UIResponse;
  timestamp: Date;
  taskId?: string;
  status?: 'pending' | 'streaming' | 'complete' | 'error';
  error?: string;
  progress?: number;  // Progress percentage (0-100)
  progressMessage?: string;  // Progress status message
}

export interface SessionInfo {
  id: number;
  sessionId: string;
  title: string | null;
  messageCount: number;
  createdAt: Date;
  updatedAt: Date;
}

interface ChatState {
  // Messages
  messages: ChatMessage[];

  // Session management
  sessionId: string | null;
  currentSession: SessionInfo | null;
  savedSessions: SessionInfo[];
  sessionsDirty: boolean;  // True if messages have changed since last save

  // Connection status
  isConnected: boolean;
  isStreaming: boolean;
  connectionState: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastError: string | null;

  // Actions
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => string;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  clearMessages: () => void;
  setSessionId: (id: string | null) => void;
  setConnected: (connected: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setConnectionState: (state: ConnectionState) => void;
  setReconnectInfo: (attempts: number, maxAttempts: number) => void;
  setLastError: (error: string | null) => void;

  // Session management actions
  setCurrentSession: (session: SessionInfo | null) => void;
  setSavedSessions: (sessions: SessionInfo[]) => void;
  markSessionDirty: () => void;
  markSessionClean: () => void;
  loadSession: (session: SessionInfo, messages: ChatMessage[]) => void;
  newSession: () => void;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      // Initial state
      messages: [],
      sessionId: null,
      currentSession: null,
      savedSessions: [],
      sessionsDirty: false,
      isConnected: false,
      isStreaming: false,
      connectionState: 'disconnected' as ConnectionState,
      reconnectAttempts: 0,
      maxReconnectAttempts: 10,
      lastError: null,

      // Actions
      addMessage: (message) => {
        const id = generateId();
        const newMessage: ChatMessage = {
          ...message,
          id,
          timestamp: new Date(),
        };
        set((state) => ({
          messages: [...state.messages, newMessage],
          sessionsDirty: true,
        }));
        return id;
      },

      updateMessage: (id, updates) => {
        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === id ? { ...msg, ...updates } : msg
          ),
          sessionsDirty: true,
        }));
      },

      clearMessages: () => {
        set({
          messages: [],
          sessionId: null,
          currentSession: null,
          sessionsDirty: false,
        });
      },

      setSessionId: (id) => set({ sessionId: id }),
      setConnected: (connected) => set({ isConnected: connected }),
      setStreaming: (streaming) => set({ isStreaming: streaming }),
      setConnectionState: (state) => set({ connectionState: state }),
      setReconnectInfo: (attempts, maxAttempts) =>
        set({ reconnectAttempts: attempts, maxReconnectAttempts: maxAttempts }),
      setLastError: (error) => set({ lastError: error }),

      // Session management
      setCurrentSession: (session) => set({ currentSession: session }),
      setSavedSessions: (sessions) => set({ savedSessions: sessions }),
      markSessionDirty: () => set({ sessionsDirty: true }),
      markSessionClean: () => set({ sessionsDirty: false }),

      loadSession: (session, messages) => {
        set({
          messages,
          sessionId: session.sessionId,
          currentSession: session,
          sessionsDirty: false,
        });
      },

      newSession: () => {
        const newSessionId = generateId();
        set({
          messages: [],
          sessionId: newSessionId,
          currentSession: null,
          sessionsDirty: false,
        });
      },
    }),
    {
      name: 'tradegent-chat-storage',
      partialize: (state) => ({
        messages: state.messages.slice(-50), // Keep last 50 messages
        sessionId: state.sessionId,
        currentSession: state.currentSession,
      }),
      // Custom serialization for Date objects
      storage: {
        getItem: (name) => {
          const str = localStorage.getItem(name);
          if (!str) return null;
          const data = JSON.parse(str);
          // Restore Date objects
          if (data.state?.messages) {
            data.state.messages = data.state.messages.map(
              (msg: ChatMessage & { timestamp: string }) => ({
                ...msg,
                timestamp: new Date(msg.timestamp),
              })
            );
          }
          if (data.state?.currentSession) {
            data.state.currentSession = {
              ...data.state.currentSession,
              createdAt: new Date(data.state.currentSession.createdAt),
              updatedAt: new Date(data.state.currentSession.updatedAt),
            };
          }
          return data;
        },
        setItem: (name, value) => {
          localStorage.setItem(name, JSON.stringify(value));
        },
        removeItem: (name) => {
          localStorage.removeItem(name);
        },
      },
    }
  )
);
