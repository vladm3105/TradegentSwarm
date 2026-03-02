'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Target, Play, Clock, TrendingUp, AlertCircle, RefreshCw, Loader2, CheckCircle, XCircle } from 'lucide-react';
import { cn, formatDate } from '@/lib/utils';
import { listScanners, getScannerResults, type ScannerConfig, type ScannerResult, type ScannerCandidate } from '@/lib/api';
import { useChat } from '@/hooks/use-chat';
import { useUIStore } from '@/stores/ui-store';

export default function ScannerPage() {
  const [selectedScanner, setSelectedScanner] = useState<string | null>(null);
  const [scanners, setScanners] = useState<ScannerConfig[]>([]);
  const [results, setResults] = useState<ScannerResult[]>([]);
  const [latestCandidates, setLatestCandidates] = useState<ScannerCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { sendMessage } = useChat();
  const { setChatPanelOpen } = useUIStore();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [scannersRes, resultsRes] = await Promise.all([
        listScanners({ enabled_only: false }),
        getScannerResults({ limit: 20 }),
      ]);
      setScanners(scannersRes.scanners);
      setResults(resultsRes.results);

      // Extract all candidates from recent results
      const allCandidates: ScannerCandidate[] = [];
      const seenTickers = new Set<string>();
      for (const result of resultsRes.results) {
        for (const candidate of result.candidates) {
          if (!seenTickers.has(candidate.ticker)) {
            seenTickers.add(candidate.ticker);
            allCandidates.push(candidate);
          }
        }
      }
      setLatestCandidates(allCandidates.slice(0, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load scanner data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRunScanners = () => {
    setChatPanelOpen(true);
    sendMessage('run scanners');
  };

  const handleRunScanner = (scannerCode: string) => {
    setChatPanelOpen(true);
    sendMessage(`run scanner ${scannerCode}`);
  };

  const handleAnalyze = (ticker: string) => {
    setChatPanelOpen(true);
    sendMessage(`stock analysis ${ticker}`);
  };

  const handleWatch = (ticker: string) => {
    setChatPanelOpen(true);
    sendMessage(`add ${ticker} to watchlist`);
  };

  const filteredResults = selectedScanner
    ? results.filter(r => r.scanner_code === selectedScanner)
    : results;

  const filteredCandidates = selectedScanner
    ? filteredResults.flatMap(r => r.candidates)
    : latestCandidates;

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Scanner</h1>
          <p className="text-muted-foreground">
            Find trading opportunities systematically
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button onClick={handleRunScanners}>
            <Play className="h-4 w-4 mr-2" />
            Run All Scanners
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 py-4">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">{error}</span>
            <Button variant="outline" size="sm" onClick={fetchData} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Scanner Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : scanners.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            <Target className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No scanners configured</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {scanners.map((scanner) => (
            <Card
              key={scanner.id}
              className={cn(
                'cursor-pointer transition-colors hover:border-primary',
                selectedScanner === scanner.scanner_code && 'border-primary'
              )}
              onClick={() => setSelectedScanner(
                selectedScanner === scanner.scanner_code ? null : scanner.scanner_code
              )}
            >
              <CardContent className="pt-6">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Target className="h-5 w-5 text-primary" />
                    {scanner.is_enabled ? (
                      <CheckCircle className="h-3 w-3 text-gain" />
                    ) : (
                      <XCircle className="h-3 w-3 text-muted-foreground" />
                    )}
                  </div>
                  <Badge variant="outline">{scanner.scanner_type}</Badge>
                </div>
                <h3 className="font-semibold truncate" title={scanner.name}>{scanner.name}</h3>
                {scanner.description && (
                  <p className="text-xs text-muted-foreground truncate mt-1">{scanner.description}</p>
                )}
                <div className="flex items-center gap-1 text-sm text-muted-foreground mt-2">
                  <Clock className="h-3 w-3" />
                  <span>
                    {scanner.last_run
                      ? formatDate(scanner.last_run, { includeTime: true })
                      : 'Never run'}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-3">
                  <span className="text-sm">
                    {scanner.last_run_status === 'completed' ? (
                      <>
                        <span className="font-semibold text-primary">{scanner.candidates_count || 0}</span>{' '}
                        results
                      </>
                    ) : scanner.last_run_status === 'failed' ? (
                      <span className="text-loss">Failed</span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRunScanner(scanner.scanner_code);
                    }}
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Results */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              {selectedScanner ? `Results: ${selectedScanner}` : 'Top Opportunities'}
            </CardTitle>
            <Badge variant="outline">{filteredCandidates.length} candidates</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filteredCandidates.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Target className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No candidates found</p>
              <p className="text-sm mt-2">Run scanners to find opportunities</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredCandidates.map((candidate, idx) => (
                <div
                  key={`${candidate.ticker}-${idx}`}
                  className="flex items-center justify-between p-4 rounded-lg border hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={cn(
                        'h-12 w-12 rounded-full flex items-center justify-center text-lg font-bold',
                        (candidate.score || 0) >= 7.5
                          ? 'bg-gain/10 text-gain'
                          : (candidate.score || 0) >= 6.5
                          ? 'bg-yellow-500/10 text-yellow-500'
                          : 'bg-muted'
                      )}
                    >
                      {candidate.score?.toFixed(1) || '-'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-lg">{candidate.ticker}</span>
                        {candidate.price && (
                          <Badge variant="outline" className="text-xs">
                            ${candidate.price.toFixed(2)}
                          </Badge>
                        )}
                      </div>
                      {candidate.notes && (
                        <p className="text-sm text-muted-foreground truncate max-w-[400px]">
                          {candidate.notes}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleAnalyze(candidate.ticker)}
                    >
                      Analyze
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleWatch(candidate.ticker)}
                    >
                      Watch
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info */}
      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-5 w-5 text-primary mt-0.5" />
            <div>
              <h3 className="font-semibold">Scanner Scoring</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Candidates are scored from 0-10 based on weighted criteria.
                Scores &ge;7.5 trigger full analysis, 6.5-7.4 go to watchlist,
                below 6.5 are skipped.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
