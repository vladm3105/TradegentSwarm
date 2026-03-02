'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCurrency } from '@/lib/utils';
import type { CustomTooltipProps, PnLDataPoint } from '@/types/recharts';

interface PnLChartProps {
  data: PnLDataPoint[];
  title?: string;
  showCumulative?: boolean;
  height?: number;
}

export function PnLChart({
  data,
  title = 'Daily P&L',
  showCumulative = false,
  height = 300,
}: PnLChartProps) {
  const dataKey = showCumulative ? 'cumulative' : 'pnl';

  const CustomTooltip = ({ active, payload, label }: CustomTooltipProps<PnLDataPoint>) => {
    if (!active || !payload?.length) return null;

    const value = payload[0].value as number;
    return (
      <div className="bg-background border rounded-lg shadow-lg p-3">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p
          className={`text-sm font-semibold ${value >= 0 ? 'text-gain' : 'text-loss'}`}
        >
          {formatCurrency(value, { showSign: true })}
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
          <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="date"
              tickFormatter={(value) => {
                const date = new Date(value);
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
              className="text-xs"
            />
            <YAxis
              tickFormatter={(value) => `$${(value / 1000).toFixed(1)}k`}
              className="text-xs"
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
