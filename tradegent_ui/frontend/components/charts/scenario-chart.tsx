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
  LabelList,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatPercent, cn, getPnlColor } from '@/lib/utils';
import type { CustomTooltipProps, ScenarioDataPoint } from '@/types/recharts';

interface ScenarioChartProps {
  scenarios: ScenarioDataPoint[];
  weighted_ev: number;
  height?: number;
}

export function ScenarioChartRecharts({
  scenarios,
  weighted_ev,
  height = 200,
}: ScenarioChartProps) {
  const CustomTooltip = ({ active, payload }: CustomTooltipProps<ScenarioDataPoint>) => {
    if (!active || !payload?.length) return null;

    const item = payload[0].payload;
    return (
      <div className="bg-background border rounded-lg shadow-lg p-3">
        <p className="font-semibold">{item.name}</p>
        <p className="text-sm">Probability: {item.probability}%</p>
        <p className={cn('text-sm', getPnlColor(item.return_pct))}>
          Return: {formatPercent(item.return_pct)}
        </p>
        {item.description && (
          <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
        )}
      </div>
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Scenarios</CardTitle>
          <span className={cn('font-semibold', getPnlColor(weighted_ev))}>
            EV: {formatPercent(weighted_ev)}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart
            data={scenarios}
            layout="vertical"
            margin={{ top: 5, right: 60, left: 60, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              type="number"
              domain={[0, 100]}
              tickFormatter={(value) => `${value}%`}
              className="text-xs"
            />
            <YAxis
              dataKey="name"
              type="category"
              className="text-xs"
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="probability" radius={[0, 4, 4, 0]}>
              {scenarios.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={
                    entry.return_pct >= 0
                      ? 'hsl(var(--gain))'
                      : 'hsl(var(--loss))'
                  }
                />
              ))}
              <LabelList
                dataKey="return_pct"
                position="right"
                formatter={(value: number) => formatPercent(value)}
                className="text-xs fill-foreground"
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
