'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { BarChart3, Search, RefreshCw, Eye, Loader2, AlertCircle, X } from 'lucide-react';
import { cn, formatDate, getRecommendationClass, getGateClass, getStatusClass } from '@/lib/utils';
import { listAnalyses, getAnalysisDetail, type AnalysisSummary, type AnalysisDetailResponse } from '@/lib/api';
import { transformToAnalysisDetail, hasFullAnalysisData } from '@/lib/analysis-transformer';
import { AnalysisDetailView } from '@/components/analysis-detail-view';
import { useChat } from '@/hooks/use-chat';
import { useUIStore } from '@/stores/ui-store';
import type { AnalysisDetail } from '@/types/analysis';

interface AnalysisRowProps {
  analysis: AnalysisSummary;
  onView: (analysis: AnalysisSummary) => void;
  isLoading?: boolean;
}

function AnalysisRow({ analysis, onView, isLoading }: AnalysisRowProps) {
  const recommendationLabel =
    typeof analysis.recommendation === 'string'
      ? analysis.recommendation.replace(/_/g, ' ')
      : null;

  return (
    <tr className="border-b hover:bg-muted/50 transition-colors">
      <td className="p-4">
        <div className="flex items-center gap-2">
          <span className="font-bold">{analysis.ticker}</span>
          <Badge variant="outline" className="text-xs">
            {analysis.type}
          </Badge>
        </div>
      </td>
      <td className="p-4">
        <Badge variant="outline" className={cn('text-xs capitalize', getStatusClass(analysis.status))}>
          {analysis.status}
        </Badge>
      </td>
      <td className="p-4">
        {recommendationLabel ? (
          <Badge className={getRecommendationClass(recommendationLabel)}>
            {recommendationLabel}
          </Badge>
        ) : (
          <span className="text-muted-foreground text-sm">-</span>
        )}
      </td>
      <td className="p-4 tabular-nums">
        {analysis.confidence !== null ? `${analysis.confidence}%` : '-'}
      </td>
      <td className="p-4">
        {analysis.gate_result ? (
          <Badge variant="outline" className={getGateClass(analysis.gate_result)}>
            {analysis.gate_result}
          </Badge>
        ) : (
          <span className="text-muted-foreground text-sm">-</span>
        )}
      </td>
      <td
        className={cn(
          'p-4 tabular-nums',
          analysis.expected_value !== null
            ? analysis.expected_value > 0 ? 'text-gain' : 'text-loss'
            : ''
        )}
      >
        {analysis.expected_value !== null
          ? `${analysis.expected_value > 0 ? '+' : ''}${analysis.expected_value.toFixed(1)}%`
          : '-'
        }
      </td>
      <td className="p-4 text-muted-foreground text-sm whitespace-nowrap">
        {formatDate(analysis.analysis_date, { includeTime: true })}
      </td>
      <td className="p-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onView(analysis)}
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Eye className="h-4 w-4 mr-1" />
              View
            </>
          )}
        </Button>
      </td>
    </tr>
  );
}

interface AnalysisDetailDialogProps {
  analysisDetail: AnalysisDetail | null;
  apiResponse: AnalysisDetailResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isLoading?: boolean;
  error?: string | null;
}

