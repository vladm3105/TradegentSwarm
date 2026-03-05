'use client';

import { usePriceStream, PriceData } from '@/hooks/use-price-stream';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface LiveTickerProps {
  tickers: string[];
  compact?: boolean;
}

function formatPrice(price: number | undefined): string {
  if (price === undefined || price === null) return '--';
  return price.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  });
}

function formatChange(change: number | undefined, changePct: number | undefined): string {
  if (change === undefined || changePct === undefined) return '--';
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
}

function TickerRow({ ticker, data }: { ticker: string; data: PriceData | undefined }) {
  const change = data?.change ?? 0;
  const isUp = change > 0;
  const isDown = change < 0;

  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex items-center gap-2">
        <span className="font-semibold">{ticker}</span>
        {isUp && <TrendingUp className="h-4 w-4 text-green-500" />}
        {isDown && <TrendingDown className="h-4 w-4 text-red-500" />}
        {!isUp && !isDown && <Minus className="h-4 w-4 text-gray-400" />}
      </div>
      <div className="text-right">
        <div className="font-mono">{formatPrice(data?.last)}</div>
        <div className={`text-sm ${isUp ? 'text-green-500' : isDown ? 'text-red-500' : 'text-gray-500'}`}>
          {formatChange(data?.change, data?.changePct)}
        </div>
      </div>
    </div>
  );
}

function CompactTicker({ ticker, data }: { ticker: string; data: PriceData | undefined }) {
  const change = data?.change ?? 0;
  const isUp = change > 0;
  const isDown = change < 0;

  return (
    <Badge
      variant="outline"
      className={`px-3 py-1 ${isUp ? 'border-green-500 text-green-600' : isDown ? 'border-red-500 text-red-600' : ''}`}
    >
      <span className="font-semibold mr-2">{ticker}</span>
      <span className="font-mono">{formatPrice(data?.last)}</span>
      {data?.changePct !== undefined && (
        <span className="ml-1 text-xs">
          ({data.changePct >= 0 ? '+' : ''}{data.changePct.toFixed(1)}%)
        </span>
      )}
    </Badge>
  );
}

export function LiveTicker({ tickers, compact = false }: LiveTickerProps) {
  const { prices, connected, error } = usePriceStream({ tickers, enabled: tickers.length > 0 });

  if (compact) {
    return (
      <div className="flex flex-wrap gap-2">
        {!connected && (
          <Badge variant="secondary" className="animate-pulse">
            Connecting...
          </Badge>
        )}
        {error && (
          <Badge variant="destructive">{error}</Badge>
        )}
        {tickers.map(ticker => (
          <CompactTicker key={ticker} ticker={ticker} data={prices[ticker]} />
        ))}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          Live Prices
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
        {tickers.length === 0 ? (
          <div className="text-muted-foreground text-sm">No tickers selected</div>
        ) : (
          <div className="space-y-1">
            {tickers.map(ticker => (
              <TickerRow key={ticker} ticker={ticker} data={prices[ticker]} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
