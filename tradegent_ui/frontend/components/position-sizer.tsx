'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Calculator, AlertTriangle } from 'lucide-react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('position-sizer');
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

interface PositionSizeResult {
  position_size: number;
  dollar_risk: number;
  risk_per_share: number;
  total_cost: number;
  portfolio_weight_pct: number;
}

async function calculateSize(params: {
  account_size: number;
  risk_per_trade_pct: number;
  entry_price: number;
  stop_loss_price: number;
}): Promise<PositionSizeResult> {
  const session = await getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const response = await fetch(`${API_URL}/api/analytics/position-size`, {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function formatCurrency(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  });
}

export function PositionSizer() {
  const [accountSize, setAccountSize] = useState<string>('100000');
  const [riskPct, setRiskPct] = useState<string>('1');
  const [entryPrice, setEntryPrice] = useState<string>('');
  const [stopPrice, setStopPrice] = useState<string>('');
  const [result, setResult] = useState<PositionSizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCalculate() {
    const account = parseFloat(accountSize);
    const risk = parseFloat(riskPct);
    const entry = parseFloat(entryPrice);
    const stop = parseFloat(stopPrice);

    if (isNaN(account) || isNaN(risk) || isNaN(entry) || isNaN(stop)) {
      setError('Please fill in all fields with valid numbers');
      return;
    }

    if (entry === stop) {
      setError('Entry price and stop price cannot be the same');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await calculateSize({
        account_size: account,
        risk_per_trade_pct: risk,
        entry_price: entry,
        stop_loss_price: stop,
      });
      setResult(res);
    } catch (e) {
      log.error('Position size calculation failed', { error: String(e) });
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const isLong = parseFloat(entryPrice) > parseFloat(stopPrice);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Calculator className="h-4 w-4" />
          Position Sizer
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Inputs */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">Account Size</label>
            <Input
              type="number"
              value={accountSize}
              onChange={(e) => setAccountSize(e.target.value)}
              placeholder="100000"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Risk per Trade (%)</label>
            <Input
              type="number"
              value={riskPct}
              onChange={(e) => setRiskPct(e.target.value)}
              placeholder="1"
              step="0.5"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Entry Price</label>
            <Input
              type="number"
              value={entryPrice}
              onChange={(e) => setEntryPrice(e.target.value)}
              placeholder="150.00"
              step="0.01"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Stop Loss Price</label>
            <Input
              type="number"
              value={stopPrice}
              onChange={(e) => setStopPrice(e.target.value)}
              placeholder="145.00"
              step="0.01"
            />
          </div>
        </div>

        <Button
          type="button"
          onClick={handleCalculate}
          disabled={loading}
          className="w-full"
        >
          {loading ? 'Calculating...' : 'Calculate Position Size'}
        </Button>

        {error && (
          <div className="text-red-500 text-sm flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-3 pt-4 border-t">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Direction</span>
              <Badge variant={isLong ? 'default' : 'destructive'}>
                {isLong ? 'LONG' : 'SHORT'}
              </Badge>
            </div>

            <div className="p-4 rounded-lg bg-muted/50 text-center">
              <div className="text-xs text-muted-foreground">Position Size</div>
              <div className="text-3xl font-bold font-mono">
                {result.position_size.toLocaleString()} shares
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="p-3 rounded-lg bg-muted/30">
                <div className="text-xs text-muted-foreground">Dollar Risk</div>
                <div className="font-mono font-medium text-red-500">
                  {formatCurrency(result.dollar_risk)}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted/30">
                <div className="text-xs text-muted-foreground">Risk per Share</div>
                <div className="font-mono font-medium">
                  {formatCurrency(result.risk_per_share)}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted/30">
                <div className="text-xs text-muted-foreground">Total Cost</div>
                <div className="font-mono font-medium">
                  {formatCurrency(result.total_cost)}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted/30">
                <div className="text-xs text-muted-foreground">Portfolio Weight</div>
                <div className="font-mono font-medium">
                  {result.portfolio_weight_pct.toFixed(1)}%
                </div>
              </div>
            </div>

            {result.portfolio_weight_pct > 20 && (
              <div className="flex items-center gap-2 text-yellow-600 text-sm p-2 bg-yellow-50 rounded">
                <AlertTriangle className="h-4 w-4" />
                Position exceeds 20% of portfolio - consider reducing size
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
