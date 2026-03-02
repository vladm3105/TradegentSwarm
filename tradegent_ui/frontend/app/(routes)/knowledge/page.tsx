'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  BookOpen,
  Search,
  Database,
  Network,
  FileText,
  Clock,
  RefreshCw,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { cn, formatDate } from '@/lib/utils';
import { getDashboardServiceHealth, listAnalyses, type AnalysisSummary } from '@/lib/api';
import { useChat } from '@/hooks/use-chat';
import { useUIStore } from '@/stores/ui-store';

interface KBStats {
  rag: { documents: number; chunks: number };
  graph: { nodes: number; edges: number };
}

export default function KnowledgePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('search');
  const [stats, setStats] = useState<KBStats | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { sendMessage } = useChat();
  const { setChatPanelOpen } = useUIStore();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, analysesRes] = await Promise.all([
        getDashboardServiceHealth(),
        listAnalyses({ limit: 10 }),
      ]);

      setStats({
        rag: {
          documents: healthRes.rag_stats.document_count,
          chunks: healthRes.rag_stats.chunk_count,
        },
        graph: {
          nodes: healthRes.graph_stats.node_count,
          edges: healthRes.graph_stats.edge_count,
        },
      });
      setAnalyses(analysesRes.analyses);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load knowledge base stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setChatPanelOpen(true);
      sendMessage(`search knowledge base for: ${searchQuery}`);
    }
  };

  const handleViewAnalysis = (ticker: string) => {
    window.location.href = `/analysis?ticker=${ticker}`;
  };

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Knowledge Base</h1>
          <p className="text-muted-foreground">
            Search and explore your trading knowledge
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
          Refresh
        </Button>
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

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-2">
              <Database className="h-5 w-5 text-primary" />
              <span className="text-sm text-muted-foreground">RAG Documents</span>
            </div>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <p className="text-2xl font-bold">{stats?.rag.documents || 0}</p>
                <p className="text-xs text-muted-foreground">
                  {(stats?.rag.chunks || 0).toLocaleString()} chunks
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-2">
              <Network className="h-5 w-5 text-primary" />
              <span className="text-sm text-muted-foreground">Graph Nodes</span>
            </div>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <p className="text-2xl font-bold">{stats?.graph.nodes || 0}</p>
                <p className="text-xs text-muted-foreground">
                  {(stats?.graph.edges || 0).toLocaleString()} edges
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-5 w-5 text-primary" />
              <span className="text-sm text-muted-foreground">Analyses</span>
            </div>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <p className="text-2xl font-bold">{analyses.length}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="h-5 w-5 text-primary" />
              <span className="text-sm text-muted-foreground">Knowledge Types</span>
            </div>
            <p className="text-2xl font-bold">5</p>
            <p className="text-xs text-muted-foreground">
              analyses, trades, watchlist, reviews, learnings
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Search className="h-5 w-5" />
            Search Knowledge Base
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search analyses, trades, learnings..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Button type="submit" disabled={!searchQuery.trim()}>
              Search
            </Button>
          </form>
          <p className="text-xs text-muted-foreground mt-2">
            Search uses RAG semantic search via chat. Try: "NVDA earnings history" or "risk management lessons"
          </p>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="search">Recent Analyses</TabsTrigger>
          <TabsTrigger value="tickers">By Ticker</TabsTrigger>
        </TabsList>

        <TabsContent value="search" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : analyses.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No analyses found</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {analyses.map((analysis) => (
                    <div
                      key={analysis.id}
                      className="flex items-start gap-4 p-4 rounded-lg border hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => handleViewAnalysis(analysis.ticker)}
                    >
                      <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                        <FileText className="h-5 w-5 text-primary" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold">{analysis.ticker}</h3>
                          <Badge variant="outline">{analysis.type}</Badge>
                          {analysis.recommendation && (
                            <Badge
                              variant="secondary"
                              className={cn(
                                analysis.recommendation === 'BUY' && 'bg-gain/20 text-gain',
                                analysis.recommendation === 'SELL' && 'bg-loss/20 text-loss',
                                analysis.recommendation === 'WATCH' && 'bg-yellow-500/20 text-yellow-600'
                              )}
                            >
                              {analysis.recommendation}
                            </Badge>
                          )}
                          {analysis.gate_result && (
                            <Badge
                              variant="outline"
                              className={cn(
                                analysis.gate_result === 'PASS' && 'text-gain',
                                analysis.gate_result === 'FAIL' && 'text-loss'
                              )}
                            >
                              {analysis.gate_result}
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDate(analysis.analysis_date)}
                          </span>
                          {analysis.confidence && (
                            <span>Confidence: {analysis.confidence}%</span>
                          )}
                          {analysis.expected_value && (
                            <span>EV: {analysis.expected_value.toFixed(1)}%</span>
                          )}
                        </div>
                      </div>
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tickers" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {/* Group analyses by ticker */}
                  {Object.entries(
                    analyses.reduce((acc, a) => {
                      if (!acc[a.ticker]) acc[a.ticker] = [];
                      acc[a.ticker].push(a);
                      return acc;
                    }, {} as Record<string, AnalysisSummary[]>)
                  ).map(([ticker, tickerAnalyses]) => (
                    <Card
                      key={ticker}
                      className="cursor-pointer hover:border-primary transition-colors"
                      onClick={() => handleViewAnalysis(ticker)}
                    >
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-bold text-lg">{ticker}</span>
                          <Badge variant="outline">{tickerAnalyses.length} analyses</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Latest: {formatDate(tickerAnalyses[0].analysis_date)}
                        </p>
                        {tickerAnalyses[0].recommendation && (
                          <Badge
                            className={cn(
                              'mt-2',
                              tickerAnalyses[0].recommendation === 'BUY' && 'bg-gain/20 text-gain',
                              tickerAnalyses[0].recommendation === 'SELL' && 'bg-loss/20 text-loss',
                              tickerAnalyses[0].recommendation === 'WATCH' && 'bg-yellow-500/20 text-yellow-600'
                            )}
                          >
                            {tickerAnalyses[0].recommendation}
                          </Badge>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
