'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  Target,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  BarChart3,
  Lightbulb,
  AlertCircle,
} from 'lucide-react';
import type {
  AnalysisDetail,
  Scenario,
} from '@/types/analysis';
import {
  getRecommendationColor,
  getGateResultColor,
  getThreatLevelColor,
  getPricePositionPct,
  formatMarketCap,
  formatPctWithSign,
} from '@/types/analysis';

interface AnalysisDetailViewProps {
  analysis: AnalysisDetail;
  className?: string;
}

// Gate Criterion Row Component
function GateCriterion({
  label,
  threshold,
  actual,
  passes,
}: {
  label: string;
  threshold: string;
  actual: string;
  passes: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-medium">{actual}</span>
        <div
          className={cn(
            'w-5 h-5 rounded-full flex items-center justify-center text-xs text-white',
            passes ? 'bg-green-500' : 'bg-red-500'
          )}
        >
          {passes ? '✓' : '✗'}
        </div>
      </div>
    </div>
  );
}

// Scenario Bar Component
function ScenarioBar({
  label,
  scenario,
  maxReturn = 150,
}: {
  label: string;
  scenario: Scenario;
  maxReturn?: number;
}) {
  const isPositive = scenario.return_pct >= 0;
  const width = Math.min(100, Math.abs(scenario.return_pct) / maxReturn * 100);

  return (
    <div className="flex items-center gap-3 py-1">
      <span className="text-sm w-28 shrink-0">{label} ({scenario.probability}%)</span>
      <div
        className={cn(
          'h-5 rounded',
          isPositive
            ? scenario.probability >= 30 ? 'bg-green-500' : 'bg-green-400'
            : scenario.probability >= 20 ? 'bg-red-500' : 'bg-red-400'
        )}
        style={{ width: `${width}%`, minWidth: '20px' }}
      />
      <span className={cn('text-sm font-medium', isPositive ? 'text-green-600' : 'text-red-600')}>
        {formatPctWithSign(scenario.return_pct)} → ${scenario.target_price}
      </span>
    </div>
  );
}

// Case Strength Bar Component
function StrengthBar({
  label,
  strength,
  color,
}: {
  label: string;
  strength: number;
  color: 'green' | 'yellow' | 'red';
}) {
  const colorClass = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  }[color];

  return (
    <div className="flex items-center gap-3 py-1">
      <span className="text-sm w-20 shrink-0">{label}</span>
      <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
        <div className={cn('h-full rounded', colorClass)} style={{ width: `${strength * 10}%` }} />
      </div>
      <span className="text-sm font-medium w-10">{strength}/10</span>
    </div>
  );
}

// Bias Item Component
function BiasItem({ name, detected, severity }: { name: string; detected: boolean; severity: string }) {
  if (!detected) return null;
  const color =
    severity === 'high' ? 'text-red-500' :
    severity === 'medium' ? 'text-yellow-600' :
    'text-yellow-500';
  return (
    <div className={cn('text-xs', color)}>
      • {name} ({severity.toUpperCase()})
    </div>
  );
}

