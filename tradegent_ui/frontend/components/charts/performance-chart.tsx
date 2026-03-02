'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCurrency } from '@/lib/utils';
import type { CustomTooltipProps, PerformanceDataPoint } from '@/types/recharts';

interface PerformanceChartProps {
  data: PerformanceDataPoint[];
  title?: string;
  height?: number;
}

export function PerformanceChart({
  data,
  title = 'Ticker Performance',
  height = 300,
}: PerformanceChartProps) {
  const CustomTooltip = ({ active, payload, label }: CustomTooltipProps<PerformanceDataPoint>) => {
    if (!active || !payload?.length) return null;

    const item = payload[0].payload;
    return (
      <div className="bg-background border rounded-lg shadow-lg p-3">
        <p className="font-semibold">{label}</p>
        <p className={`text-sm ${item.pnl >= 0 ? 'text-gain' : 'text-loss'}`}>
          P&L: {formatCurrency(item.pnl, { showSign: true })}
        </p>
        <p className="text-sm text-muted-foreground">
          Win Rate: {item.win_rate.toFixed(1)}%
        </p>
        <p className="text-sm text-muted-foreground">
          Trades: {item.trades}
        </p>
      </div>
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              type="number"
              tickFormatter={(value) => `$${(value / 1000).toFixed(1)}k`}
              className="text-xs"
            />
            <YAxis
              dataKey="ticker"
              type="category"
              className="text-xs font-medium"
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.pnl >= 0 ? 'hsl(var(--gain))' : 'hsl(var(--loss))'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
