'use client';

import { useState, useEffect, useCallback } from 'react';
import { Bell, Check, AlertTriangle, Info, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { createLogger } from '@/lib/logger';
import { getSession } from 'next-auth/react';

const log = createLogger('notification-center');

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

interface Notification {
  id: number;
  type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  title: string;
  message: string | null;
  is_read: boolean;
  created_at: string;
}

async function fetchWithAuth<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const session = await getSession();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: { ...headers, ...options?.headers },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

const severityIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  info: Info,
  warning: AlertTriangle,
  error: AlertCircle,
  critical: AlertTriangle,
};

const severityColors: Record<string, string> = {
  info: 'text-blue-500',
  warning: 'text-yellow-500',
  error: 'text-red-500',
  critical: 'text-red-600',
};

export function NotificationCenter() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const loadNotifications = useCallback(async () => {
    try {
      setLoading(true);
      const [notifs, count] = await Promise.all([
        fetchWithAuth<Notification[]>('/api/notifications?limit=20'),
        fetchWithAuth<{ unread: number }>('/api/notifications/count'),
      ]);
      setNotifications(notifs);
      setUnreadCount(count.unread);
    } catch (error) {
      log.error('Failed to load notifications', { error: String(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNotifications();
    // Poll for new notifications every 30 seconds
    const interval = setInterval(loadNotifications, 30000);
    return () => clearInterval(interval);
  }, [loadNotifications]);

  // Refresh when dropdown opens
  useEffect(() => {
    if (open) {
      loadNotifications();
    }
  }, [open, loadNotifications]);

  async function markAsRead(id: number) {
    try {
      await fetchWithAuth(`/api/notifications/${id}/read`, { method: 'PATCH' });
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      log.error('Failed to mark as read', { error: String(error) });
    }
  }

  async function markAllAsRead() {
    try {
      await fetchWithAuth('/api/notifications/read-all', { method: 'POST' });
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      log.error('Failed to mark all as read', { error: String(error) });
    }
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-80 p-0" align="end">
        <div className="flex items-center justify-between p-4 border-b">
          <h4 className="font-semibold">Notifications</h4>
          {unreadCount > 0 && (
            <Button type="button" variant="ghost" size="sm" onClick={markAllAsRead}>
              <Check className="h-4 w-4 mr-1" />
              Mark all read
            </Button>
          )}
        </div>
        <ScrollArea className="h-[400px]">
          {loading && notifications.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground">
              Loading...
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground">
              No notifications
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map(notif => {
                const Icon = severityIcons[notif.severity] || Info;
                return (
                  <div
                    key={notif.id}
                    className={`p-4 hover:bg-muted/50 cursor-pointer ${
                      !notif.is_read ? 'bg-muted/30' : ''
                    }`}
                    onClick={() => !notif.is_read && markAsRead(notif.id)}
                  >
                    <div className="flex gap-3">
                      <Icon className={`h-5 w-5 flex-shrink-0 ${severityColors[notif.severity]}`} />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{notif.title}</p>
                        {notif.message && (
                          <p className="text-sm text-muted-foreground truncate">
                            {notif.message}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">
                          {formatTimeAgo(notif.created_at)}
                        </p>
                      </div>
                      {!notif.is_read && (
                        <div className="h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
