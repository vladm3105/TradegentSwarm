'use client';

import { useMemo } from 'react';
import { WidgetManager, useWidgetConfig, WidgetConfig } from './widget-manager';

// Widget components - lazy imports would be better for production
import { LivePnL } from './live-pnl';
import { LiveTicker } from './live-ticker';
import { MarketStatus } from './market-status';
import { ServiceHealth } from './service-health';
import { TradingControls } from './trading-controls';
import { OpenOrders } from './open-orders';
import { BracketOrderForm } from './bracket-order-form';
import { EquityCurve } from './equity-curve';
import { PortfolioHeatmap } from './portfolio-heatmap';
import { WinRateDashboard } from './win-rate-dashboard';
import { PositionSizer } from './position-sizer';
import { ScheduleManager } from './schedule-manager';
import { NotificationCenter } from './notification-center';
import { DailySummary } from './daily-summary';

// Widget registry mapping IDs to components
const widgetComponents: Record<string, React.ComponentType<unknown>> = {
  'live-pnl': LivePnL as React.ComponentType<unknown>,
  'live-ticker': LiveTicker as React.ComponentType<unknown>,
  'market-status': MarketStatus as React.ComponentType<unknown>,
  'service-health': ServiceHealth as React.ComponentType<unknown>,
  'trading-controls': TradingControls as React.ComponentType<unknown>,
  'open-orders': OpenOrders as React.ComponentType<unknown>,
  'bracket-order': BracketOrderForm as React.ComponentType<unknown>,
  'equity-curve': EquityCurve as React.ComponentType<unknown>,
  'portfolio-heatmap': PortfolioHeatmap as React.ComponentType<unknown>,
  'win-rate': WinRateDashboard as React.ComponentType<unknown>,
  'position-sizer': PositionSizer as React.ComponentType<unknown>,
  'schedule-manager': ScheduleManager as React.ComponentType<unknown>,
  'notification-center': NotificationCenter as React.ComponentType<unknown>,
  'daily-summary': DailySummary as React.ComponentType<unknown>,
};

// Size to grid class mapping
const sizeClasses: Record<string, string> = {
  small: 'col-span-1',
  medium: 'col-span-1 md:col-span-2',
  large: 'col-span-1 md:col-span-2 lg:col-span-3',
  full: 'col-span-1 md:col-span-2 lg:col-span-4',
};

interface DashboardLayoutProps {
  className?: string;
}

export function DashboardLayout({ className = '' }: DashboardLayoutProps) {
  const { widgets, enabledWidgets, toggleWidget, reorderWidget, resetToDefaults } = useWidgetConfig();

  // Group widgets by row based on size
  const renderedWidgets = useMemo(() => {
    return enabledWidgets.map((widget: WidgetConfig) => {
      const Component = widgetComponents[widget.id];
      if (!Component) return null;

      return (
        <div
          key={widget.id}
          className={`${sizeClasses[widget.size]} transition-all duration-200`}
        >
          <Component />
        </div>
      );
    });
  }, [enabledWidgets]);

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Dashboard Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trading Dashboard</h1>
        <WidgetManager
          widgets={widgets}
          onToggle={toggleWidget}
          onReorder={reorderWidget}
          onReset={resetToDefaults}
        />
      </div>

      {/* Responsive Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {renderedWidgets}
      </div>
    </div>
  );
}

// Export individual widget wrapper for custom layouts
interface WidgetWrapperProps {
  widgetId: string;
  className?: string;
}

export function WidgetWrapper({ widgetId, className = '' }: WidgetWrapperProps) {
  const Component = widgetComponents[widgetId];
  if (!Component) return null;
  return (
    <div className={className}>
      <Component />
    </div>
  );
}