function AnalysisDetailDialog({
  analysisDetail,
  apiResponse,
  open,
  onOpenChange,
  isLoading,
  error,
}: AnalysisDetailDialogProps) {
  const recommendationLabel =
    typeof apiResponse?.recommendation === 'string'
      ? apiResponse.recommendation.replace(/_/g, ' ')
      : null;

  // Loading state
  if (isLoading) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-md">
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Loading analysis...</p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // Error state
  if (error) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-md">
          <div className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-8 w-8 text-destructive mb-4" />
            <p className="text-destructive font-medium">Error loading analysis</p>
            <p className="text-muted-foreground text-sm mt-2">{error}</p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // No data
  if (!apiResponse) {
    return null;
  }

  // Full analysis view if we have complete data
  if (analysisDetail && hasFullAnalysisData(apiResponse)) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto p-0">
          <AnalysisDetailView analysis={analysisDetail} />
        </DialogContent>
      </Dialog>
    );
  }

  // Fallback: Basic view for incomplete analyses
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span className="text-2xl font-bold">{apiResponse.ticker}</span>
            <Badge variant="outline" className="text-xs">
              v{apiResponse.schema_version}
            </Badge>
            {recommendationLabel && (
              <Badge className={getRecommendationClass(recommendationLabel)}>
                {recommendationLabel}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Confidence</p>
              <p className="text-2xl font-bold">
                {apiResponse.confidence !== null ? `${apiResponse.confidence}%` : 'N/A'}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Expected Value</p>
              <p className={cn(
                'text-2xl font-bold',
                apiResponse.expected_value !== null
                  ? apiResponse.expected_value > 0 ? 'text-gain' : 'text-loss'
                  : ''
              )}>
                {apiResponse.expected_value !== null
                  ? `${apiResponse.expected_value > 0 ? '+' : ''}${apiResponse.expected_value.toFixed(1)}%`
                  : 'N/A'
                }
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Gate Result</p>
              {apiResponse.gate_result ? (
                <Badge variant="outline" className={cn('text-lg', getGateClass(apiResponse.gate_result))}>
                  {apiResponse.gate_result}
                </Badge>
              ) : (
                <p className="text-lg text-muted-foreground">N/A</p>
              )}
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Current Price</p>
              <p className="text-2xl font-bold">
                {apiResponse.current_price !== null ? `$${apiResponse.current_price.toFixed(2)}` : 'N/A'}
              </p>
            </div>
          </div>

          <div className="text-center text-muted-foreground py-8 border rounded-lg bg-muted/20">
            <AlertCircle className="h-8 w-8 mx-auto mb-2 text-yellow-500" />
            <p className="text-sm">This analysis has incomplete data.</p>
            <p className="text-xs mt-1">Run a complete analysis to see the full dashboard view.</p>
          </div>

          {/* Analysis Date and File */}
          <div className="text-sm text-muted-foreground border-t pt-4">
            <p>Analysis Date: {formatDate(apiResponse.analysis_date)}</p>
            <p className="text-xs mt-1 truncate">Source: {apiResponse.file_path}</p>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-4 border-t">
            <Button variant="outline" className="flex-1">
              Add to Watchlist
            </Button>
            <Button className="flex-1">
              <RefreshCw className="h-4 w-4 mr-2" />
              Run Updated Analysis
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function AnalysisPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlTicker = searchParams.get('ticker')?.toUpperCase() || '';

  const [ticker, setTicker] = useState(urlTicker);
  const [filter, setFilter] = useState<'all' | 'completed' | 'expired' | 'declined' | 'error'>('all');
  const [searchTicker, setSearchTicker] = useState(urlTicker);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  // Chat integration for triggering analysis
  const { sendMessage } = useChat();
  const { setChatPanelOpen } = useUIStore();

  const [selectedAnalysisId, setSelectedAnalysisId] = useState<number | null>(null);
  const [selectedAnalysisDetail, setSelectedAnalysisDetail] = useState<AnalysisDetail | null>(null);
  const [selectedApiResponse, setSelectedApiResponse] = useState<AnalysisDetailResponse | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Sync from URL only when navigating with a ticker parameter
  useEffect(() => {
    if (urlTicker) {
      setTicker(urlTicker);
      setSearchTicker(urlTicker);
    }
  }, [urlTicker]);

  // Fetch analyses list
  const fetchAnalyses = useCallback(async () => {
    setIsLoadingList(true);
    setListError(null);
    try {
      const response = await listAnalyses({
        status: filter,
        limit: 50,
      });
      setAnalyses(response.analyses);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to fetch analyses:', err);
      setListError(err instanceof Error ? err.message : 'Failed to load analyses');
      setAnalyses([]);
    } finally {
      setIsLoadingList(false);
    }
  }, [filter]);

  // Initial load and filter changes
  useEffect(() => {
    fetchAnalyses();
  }, [fetchAnalyses]);

  // Filter analyses by search term
  const filteredAnalyses = useMemo(() => {
    if (!searchTicker.trim()) return analyses;
    const search = searchTicker.trim().toUpperCase();
    return analyses.filter((a) => a.ticker.includes(search));
  }, [analyses, searchTicker]);

  const handleRunAnalysis = () => {
    if (ticker.trim()) {
      // Open chat panel and trigger analysis
      setChatPanelOpen(true);
      sendMessage(`stock analysis ${ticker.trim()}`);
    }
  };

  const handleResetSearch = () => {
    setTicker('');
    setSearchTicker('');
    // Clear URL parameter
    router.push('/analysis');
  };

  const handleViewAnalysis = async (analysis: AnalysisSummary) => {
    setSelectedAnalysisId(analysis.id);
    setSelectedAnalysisDetail(null);
    setSelectedApiResponse(null);
    setDetailError(null);
    setDialogOpen(true);
    setIsLoadingDetail(true);

    try {
      const response = await getAnalysisDetail(analysis.id);
      setSelectedApiResponse(response);

      // Transform to AnalysisDetail if we have full data
      if (hasFullAnalysisData(response)) {
        const detail = transformToAnalysisDetail(response);
        setSelectedAnalysisDetail(detail);
      }
    } catch (err) {
      console.error('Failed to fetch analysis detail:', err);
      setDetailError(err instanceof Error ? err.message : 'Failed to load analysis');
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleDialogClose = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      setSelectedAnalysisId(null);
      setSelectedAnalysisDetail(null);
      setSelectedApiResponse(null);
      setDetailError(null);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Analysis</h1>
          <p className="text-muted-foreground">
            Run and manage stock analyses
          </p>
        </div>
      </div>

      {/* Quick Analysis */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Run Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Enter ticker symbol (e.g., NVDA)"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && ticker.trim()) {
                    e.preventDefault();
                    handleRunAnalysis();
                  }
                }}
                className="pl-9"
              />
            </div>
            <Button
              type="button"
              disabled={!ticker.trim()}
              onClick={() => handleRunAnalysis()}
            >
              <BarChart3 className="h-4 w-4 mr-2" />
              Analyze
            </Button>
          </div>
          <div className="flex gap-2 mt-4">
            <span className="text-sm text-muted-foreground">Quick:</span>
            {['NVDA', 'AAPL', 'MSFT', 'TSLA', 'AMZN'].map((t) => (
              <Button
                key={t}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setTicker(t)}
              >
                {t}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Analyses List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">
              Recent Analyses
              {total > 0 && (
                <span className="text-sm font-normal text-muted-foreground ml-2">
                  ({filteredAnalyses.length !== total ? `${filteredAnalyses.length} of ${total}` : `${total} total`})
                </span>
              )}
            </CardTitle>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search ticker..."
                  value={searchTicker}
                  onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
                  className="pl-8 pr-8 w-36 h-8 text-sm"
                />
                {searchTicker && (
                  <button
                    type="button"
                    onClick={() => setSearchTicker('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
              {(searchTicker || urlTicker) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleResetSearch}
                  className="h-8 px-2 text-xs"
                >
                  Reset
                </Button>
              )}
              <Tabs value={filter} onValueChange={(v) => setFilter(v as typeof filter)}>
                <TabsList>
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="completed">Completed</TabsTrigger>
                  <TabsTrigger value="expired">Expired</TabsTrigger>
                  <TabsTrigger value="declined">Declined</TabsTrigger>
                  <TabsTrigger value="error">Error</TabsTrigger>
                </TabsList>
              </Tabs>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchAnalyses}
                disabled={isLoadingList}
              >
                {isLoadingList ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {listError ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <AlertCircle className="h-8 w-8 text-destructive mb-4" />
              <p className="text-destructive font-medium">Error loading analyses</p>
              <p className="text-muted-foreground text-sm mt-2">{listError}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchAnalyses}
                className="mt-4"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
            </div>
          ) : isLoadingList ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : analyses.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <p>No analyses found.</p>
              <p className="text-sm mt-1">Run an analysis to get started.</p>
            </div>
          ) : filteredAnalyses.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <p>No analyses match "{searchTicker}"</p>
              <Button
                variant="link"
                size="sm"
                onClick={() => setSearchTicker('')}
                className="mt-2"
              >
                Clear search
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-4 font-medium text-muted-foreground">Ticker</th>
                    <th className="p-4 font-medium text-muted-foreground">Status</th>
                    <th className="p-4 font-medium text-muted-foreground">Recommendation</th>
                    <th className="p-4 font-medium text-muted-foreground">Confidence</th>
                    <th className="p-4 font-medium text-muted-foreground">Open-Trade Gate</th>
                    <th className="p-4 font-medium text-muted-foreground">EV</th>
                    <th className="p-4 font-medium text-muted-foreground">Date</th>
                    <th className="p-4 font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAnalyses.map((analysis) => (
                    <AnalysisRow
                      key={analysis.id}
                      analysis={analysis}
                      onView={handleViewAnalysis}
                      isLoading={selectedAnalysisId === analysis.id && isLoadingDetail}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Analysis Detail Dialog */}
      <AnalysisDetailDialog
        analysisDetail={selectedAnalysisDetail}
        apiResponse={selectedApiResponse}
        open={dialogOpen}
        onOpenChange={handleDialogClose}
        isLoading={isLoadingDetail}
        error={detailError}
      />
    </div>
  );
}