export function AnalysisDetailView({ analysis, className }: AnalysisDetailViewProps) {
  const gate = analysis.do_nothing_gate;
  const scenarios = analysis.scenarios;
  const setup = analysis.setup;
  const comparable = analysis.comparable_companies;
  const liquidity = analysis.liquidity_analysis;
  const sentiment = analysis.sentiment;
  const fundamentals = analysis.fundamentals;
  const biasCheck = analysis.bias_check;
  const alerts = analysis.alert_levels;
  const threat = analysis.threat_assessment;
  const altStrategies = analysis.alternative_strategies;
  const metaLearning = analysis.meta_learning;
  const newsCheck = analysis.news_age_check;
  const falsification = analysis.falsification;

  const pricePositionPct = getPricePositionPct(
    analysis.current_price,
    setup.fifty_two_week_low,
    setup.fifty_two_week_high
  );

  return (
    <div className={cn('space-y-4 p-4 bg-muted/30', className)}>
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-lg p-4 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">{analysis.ticker}</h1>
            <p className="text-sm text-slate-400">
              Stock Analysis v{analysis._meta.version} | {analysis.analysis_date}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {analysis._meta.status && !['completed', 'active'].includes(analysis._meta.status) && (
              <Badge
                variant="outline"
                className={cn(
                  'capitalize border-white/30 text-white',
                  analysis._meta.status === 'declined' && 'border-red-400/60 text-red-300 bg-red-900/30',
                  analysis._meta.status === 'error' && 'border-orange-400/60 text-orange-300 bg-orange-900/30',
                  analysis._meta.status === 'expired' && 'border-slate-400/60 text-slate-300',
                )}
              >
                {analysis._meta.status}
              </Badge>
            )}
            <Badge className={cn('text-lg px-6 py-2 rounded-full', getRecommendationColor(analysis.recommendation))}>
              {analysis.recommendation.replace('_', ' ')}
            </Badge>
          </div>
        </div>
      </div>

      {/* Row 1: Price Info, Key Metrics, Gate Decision */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Price Info */}
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">Current Price</p>
            <p className="text-3xl font-bold">${analysis.current_price.toFixed(2)}</p>
            <p className="text-sm text-muted-foreground mt-2">52-Week Range</p>
            <div className="mt-2">
              <div className="h-3 bg-muted rounded-full overflow-hidden relative">
                <div
                  className="h-full bg-gradient-to-r from-red-400 to-red-500 rounded-full"
                  style={{ width: `${pricePositionPct}%` }}
                />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-blue-500 rounded-full border-2 border-white"
                  style={{ left: `calc(${pricePositionPct}% - 8px)` }}
                />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>${setup.fifty_two_week_low.toFixed(2)}</span>
                <span className="text-blue-500">{pricePositionPct.toFixed(0)}% from low</span>
                <span>${setup.fifty_two_week_high.toFixed(2)}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Key Metrics */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Key Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Forward P/E</span>
              <span className="font-medium">{setup.pe_forward}x</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Market Cap</span>
              <span className="font-medium">{formatMarketCap(setup.market_cap_b)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">YTD Return</span>
              <span className={cn('font-medium', setup.ytd_return_pct >= 0 ? 'text-green-600' : 'text-red-600')}>
                {formatPctWithSign(setup.ytd_return_pct)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Next Earnings</span>
              <span className="font-medium">
                {setup.next_earnings_date}
                <span className="text-muted-foreground ml-1">({setup.days_to_earnings}d)</span>
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Gate Decision */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldCheck className="h-4 w-4" /> Gate Decision
              </CardTitle>
              <div className="flex items-center gap-2">
                <Badge className={cn('text-xs', getGateResultColor(gate.gate_result))}>
                  {gate.gate_result}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {gate.gates_passed}/4
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-0">
            <GateCriterion
              label="Expected Value >5%"
              threshold=">5%"
              actual={`${gate.ev_actual.toFixed(1)}%`}
              passes={gate.ev_passes}
            />
            <GateCriterion
              label="Confidence >60%"
              threshold=">60%"
              actual={`${gate.confidence_actual}%`}
              passes={gate.confidence_passes}
            />
            <GateCriterion
              label="Risk:Reward >2:1"
              threshold=">2:1"
              actual={`${gate.rr_actual.toFixed(1)}`}
              passes={gate.rr_passes}
            />
            <GateCriterion
              label="Edge Not Priced"
              threshold="Yes"
              actual={gate.edge_exists ? 'Yes' : 'No'}
              passes={gate.edge_exists}
            />
          </CardContent>
        </Card>
      </div>

      {/* Row 2: Scenario Analysis, Comparable Companies */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Scenario Analysis */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="h-4 w-4" /> Scenario Analysis
              </CardTitle>
              <span className="text-sm text-muted-foreground">EV: {scenarios.expected_value.toFixed(1)}%</span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <div className="flex-1 space-y-1">
                <ScenarioBar label="Strong Bull" scenario={scenarios.strong_bull} />
                <ScenarioBar label="Base Bull" scenario={scenarios.base_bull} />
                <ScenarioBar label="Base Bear" scenario={scenarios.base_bear} />
                <ScenarioBar label="Strong Bear" scenario={scenarios.strong_bear} />
              </div>
              {/* Mini EV Circle */}
              <div className="w-24 h-24 rounded-full border-8 border-muted flex flex-col items-center justify-center">
                <span className="text-xs text-muted-foreground">EV</span>
                <span className="text-lg font-bold">{scenarios.expected_value.toFixed(1)}%</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Comparable Companies */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Comparable Companies</CardTitle>
              <span className={cn(
                'text-xs',
                comparable.valuation_position === 'discount' ? 'text-red-500' : 'text-green-500'
              )}>
                {analysis.ticker} at {Math.abs(comparable.discount_premium_pct).toFixed(0)}%{' '}
                {comparable.valuation_position}
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left p-1.5 font-medium">Ticker</th>
                    <th className="text-right p-1.5 font-medium">P/E Fwd</th>
                    <th className="text-right p-1.5 font-medium">P/S</th>
                    <th className="text-right p-1.5 font-medium">EV/EBITDA</th>
                    <th className="text-right p-1.5 font-medium">Mkt Cap</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Subject row */}
                  <tr className="bg-yellow-100/50 dark:bg-yellow-900/20 font-medium">
                    <td className="p-1.5">{analysis.ticker}</td>
                    <td className="text-right p-1.5">{setup.pe_forward}</td>
                    <td className="text-right p-1.5">{fundamentals.valuation.ps_ratio}</td>
                    <td className="text-right p-1.5">{fundamentals.valuation.ev_ebitda}</td>
                    <td className="text-right p-1.5">{formatMarketCap(setup.market_cap_b)}</td>
                  </tr>
                  {comparable.peers.slice(0, 4).map((peer) => (
                    <tr key={peer.ticker} className="border-b">
                      <td className="p-1.5 text-muted-foreground">{peer.ticker}</td>
                      <td className="text-right p-1.5 text-muted-foreground">{peer.pe_forward}</td>
                      <td className="text-right p-1.5 text-muted-foreground">{peer.ps_ratio}</td>
                      <td className="text-right p-1.5 text-muted-foreground">{peer.ev_ebitda}</td>
                      <td className="text-right p-1.5 text-muted-foreground">{formatMarketCap(peer.market_cap_b)}</td>
                    </tr>
                  ))}
                  {/* Median row */}
                  <tr className="bg-muted/50 font-medium text-muted-foreground">
                    <td className="p-1.5">MEDIAN</td>
                    <td className="text-right p-1.5">{comparable.sector_median_pe ?? 'N/A'}</td>
                    <td className="text-right p-1.5">{comparable.sector_median_ps ?? 'N/A'}</td>
                    <td className="text-right p-1.5">{comparable.sector_median_ev_ebitda ?? 'N/A'}</td>
                    <td className="text-right p-1.5">-</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 3: Threat Assessment, Case Strength, Alternative Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Threat Assessment */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" /> Threat Assessment
              </CardTitle>
              <Badge className={cn('text-xs', getThreatLevelColor(threat.primary_concern))}>
                {(threat.primary_concern || 'NONE').toUpperCase()}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground line-clamp-3">
              {threat.threat_summary?.substring(0, 100)}...
            </p>
          </CardContent>
        </Card>

        {/* Case Strength */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Case Strength</CardTitle>
          </CardHeader>
          <CardContent>
            <StrengthBar label="Bull Case" strength={analysis.bull_case_analysis.strength} color="green" />
            <StrengthBar label="Base Case" strength={analysis.base_case_analysis.strength} color="yellow" />
            <StrengthBar label="Bear Case" strength={analysis.bear_case_analysis.strength} color="red" />
          </CardContent>
        </Card>

        {/* Alternative Actions */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Lightbulb className="h-4 w-4" /> Alternative Actions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {altStrategies?.strategies.slice(0, 3).map((strat, i) => (
              <div key={i} className="flex items-start gap-2 py-1">
                <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                <span className="text-sm text-muted-foreground">{strat.strategy}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Row 4: Liquidity, Confidence, Biases, Next Steps */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Liquidity Score */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Liquidity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn(
              'text-2xl font-bold',
              liquidity.liquidity_score >= 7 ? 'text-green-600' : liquidity.liquidity_score >= 5 ? 'text-yellow-600' : 'text-red-600'
            )}>
              {liquidity.liquidity_score}/10
            </p>
            <p className="text-xs text-muted-foreground">
              ADV: ${(liquidity.adv_dollars / 1_000_000).toFixed(1)}M | Spread: {liquidity.bid_ask_spread_pct.toFixed(2)}%
            </p>
          </CardContent>
        </Card>

        {/* Confidence */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Confidence</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn(
              'text-2xl font-bold',
              analysis.confidence.level >= 70 ? 'text-green-600' : analysis.confidence.level >= 60 ? 'text-yellow-600' : 'text-red-600'
            )}>
              {analysis.confidence.level}%
            </p>
            <p className="text-xs text-muted-foreground">
              {analysis.confidence.level >= 60 ? 'Above' : 'Below'} 60% threshold
            </p>
          </CardContent>
        </Card>

        {/* Biases Detected */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Biases Detected</CardTitle>
          </CardHeader>
          <CardContent className="space-y-0.5">
            <BiasItem name="Recency Bias" detected={biasCheck.recency_bias.detected} severity={biasCheck.recency_bias.severity} />
            <BiasItem name="Confirmation Bias" detected={biasCheck.confirmation_bias.detected} severity={biasCheck.confirmation_bias.severity} />
            <BiasItem name="Anchoring" detected={biasCheck.anchoring.detected} severity={biasCheck.anchoring.severity} />
            <BiasItem name="FOMO" detected={biasCheck.fomo.detected} severity={biasCheck.fomo.severity} />
            {!biasCheck.recency_bias.detected && !biasCheck.confirmation_bias.detected &&
             !biasCheck.anchoring.detected && !biasCheck.fomo.detected && (
              <p className="text-xs text-green-600">No biases detected</p>
            )}
          </CardContent>
        </Card>

        {/* Next Steps */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Next Steps</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Review Date: <span className="font-medium">{alerts.post_event_review}</span>
            </p>
            {alerts.price_alerts.slice(0, 2).map((alert, i) => (
              <p key={i} className="text-xs text-muted-foreground mt-0.5">
                • Set alert at ${alert.price.toFixed(2)}
              </p>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Row 5: Pattern Identified, Data Source, Historical Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Pattern Identified */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Pattern Identified</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium text-blue-600">
              {metaLearning?.pattern_identified || 'No specific pattern identified'}
            </p>
            {metaLearning?.similar_setup && (
              <p className="text-xs text-muted-foreground mt-1">
                {metaLearning.similar_setup.substring(0, 80)}...
              </p>
            )}
          </CardContent>
        </Card>

        {/* Data Source Effectiveness */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Data Source</CardTitle>
          </CardHeader>
          <CardContent>
            {newsCheck?.fresh_catalyst_exists ? (
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span className="text-xs text-green-600">Fresh catalyst exists</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-yellow-500" />
                <span className="text-xs text-yellow-600">No fresh catalyst</span>
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              {newsCheck?.items[0]?.news_item?.substring(0, 60)}...
            </p>
          </CardContent>
        </Card>

        {/* Sentiment Summary */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Sentiment Details</CardTitle>
          </CardHeader>
          <CardContent className="text-xs space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Analyst Ratings:</span>
              <span className="text-green-600">{sentiment.analyst.buy}B</span>
              <span className="text-yellow-600">{sentiment.analyst.hold}H</span>
              <span className="text-red-600">{sentiment.analyst.sell}S</span>
            </div>
            <div>
              <span className="text-muted-foreground">Short Interest: </span>
              <span>{sentiment.short_interest.pct_float}% of float</span>
            </div>
            <div>
              <span className="text-muted-foreground">P/C Ratio: </span>
              <span>{sentiment.options.put_call_ratio}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 6: Fundamentals, Alert Levels, Falsification */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Fundamentals */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm">Fundamentals</CardTitle>
          </CardHeader>
          <CardContent className="text-xs space-y-1">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Revenue Growth YoY</span>
              <span className={fundamentals.growth.revenue_growth_yoy > 0 ? 'text-green-600' : 'text-red-600'}>
                {formatPctWithSign(fundamentals.growth.revenue_growth_yoy)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">EPS Growth YoY</span>
              <span className={fundamentals.growth.earnings_growth_yoy > 0 ? 'text-green-600' : 'text-red-600'}>
                {formatPctWithSign(fundamentals.growth.earnings_growth_yoy)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Operating Margin</span>
              <span>{fundamentals.quality.operating_margin}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cash Position</span>
              <span>${fundamentals.quality.cash_position_b.toFixed(2)}B</span>
            </div>
          </CardContent>
        </Card>

        {/* Alert Levels */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm flex items-center gap-2">
              <Activity className="h-4 w-4" /> Alert Levels
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs space-y-1">
            {alerts.price_alerts.slice(0, 3).map((alert, i) => (
              <div key={i} className="flex items-center gap-2">
                {alert.direction === 'above' ? (
                  <TrendingUp className="h-3 w-3 text-green-500" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-red-500" />
                )}
                <span>${alert.price.toFixed(2)}</span>
                <span className="text-muted-foreground truncate">{alert.tag || alert.significance.substring(0, 20)}</span>
              </div>
            ))}
            {alerts.event_alerts.slice(0, 2).map((event, i) => (
              <div key={i} className="flex items-center gap-2 text-blue-600">
                <Clock className="h-3 w-3" />
                <span className="truncate">{event.event.substring(0, 30)}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Falsification */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm flex items-center gap-2">
              <XCircle className="h-4 w-4" /> Falsification
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Thesis invalid if:</p>
            <p className="text-xs text-red-600 mt-1 line-clamp-3">
              {falsification.thesis_invalid_if.substring(0, 120)}...
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Row 7: Rationale (Full Width) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Rationale</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground whitespace-pre-line">
            {analysis.rationale}
          </p>
          {analysis.pass_reasoning?.applicable && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-sm text-blue-600">
                <strong>Entry Trigger:</strong> {analysis.pass_reasoning.primary_reason}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="bg-slate-900 rounded-lg px-4 py-2 flex justify-between text-xs text-slate-400">
        <span>Source: {analysis._meta.id}.yaml</span>
        <span>Tradegent v{analysis._meta.version} | {analysis.analysis_date}</span>
      </div>
    </div>
  );
}
