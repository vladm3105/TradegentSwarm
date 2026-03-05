'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Settings2, GripVertical, Eye, EyeOff } from 'lucide-react';
import { createLogger } from '@/lib/logger';

const log = createLogger('widget-manager');

export interface WidgetConfig {
  id: string;
  name: string;
  enabled: boolean;
  order: number;
  size: 'small' | 'medium' | 'large' | 'full';
  category: 'trading' | 'analytics' | 'monitoring' | 'orders';
}

const DEFAULT_WIDGETS: WidgetConfig[] = [
  { id: 'live-pnl', name: 'Live P&L', enabled: true, order: 0, size: 'medium', category: 'monitoring' },
  { id: 'live-ticker', name: 'Live Ticker', enabled: true, order: 1, size: 'small', category: 'monitoring' },
  { id: 'market-status', name: 'Market Status', enabled: true, order: 2, size: 'small', category: 'monitoring' },
  { id: 'service-health', name: 'Service Health', enabled: true, order: 3, size: 'small', category: 'monitoring' },
  { id: 'trading-controls', name: 'Trading Controls', enabled: true, order: 4, size: 'medium', category: 'trading' },
  { id: 'open-orders', name: 'Open Orders', enabled: true, order: 5, size: 'large', category: 'orders' },
  { id: 'bracket-order', name: 'Bracket Order Form', enabled: true, order: 6, size: 'medium', category: 'orders' },
  { id: 'equity-curve', name: 'Equity Curve', enabled: true, order: 7, size: 'large', category: 'analytics' },
  { id: 'portfolio-heatmap', name: 'Portfolio Heatmap', enabled: false, order: 8, size: 'large', category: 'analytics' },
  { id: 'win-rate', name: 'Win Rate Dashboard', enabled: false, order: 9, size: 'medium', category: 'analytics' },
  { id: 'position-sizer', name: 'Position Sizer', enabled: false, order: 10, size: 'medium', category: 'trading' },
  { id: 'schedule-manager', name: 'Schedule Manager', enabled: true, order: 11, size: 'medium', category: 'orders' },
  { id: 'notification-center', name: 'Notifications', enabled: true, order: 12, size: 'small', category: 'monitoring' },
  { id: 'daily-summary', name: 'Daily Summary', enabled: true, order: 13, size: 'large', category: 'analytics' },
];

const STORAGE_KEY = 'tradegent_widget_config';

export function useWidgetConfig() {
  const [widgets, setWidgets] = useState<WidgetConfig[]>(DEFAULT_WIDGETS);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as WidgetConfig[];
        // Merge with defaults to handle new widgets
        const merged = DEFAULT_WIDGETS.map(defaultWidget => {
          const savedWidget = parsed.find(w => w.id === defaultWidget.id);
          return savedWidget ? { ...defaultWidget, ...savedWidget } : defaultWidget;
        });
        setWidgets(merged.sort((a, b) => a.order - b.order));
      } catch {
        setWidgets(DEFAULT_WIDGETS);
      }
    }
  }, []);

  const saveWidgets = useCallback((newWidgets: WidgetConfig[]) => {
    setWidgets(newWidgets);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newWidgets));
    log.action('widgets_saved', { count: newWidgets.filter(w => w.enabled).length });
  }, []);

  const toggleWidget = useCallback((id: string) => {
    setWidgets(prev => {
      const updated = prev.map(w =>
        w.id === id ? { ...w, enabled: !w.enabled } : w
      );
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  }, []);

  const reorderWidget = useCallback((id: string, direction: 'up' | 'down') => {
    setWidgets(prev => {
      const index = prev.findIndex(w => w.id === id);
      if (index === -1) return prev;
      if (direction === 'up' && index === 0) return prev;
      if (direction === 'down' && index === prev.length - 1) return prev;

      const newWidgets = [...prev];
      const swapIndex = direction === 'up' ? index - 1 : index + 1;

      // Swap orders
      const tempOrder = newWidgets[index].order;
      newWidgets[index] = { ...newWidgets[index], order: newWidgets[swapIndex].order };
      newWidgets[swapIndex] = { ...newWidgets[swapIndex], order: tempOrder };

      // Sort by order
      newWidgets.sort((a, b) => a.order - b.order);

      localStorage.setItem(STORAGE_KEY, JSON.stringify(newWidgets));
      return newWidgets;
    });
  }, []);

  const resetToDefaults = useCallback(() => {
    setWidgets(DEFAULT_WIDGETS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_WIDGETS));
    log.action('widgets_reset');
  }, []);

  return {
    widgets,
    enabledWidgets: widgets.filter(w => w.enabled),
    toggleWidget,
    reorderWidget,
    saveWidgets,
    resetToDefaults,
  };
}

const categoryColors: Record<string, string> = {
  trading: 'bg-green-500',
  analytics: 'bg-blue-500',
  monitoring: 'bg-yellow-500',
  orders: 'bg-purple-500',
};

interface WidgetManagerProps {
  widgets: WidgetConfig[];
  onToggle: (id: string) => void;
  onReorder: (id: string, direction: 'up' | 'down') => void;
  onReset: () => void;
}

export function WidgetManager({ widgets, onToggle, onReorder, onReset }: WidgetManagerProps) {
  const [open, setOpen] = useState(false);
  const enabledCount = widgets.filter(w => w.enabled).length;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" className="gap-2">
          <Settings2 className="h-4 w-4" />
          Widgets ({enabledCount})
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Dashboard Widgets</span>
            <Button type="button" variant="ghost" size="sm" onClick={onReset}>
              Reset
            </Button>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-2 mt-4">
          {widgets.map((widget, index) => (
            <div
              key={widget.id}
              className={`flex items-center gap-3 p-3 rounded-lg border ${
                widget.enabled ? 'bg-background' : 'bg-muted/50 opacity-60'
              }`}
            >
              <div className="flex flex-col gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-5 w-5 p-0"
                  onClick={() => onReorder(widget.id, 'up')}
                  disabled={index === 0}
                >
                  <GripVertical className="h-3 w-3 rotate-90" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-5 w-5 p-0"
                  onClick={() => onReorder(widget.id, 'down')}
                  disabled={index === widgets.length - 1}
                >
                  <GripVertical className="h-3 w-3 rotate-90" />
                </Button>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium truncate">{widget.name}</span>
                  <Badge className={`${categoryColors[widget.category]} text-xs`}>
                    {widget.category}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                  Size: {widget.size}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {widget.enabled ? (
                  <Eye className="h-4 w-4 text-green-500" />
                ) : (
                  <EyeOff className="h-4 w-4 text-muted-foreground" />
                )}
                <Switch
                  checked={widget.enabled}
                  onCheckedChange={() => onToggle(widget.id)}
                />
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
