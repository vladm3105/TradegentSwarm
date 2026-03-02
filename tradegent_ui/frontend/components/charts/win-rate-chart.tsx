'use client';

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { CustomTooltipProps, WinRateDataPoint } from '@/types/recharts';

interface WinRateChartProps {
  winRate: number;
  totalTrades: number;
  title?: string;
  height?: number;
}

export function WinRateChart({
  winRate,
  totalTrades,
  title = 'Win Rate',
  height = 200,
}: WinRateChartProps) {
  const wins = Math.round((winRate / 100) * totalTrades);
  const losses = totalTrades - wins;

  const data: WinRateDataPoint[] = [
    { name: 'Wins', value: wins },
    { name: 'Losses', value: losses },
  ];

  const COLORS = ['hsl(var(--gain))', 'hsl(var(--loss))'];

  const CustomTooltip = ({ active, payload }: CustomTooltipProps<WinRateDataPoint>) => {
    if (!active || !payload?.length) return null;

    return (
      <div className="bg-background border rounded-lg shadow-lg p-3">
        <p className="font-semibold">{payload[0].name}</p>
        <p className="text-sm">{payload[0].value} trades</p>
      </div>
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-center">
          <ResponsiveContainer width="100%" height={height}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={70}
                paddingAngle={2}
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index]}
                  />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="text-center mt-4">
          <p className="text-3xl font-bold text-gain">{winRate.toFixed(1)}%</p>
          <p className="text-sm text-muted-foreground">{totalTrades} total trades</p>
        </div>
      </CardContent>
    </Card>
  );
}
