'use client';

import { usePortfolioStream } from '@/hooks/use-portfolio-stream';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, DollarSign, Activity } from 'lucide-react';

function formatCurrency(value: number | undefined): string {
  if (value === undefined || value === null) return '--';
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function PnLValue({ label, value, showSign = false }: { label: string; value: number | undefined; showSign?: boolean }) {
  const isPositive = (value ?? 0) > 0;
  const isNegative = (value ?? 0) < 0;

  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`font-mono font-medium ${isPositive ? 'text-green-500' : isNegative ? 'text-red-500' : ''}`}>
        {showSign && (value ?? 0) > 0 ? '+' : ''}
        {formatCurrency(value)}
      </span>
    </div>
  );
}

export function LivePnL() {
  const { portfolio, connected, error } = usePortfolioStream();

  const pnl = portfolio?.pnl;
  const dailyPnl = pnl?.daily_pnl ?? 0;
  const isUp = dailyPnl > 0;
  const isDown = dailyPnl < 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Portfolio P&L
          </div>
          {connected ? (
            <Badge variant="default" className="text-xs">Live</Badge>
          ) : (
            <Badge variant="secondary" className="text-xs animate-pulse">Connecting</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="text-red-500 text-sm mb-2">{error}</div>
        )}

        {/* Daily P&L - Hero metric */}
        <div className={`p-4 rounded-lg mb-4 ${isUp ? 'bg-green-50' : isDown ? 'bg-red-50' : 'bg-gray-50'}`}>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Today's P&L</span>
            {isUp && <TrendingUp className="h-5 w-5 text-green-500" />}
            {isDown && <TrendingDown className="h-5 w-5 text-red-500" />}
          </div>
          <div className={`text-2xl font-bold font-mono ${isUp ? 'text-green-600' : isDown ? 'text-red-600' : ''}`}>
            {dailyPnl > 0 ? '+' : ''}{formatCurrency(dailyPnl)}
          </div>
        </div>

        {/* Other P&L metrics */}
        <div className="space-y-1">
          <PnLValue label="Unrealized P&L" value={pnl?.unrealized_pnl} showSign />
          <PnLValue label="Realized P&L" value={pnl?.realized_pnl} showSign />
          <div className="border-t mt-2 pt-2">
            <PnLValue label="Net Liquidation" value={pnl?.net_liquidation} />
          </div>
        </div>

        {/* Position count */}
        {portfolio?.positions && (
          <div className="mt-4 pt-3 border-t">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Open Positions</span>
              <Badge variant="outline">{portfolio.positions.length}</Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
