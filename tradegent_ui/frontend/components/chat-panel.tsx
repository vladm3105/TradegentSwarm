'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  X,
  Send,
  Loader2,
  Trash2,
  Wifi,
  WifiOff,
  History,
  Plus,
  Save,
  ChevronDown,
  Archive,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useUIStore } from '@/stores/ui-store';
import { useChatStore, type ChatMessage, type SessionInfo } from '@/stores/chat-store';
import { useChat } from '@/hooks/use-chat';
import { cn, formatRelativeTime } from '@/lib/utils';
import {
  listSessions,
  getAgentSession,
  createSession,
  saveSessionMessages,
  deleteSession,
  type SessionSummary,
} from '@/lib/api';

function ProgressBar({ progress, message }: { progress?: number; message?: string }) {
  if (progress === undefined) return null;

  return (
    <div className="mt-2 space-y-1">
      <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
      {message && (
        <p className="text-xs text-muted-foreground truncate">{message}</p>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'flex gap-3 p-3',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-medium',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-muted-foreground'
        )}
      >
        {isUser ? 'U' : 'A'}
      </div>

      {/* Message content */}
      <div
        className={cn(
          'flex flex-col gap-1 max-w-[80%]',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        <div
          className={cn(
            'rounded-lg px-3 py-2 text-sm',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
          )}
        >
          {message.content || (message.status === 'pending' ? '' : 'Processing...')}

          {/* Progress bar for streaming messages */}
          {(message.status === 'pending' || message.status === 'streaming') && (
            <ProgressBar
              progress={message.progress}
              message={message.progressMessage}
            />
          )}
        </div>

        {/* Status indicator */}
        {message.status === 'pending' && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            {message.progressMessage || 'Thinking...'}
          </span>
        )}
        {message.status === 'streaming' && !message.progress && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            Processing...
          </span>
        )}
        {message.status === 'error' && (
          <span className="text-xs text-loss">{message.error || 'Error'}</span>
        )}

        {/* Timestamp */}
        <span className="text-xs text-muted-foreground">
          {formatRelativeTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}

function SessionHistoryDropdown({
  sessions,
  onLoadSession,
  onArchiveSession,
  loading,
}: {
  sessions: SessionSummary[];
  onLoadSession: (session: SessionSummary) => void;
  onArchiveSession: (sessionId: string) => void;
  loading: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);

  if (loading) {
    return (
      <Button variant="ghost" size="icon" disabled>
        <Loader2 className="h-4 w-4 animate-spin" />
      </Button>
    );
  }

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        title="Session history"
      >
        <History className="h-4 w-4" />
      </Button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-1 w-64 z-50 bg-background border rounded-lg shadow-lg overflow-hidden">
            <div className="p-2 border-b">
              <p className="text-xs font-medium text-muted-foreground">Recent Sessions</p>
            </div>

            {sessions.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                No saved sessions
              </div>
            ) : (
              <div className="max-h-64 overflow-y-auto">
                {sessions.map((session) => (
                  <div
                    key={session.session_id}
                    className="flex items-center justify-between px-3 py-2 hover:bg-muted cursor-pointer group"
                    onClick={() => {
                      onLoadSession(session);
                      setIsOpen(false);
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {session.title || 'Untitled session'}
                      </p>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatRelativeTime(new Date(session.updated_at))}
                        <span className="mx-1">|</span>
                        {session.message_count} messages
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        onArchiveSession(session.session_id);
                      }}
                    >
                      <Archive className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function ChatPanel() {
  const [input, setInput] = useState('');
  const [sessionsList, setSessionsList] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [savingSession, setSavingSession] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { chatPanelOpen, setChatPanelOpen } = useUIStore();
  const {
    messages,
    isStreaming,
    isConnected,
    sessionId,
    currentSession,
    sessionsDirty,
    sendMessage,
    clearMessages,
    loadSession,
    newSession,
    markSessionClean,
  } = useChat();

  // Fetch sessions list
  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const response = await listSessions({ limit: 20 });
      setSessionsList(response.sessions);
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (chatPanelOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
      fetchSessions();
    }
  }, [chatPanelOpen, fetchSessions]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');

    // Send via WebSocket (adds user message and pending assistant message automatically)
    sendMessage(userMessage);
  };

  const handleSaveSession = async () => {
    if (messages.length === 0) return;

    setSavingSession(true);
    try {
      // Create session if not exists
      let targetSessionId = sessionId;
      if (!currentSession) {
        const newSessionData = await createSession();
        targetSessionId = newSessionData.session_id;
      }

      if (!targetSessionId) {
        console.error('No session ID available');
        return;
      }

      // Save messages
      await saveSessionMessages(
        targetSessionId,
        messages.map((msg) => ({
          message_id: msg.id,
          role: msg.role,
          content: msg.content,
          status: msg.status || 'complete',
          error: msg.error,
          a2ui: msg.a2ui,
          task_id: msg.taskId,
        }))
      );

      markSessionClean();
      fetchSessions();
    } catch (error) {
      console.error('Failed to save session:', error);
    } finally {
      setSavingSession(false);
    }
  };

  const handleLoadSession = async (session: SessionSummary) => {
    try {
      const detail = await getAgentSession(session.session_id);

      const sessionInfo: SessionInfo = {
        id: detail.id,
        sessionId: detail.session_id,
        title: detail.title,
        messageCount: detail.message_count,
        createdAt: new Date(detail.created_at),
        updatedAt: new Date(detail.updated_at),
      };

      const loadedMessages: ChatMessage[] = detail.messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        status: msg.status,
        error: msg.error,
        a2ui: msg.a2ui as any,
        taskId: msg.taskId,
        timestamp: new Date(msg.timestamp),
      }));

      loadSession(sessionInfo, loadedMessages);
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  };

  const handleArchiveSession = async (sessionIdToArchive: string) => {
    try {
      await deleteSession(sessionIdToArchive);
      fetchSessions();
    } catch (error) {
      console.error('Failed to archive session:', error);
    }
  };

  const handleNewSession = () => {
    if (sessionsDirty && messages.length > 0) {
      // Auto-save current session before creating new one
      handleSaveSession().then(() => {
        newSession();
      });
    } else {
      newSession();
    }
  };

  const handleClearSession = () => {
    clearMessages();
  };

  if (!chatPanelOpen) return null;

  return (
    <aside className="fixed inset-y-0 right-0 z-50 w-80 border-l bg-background flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold">Agent</h2>
          <span
            className={cn(
              'flex items-center gap-1 text-xs',
              isConnected ? 'text-gain' : 'text-muted-foreground'
            )}
            title={isConnected ? 'Connected' : 'Disconnected'}
          >
            {isConnected ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
          </span>
          {sessionsDirty && messages.length > 0 && (
            <span className="h-2 w-2 rounded-full bg-yellow-500" title="Unsaved changes" />
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Session History */}
          <SessionHistoryDropdown
            sessions={sessionsList}
            onLoadSession={handleLoadSession}
            onArchiveSession={handleArchiveSession}
            loading={loadingSessions}
          />

          {/* Save Session */}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleSaveSession}
            disabled={!sessionsDirty || messages.length === 0 || savingSession}
            title="Save session"
          >
            {savingSession ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
          </Button>

          {/* New Session */}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleNewSession}
            title="New session"
          >
            <Plus className="h-4 w-4" />
          </Button>

          {/* Clear Chat */}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleClearSession}
            title="Clear chat"
          >
            <Trash2 className="h-4 w-4" />
          </Button>

          {/* Close Panel */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setChatPanelOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Current Session Info */}
      {currentSession && (
        <div className="px-4 py-2 bg-muted/50 border-b text-xs text-muted-foreground">
          <span className="font-medium">{currentSession.title || 'Untitled'}</span>
          <span className="mx-2">|</span>
          <span>{currentSession.messageCount} messages</span>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-4 text-center">
            <p className="text-muted-foreground text-sm">
              Ask me about your portfolio, run an analysis, or get trading
              insights.
            </p>
            <div className="mt-4 space-y-2">
              <button
                onClick={() => setInput('Analyze NVDA')}
                className="block w-full text-left px-3 py-2 text-sm rounded-md bg-muted hover:bg-accent transition-colors"
              >
                Analyze NVDA
              </button>
              <button
                onClick={() => setInput('Show my positions')}
                className="block w-full text-left px-3 py-2 text-sm rounded-md bg-muted hover:bg-accent transition-colors"
              >
                Show my positions
              </button>
              <button
                onClick={() => setInput('Run daily scanner')}
                className="block w-full text-left px-3 py-2 text-sm rounded-md bg-muted hover:bg-accent transition-colors"
              >
                Run daily scanner
              </button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t p-4">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything..."
            disabled={isStreaming}
            className="flex-1 h-9 rounded-md border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isStreaming}
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </form>
    </aside>
  );
}
