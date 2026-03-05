'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ArrowUpCircle, ArrowDownCircle, AlertTriangle, CheckCircle } from 'lucide-react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('bracket-order-form');
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

interface BracketOrderResult {
  success: boolean;
  parent_order_id: string | null;
  stop_order_id: string | null;
  profit_order_id: string | null;
  message: string;
}

async function placeBracketOrder(params: {
  symbol: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  entry_type: 'MARKET' | 'LIMIT';
  entry_price?: number;
  stop_loss_price: number;
  take_profit_price?: number;
}): Promise<BracketOrderResult> {
  const session = await getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const response = await fetch(`${API_URL}/api/orders/bracket`, {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
  });

  return response.json();
}

function formatCurrency(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  });
}

export function BracketOrderForm() {
  const [symbol, setSymbol] = useState('');
  const [action, setAction] = useState<'BUY' | 'SELL'>('BUY');
  const [quantity, setQuantity] = useState('');
  const [entryType, setEntryType] = useState<'MARKET' | 'LIMIT'>('LIMIT');
  const [entryPrice, setEntryPrice] = useState('');
  const [stopPrice, setStopPrice] = useState('');
  const [targetPrice, setTargetPrice] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BracketOrderResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!symbol || !quantity || !stopPrice) {
      setError('Symbol, quantity, and stop price are required');
      return;
    }

    if (entryType === 'LIMIT' && !entryPrice) {
      setError('Entry price is required for limit orders');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await placeBracketOrder({
        symbol: symbol.toUpperCase(),
        action,
        quantity: parseInt(quantity),
        entry_type: entryType,
        entry_price: entryPrice ? parseFloat(entryPrice) : undefined,
        stop_loss_price: parseFloat(stopPrice),
        take_profit_price: targetPrice ? parseFloat(targetPrice) : undefined,
      });

      setResult(res);
      if (res.success) {
        log.action('bracket_order_placed', { symbol, action, quantity });
      }
    } catch (e) {
      log.error('Bracket order failed', { error: String(e) });
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const entry = entryPrice ? parseFloat(entryPrice) : 0;
  const stop = stopPrice ? parseFloat(stopPrice) : 0;
  const target = targetPrice ? parseFloat(targetPrice) : 0;
  const qty = quantity ? parseInt(quantity) : 0;

  const riskPerShare = entry && stop ? Math.abs(entry - stop) : 0;
  const rewardPerShare = entry && target ? Math.abs(target - entry) : 0;
  const riskReward = riskPerShare > 0 && rewardPerShare > 0 ? rewardPerShare / riskPerShare : 0;
  const totalRisk = riskPerShare * qty;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Bracket Order</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Action Toggle */}
        <div className="flex gap-2">
          <Button
            type="button"
            variant={action === 'BUY' ? 'default' : 'outline'}
            className={action === 'BUY' ? 'bg-green-500 hover:bg-green-600 flex-1' : 'flex-1'}
            onClick={() => setAction('BUY')}
          >
            <ArrowUpCircle className="h-4 w-4 mr-2" />
            BUY
          </Button>
          <Button
            type="button"
            variant={action === 'SELL' ? 'default' : 'outline'}
            className={action === 'SELL' ? 'bg-red-500 hover:bg-red-600 flex-1' : 'flex-1'}
            onClick={() => setAction('SELL')}
          >
            <ArrowDownCircle className="h-4 w-4 mr-2" />
            SELL
          </Button>
        </div>

        {/* Symbol and Quantity */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">Symbol</label>
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="NVDA"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Quantity</label>
            <Input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="100"
            />
          </div>
        </div>

        {/* Entry Type and Price */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">Entry Type</label>
            <div className="flex gap-1">
              <Button
                type="button"
                variant={entryType === 'MARKET' ? 'default' : 'outline'}
                size="sm"
                className="flex-1"
                onClick={() => setEntryType('MARKET')}
              >
                Market
              </Button>
              <Button
                type="button"
                variant={entryType === 'LIMIT' ? 'default' : 'outline'}
                size="sm"
                className="flex-1"
                onClick={() => setEntryType('LIMIT')}
              >
                Limit
              </Button>
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Entry Price</label>
            <Input
              type="number"
              value={entryPrice}
              onChange={(e) => setEntryPrice(e.target.value)}
              placeholder="150.00"
              step="0.01"
              disabled={entryType === 'MARKET'}
            />
          </div>
        </div>

        {/* Stop and Target */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">Stop Loss *</label>
            <Input
              type="number"
              value={stopPrice}
              onChange={(e) => setStopPrice(e.target.value)}
              placeholder="145.00"
              step="0.01"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Take Profit</label>
            <Input
              type="number"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              placeholder="160.00"
              step="0.01"
            />
          </div>
        </div>

        {/* Risk/Reward Preview */}
        {entry > 0 && stop > 0 && (
          <div className="p-3 rounded-lg bg-muted/50 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Risk per Share</span>
              <span className="font-mono text-red-500">{formatCurrency(riskPerShare)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total Risk</span>
              <span className="font-mono text-red-500">{formatCurrency(totalRisk)}</span>
            </div>
            {riskReward > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Risk:Reward</span>
                <Badge variant={riskReward >= 2 ? 'default' : 'secondary'}>
                  1:{riskReward.toFixed(1)}
                </Badge>
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 text-red-500 text-sm">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={`p-3 rounded-lg ${result.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
            <div className="flex items-center gap-2 font-medium">
              {result.success ? <CheckCircle className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
              {result.message}
            </div>
            {result.success && (
              <div className="text-xs mt-1 space-y-1">
                <div>Parent: {result.parent_order_id}</div>
                <div>Stop: {result.stop_order_id}</div>
                {result.profit_order_id && <div>Target: {result.profit_order_id}</div>}
              </div>
            )}
          </div>
        )}

        {/* Submit */}
        <Button
          type="button"
          onClick={handleSubmit}
          disabled={loading}
          className={`w-full ${action === 'BUY' ? 'bg-green-500 hover:bg-green-600' : 'bg-red-500 hover:bg-red-600'}`}
        >
          {loading ? 'Placing Order...' : `Place ${action} Bracket Order`}
        </Button>
      </CardContent>
    </Card>
  );
}
