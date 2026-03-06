'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Network,
  Search,
  RefreshCw,
  Loader2,
  AlertCircle,
  Clock,
  Box,
  GitBranch,
  Maximize2,
  Minimize2,
  GripVertical,
  GripHorizontal,
  Filter,
  Eye,
  EyeOff,
} from 'lucide-react';
import { cn, formatRelativeTime } from '@/lib/utils';
import { getGraphStats, getGraphSearch, getGraphContext } from '@/lib/api';
import { GraphViewer, GraphLegend, NODE_COLORS } from '@/components/graph-viewer';
import type { GraphStats, GraphData, GraphNode, GraphContext, GraphNodeType } from '@/types/graph';

export default function GraphPage() {
  const [searchTicker, setSearchTicker] = useState('');
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [originalGraphData, setOriginalGraphData] = useState<GraphData | null>(null); // Unmutated copy for filtering
  const [context, setContext] = useState<GraphContext | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [depth, setDepth] = useState(2);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [panelWidth, setPanelWidth] = useState(300);
  const [containerHeight, setContainerHeight] = useState(700);
  const [isDraggingH, setIsDraggingH] = useState(false);
  const [isDraggingV, setIsDraggingV] = useState(false);
  const [graphHeight, setGraphHeight] = useState(600);
  const [showFilters, setShowFilters] = useState(false);
  const [enabledNodeTypes, setEnabledNodeTypes] = useState<Set<string>>(new Set());
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Get unique node types from original graph data
  const availableNodeTypes = useMemo(() => {
    if (!originalGraphData) return [];
    const types = new Set(originalGraphData.nodes.map(n => n.type));
    return Array.from(types).sort();
  }, [originalGraphData]);

  // Initialize enabled types when graph data changes
  useEffect(() => {
    if (graphData && enabledNodeTypes.size === 0) {
      setEnabledNodeTypes(new Set(graphData.nodes.map(n => n.type)));
    }
  }, [graphData]);

  // Helper to get node ID from link source/target (handles both string and object)
  const getLinkNodeId = (node: string | { id?: string } | any): string => {
    if (typeof node === 'string') return node;
    if (node && typeof node === 'object' && 'id' in node) return node.id;
    return String(node);
  };

  // Color mapping for relationship types
  const getRelationshipColor = (relType: string): string => {
    const colorMap: Record<string, string> = {
      'THREATENS': 'bg-red-100 text-red-800 border-red-300 dark:bg-red-900/50 dark:text-red-200',
      'AFFECTED_BY': 'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/50 dark:text-orange-200',
      'INDICATES': 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/50 dark:text-yellow-200',
      'USES': 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/50 dark:text-blue-200',
      'WORKS_FOR': 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-900/50 dark:text-purple-200',
      'OBSERVED_IN': 'bg-cyan-100 text-cyan-800 border-cyan-300 dark:bg-cyan-900/50 dark:text-cyan-200',
      'HAS_EARNINGS': 'bg-green-100 text-green-800 border-green-300 dark:bg-green-900/50 dark:text-green-200',
      'EXTRACTED_FROM': 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-900/50 dark:text-slate-200',
      'DETECTED_IN': 'bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-900/50 dark:text-indigo-200',
      'COMPETES_WITH': 'bg-pink-100 text-pink-800 border-pink-300 dark:bg-pink-900/50 dark:text-pink-200',
      'PEER_OF': 'bg-teal-100 text-teal-800 border-teal-300 dark:bg-teal-900/50 dark:text-teal-200',
      'RELATED_TO': 'bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-900/50 dark:text-gray-200',
    };
    return colorMap[relType] || 'bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-900/50 dark:text-gray-200';
  };

  // Filter graph data based on enabled node types (use original unmutated data)
  const filteredGraphData = useMemo(() => {
    if (!originalGraphData) return null;
    if (enabledNodeTypes.size === 0) return null;

    const filteredNodes = originalGraphData.nodes.filter(n => enabledNodeTypes.has(n.type));
    const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredLinks = originalGraphData.links.filter(l => {
      const sourceId = getLinkNodeId(l.source);
      const targetId = getLinkNodeId(l.target);
      return filteredNodeIds.has(sourceId) && filteredNodeIds.has(targetId);
    });

    return { nodes: filteredNodes, links: filteredLinks };
  }, [originalGraphData, enabledNodeTypes]);

  // Toggle a node type
  const toggleNodeType = (type: string) => {
    setEnabledNodeTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  // Enable/disable all node types
  const toggleAllNodeTypes = (enable: boolean) => {
    if (enable) {
      setEnabledNodeTypes(new Set(availableNodeTypes));
    } else {
      setEnabledNodeTypes(new Set());
    }
  };

  // Fetch initial stats
  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const statsData = await getGraphStats();
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Update graph height based on container
  useEffect(() => {
    if (!graphContainerRef.current) return;

    const updateHeight = () => {
      if (graphContainerRef.current) {
        const rect = graphContainerRef.current.getBoundingClientRect();
        setGraphHeight(Math.max(400, rect.height - 20));
      }
    };

    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(graphContainerRef.current);

    return () => observer.disconnect();
  }, [isFullscreen]);

  // Handle horizontal resize drag (panel width)
  useEffect(() => {
    if (!isDraggingH) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = containerRect.right - e.clientX;
      setPanelWidth(Math.max(200, Math.min(500, newWidth)));
    };

    const handleMouseUp = () => {
      setIsDraggingH(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingH]);

  // Handle vertical resize drag (container height)
  useEffect(() => {
    if (!isDraggingV) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newHeight = e.clientY - containerRect.top;
      setContainerHeight(Math.max(400, Math.min(1200, newHeight)));
    };

    const handleMouseUp = () => {
      setIsDraggingV(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingV]);

  // Search for ticker
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTicker.trim()) return;

    setSearching(true);
    setError(null);
    setSelectedNode(null);
    setEnabledNodeTypes(new Set()); // Reset filters for new search

    try {
      const [searchData, contextData] = await Promise.all([
        getGraphSearch(searchTicker, depth),
        getGraphContext(searchTicker),
      ]);
      // Store original data (deep copy) for filtering - this won't be mutated
      setOriginalGraphData(JSON.parse(JSON.stringify(searchData)));
      setGraphData(searchData);
      setContext(contextData);
      setActiveTicker(searchTicker.toUpperCase());
      // Enable all types by default for new search
      setEnabledNodeTypes(new Set(searchData.nodes.map(n => n.type)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search graph');
      setGraphData(null);
      setContext(null);
    } finally {
      setSearching(false);
    }
  };

  // Handle node click
  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  // Toggle fullscreen mode
  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  return (
    <div className={cn(
      "flex-1 flex flex-col p-6 gap-4",
      isFullscreen && "fixed inset-0 z-50 bg-background"
    )}>
      {/* Header */}
      <div className={cn(
        "flex items-center justify-between",
        isFullscreen && "pb-2"
      )}>
        <div>
          <h1 className={cn(
            "font-bold tracking-tight",
            isFullscreen ? "text-xl" : "text-3xl"
          )}>Knowledge Graph</h1>
          {!isFullscreen && (
            <p className="text-muted-foreground">
              Explore ticker relationships, risks, and patterns
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchStats} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={toggleFullscreen}>
            {isFullscreen ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 py-4">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">{error}</span>
            <Button variant="outline" size="sm" onClick={fetchStats} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards - Hidden in fullscreen */}
      {!isFullscreen && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-2">
                <Box className="h-5 w-5 text-primary" />
                <span className="text-sm text-muted-foreground">Nodes</span>
              </div>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <p className="text-2xl font-bold tabular-nums">
                  {stats?.node_count.toLocaleString() || 0}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-2">
                <GitBranch className="h-5 w-5 text-primary" />
                <span className="text-sm text-muted-foreground">Edges</span>
              </div>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <p className="text-2xl font-bold tabular-nums">
                  {stats?.edge_count.toLocaleString() || 0}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-2">
                <Network className="h-5 w-5 text-primary" />
                <span className="text-sm text-muted-foreground">Entity Types</span>
              </div>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <p className="text-2xl font-bold tabular-nums">
                  {Object.keys(stats?.node_types || {}).length}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="h-5 w-5 text-primary" />
                <span className="text-sm text-muted-foreground">Last Extraction</span>
              </div>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <p className="text-sm font-medium">
                  {stats?.last_extraction
                    ? formatRelativeTime(new Date(stats.last_extraction))
                    : 'Never'}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Search */}
      <Card className={isFullscreen ? "py-2" : ""}>
        <CardContent className={cn("pt-4", isFullscreen && "py-2")}>
          <form onSubmit={handleSearch} className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Enter ticker symbol (e.g., NVDA)"
                value={searchTicker}
                onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
                className="pl-9"
                maxLength={10}
              />
            </div>
            <select
              value={depth}
              onChange={(e) => setDepth(parseInt(e.target.value))}
              className="px-3 py-2 border rounded-md bg-background text-sm"
            >
              <option value={1}>1 hop</option>
              <option value={2}>2 hops</option>
              <option value={3}>3 hops</option>
            </select>
            <Button type="submit" disabled={!searchTicker.trim() || searching}>
              {searching ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Search
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Main Content - Resizable */}
      <div className="flex flex-col">
        <div
          ref={containerRef}
          className={cn(
            "flex rounded-lg border overflow-hidden",
            (isDraggingH || isDraggingV) && "select-none"
          )}
          style={{ height: isFullscreen ? 'calc(100vh - 180px)' : containerHeight }}
        >
        {/* Graph Visualization Panel */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4" />
              <span className="font-medium">
                {activeTicker ? `Graph: ${activeTicker}` : 'Graph Visualization'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {originalGraphData && filteredGraphData && (
                <Badge variant="outline">
                  {filteredGraphData.nodes.length}/{originalGraphData.nodes.length} nodes, {filteredGraphData.links.length}/{originalGraphData.links.length} edges
                </Badge>
              )}
              {originalGraphData && (
                <Button
                  variant={showFilters ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => setShowFilters(!showFilters)}
                  className="h-7 px-2"
                >
                  <Filter className="h-3 w-3 mr-1" />
                  Filter
                </Button>
              )}
            </div>
          </div>
          {/* Filter Panel */}
          {showFilters && originalGraphData && (
            <div className="px-4 py-2 border-b bg-muted/20">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-muted-foreground">Node Type Filters</span>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleAllNodeTypes(true)}
                    className="h-6 px-2 text-xs"
                  >
                    <Eye className="h-3 w-3 mr-1" />
                    All
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleAllNodeTypes(false)}
                    className="h-6 px-2 text-xs"
                  >
                    <EyeOff className="h-3 w-3 mr-1" />
                    None
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {availableNodeTypes.map(type => {
                  const isEnabled = enabledNodeTypes.has(type);
                  const count = originalGraphData.nodes.filter(n => n.type === type).length;
                  const nodeColor = NODE_COLORS[type as GraphNodeType] || '#6b7280';
                  return (
                    <button
                      key={type}
                      onClick={() => toggleNodeType(type)}
                      className={cn(
                        "inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all",
                        isEnabled
                          ? "border shadow-sm"
                          : "bg-muted/50 text-muted-foreground border border-transparent opacity-40 grayscale"
                      )}
                      style={isEnabled ? {
                        backgroundColor: `${nodeColor}15`,
                        borderColor: `${nodeColor}50`,
                        color: nodeColor,
                      } : undefined}
                    >
                      <div
                        className={cn(
                          "w-2.5 h-2.5 rounded-full transition-opacity",
                          !isEnabled && "opacity-30"
                        )}
                        style={{ backgroundColor: nodeColor }}
                      />
                      {type} ({count})
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {!showFilters && <GraphLegend compact />}
          <div ref={graphContainerRef} className="flex-1 min-h-0 bg-background">
            {searching ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : filteredGraphData && filteredGraphData.nodes.length > 0 ? (
              <GraphViewer
                data={filteredGraphData}
                onNodeClick={handleNodeClick}
                onNodeHover={setHoveredNode}
                height={graphHeight}
                highlightedNodeId={selectedNode?.id}
              />
            ) : originalGraphData ? (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                <div className="text-center">
                  <EyeOff className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>All node types are hidden</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleAllNodeTypes(true)}
                    className="mt-2"
                  >
                    Show All
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                <div className="text-center">
                  <Network className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Search for a ticker to visualize its graph</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Horizontal Resize Handle */}
        <div
          className={cn(
            "w-1 bg-border hover:bg-primary/50 cursor-col-resize flex items-center justify-center transition-colors",
            isDraggingH && "bg-primary/50"
          )}
          onMouseDown={() => setIsDraggingH(true)}
        >
          <div className="h-8 w-4 flex items-center justify-center">
            <GripVertical className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>

        {/* Details Panel */}
        <div
          className="h-full overflow-auto bg-muted/10 border-l"
          style={{ width: panelWidth }}
        >
          <div className="p-4 space-y-4">
            {/* Selected Node */}
            <div>
              <h3 className="font-medium mb-2 flex items-center gap-2">
                <Box className="h-4 w-4" />
                Selected Node
              </h3>
              {selectedNode ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge>{selectedNode.type}</Badge>
                    <span className="font-semibold text-sm">{selectedNode.label}</span>
                  </div>
                  {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Properties</p>
                      <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-32">
                        {JSON.stringify(selectedNode.properties, null, 2)}
                      </pre>
                    </div>
                  )}
                  {/* Connected Edges */}
                  {originalGraphData && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">
                        Connections ({originalGraphData.links.filter(l =>
                          getLinkNodeId(l.source) === selectedNode.id ||
                          getLinkNodeId(l.target) === selectedNode.id
                        ).length})
                      </p>
                      <div className="space-y-1 max-h-48 overflow-auto">
                        {originalGraphData.links
                          .filter(l => {
                            const sourceId = getLinkNodeId(l.source);
                            const targetId = getLinkNodeId(l.target);
                            return sourceId === selectedNode.id || targetId === selectedNode.id;
                          })
                          .map((link, idx) => {
                            const sourceId = getLinkNodeId(link.source);
                            const targetId = getLinkNodeId(link.target);
                            const isOutgoing = sourceId === selectedNode.id;
                            const otherNodeId = isOutgoing ? targetId : sourceId;
                            const otherNode = originalGraphData.nodes.find(n => n.id === otherNodeId);

                            return (
                              <div
                                key={idx}
                                className="flex items-center gap-1 text-xs p-1.5 bg-muted/50 rounded cursor-pointer hover:bg-muted"
                                onClick={() => otherNode && handleNodeClick(otherNode)}
                              >
                                <span className={cn(
                                  "shrink-0",
                                  isOutgoing ? "text-blue-500" : "text-green-500"
                                )}>
                                  {isOutgoing ? "→" : "←"}
                                </span>
                                <Badge variant="outline" className={cn("text-[10px] px-1 py-0 shrink-0 border", getRelationshipColor(link.type))}>
                                  {link.type}
                                </Badge>
                                <span className="truncate">
                                  {otherNode?.label || otherNodeId}
                                </span>
                                <Badge variant="secondary" className="text-[10px] px-1 py-0 ml-auto shrink-0">
                                  {otherNode?.type}
                                </Badge>
                              </div>
                            );
                          })}
                        {originalGraphData.links.filter(l => {
                          const sourceId = getLinkNodeId(l.source);
                          const targetId = getLinkNodeId(l.target);
                          return sourceId === selectedNode.id || targetId === selectedNode.id;
                        }).length === 0 && (
                          <p className="text-xs text-muted-foreground italic">No connections</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Click a node in the graph to see details
                </p>
              )}
            </div>

            {/* Context Summary */}
            {context && (
              <div className="border-t pt-4">
                <h3 className="font-medium mb-2">Context: {context.ticker}</h3>
                <div className="space-y-3">
                  {context.peers.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Peers</p>
                      <div className="flex flex-wrap gap-1">
                        {context.peers.slice(0, 5).map((p) => (
                          <Badge key={p.peer} variant="secondary" className="text-xs">
                            {p.peer}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {context.risks.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Risks</p>
                      <div className="flex flex-wrap gap-1">
                        {context.risks.slice(0, 5).map((r) => (
                          <Badge key={r.name} variant="destructive" className="text-xs">
                            {r.name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {context.patterns.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Patterns</p>
                      <div className="flex flex-wrap gap-1">
                        {context.patterns.slice(0, 5).map((p) => (
                          <Badge key={p.name} variant="outline" className="text-xs">
                            {p.name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {context.signals.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Signals</p>
                      <div className="flex flex-wrap gap-1">
                        {context.signals.slice(0, 5).map((s) => (
                          <Badge key={s.name} variant="secondary" className="text-xs bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                            {s.name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {context.biases.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Biases</p>
                      <div className="flex flex-wrap gap-1">
                        {context.biases.slice(0, 5).map((b) => (
                          <Badge key={b.name} variant="secondary" className="text-xs bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
                            {b.name} ({b.occurrences})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {context.strategies.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Strategies</p>
                      <div className="flex flex-wrap gap-1">
                        {context.strategies.map((s) => (
                          <Badge key={s.strategy} variant="secondary" className="text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                            {s.strategy} ({(s.avg_win_rate * 100).toFixed(0)}%)
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Stats in fullscreen mode */}
            {isFullscreen && stats && (
              <div className="border-t pt-4">
                <h3 className="font-medium mb-2">Graph Stats</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Nodes:</span>{' '}
                    <span className="font-medium">{stats.node_count.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Edges:</span>{' '}
                    <span className="font-medium">{stats.edge_count.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Types:</span>{' '}
                    <span className="font-medium">{Object.keys(stats.node_types).length}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        </div>

        {/* Vertical Resize Handle (Bottom) */}
        {!isFullscreen && (
          <div
            className={cn(
              "h-2 bg-border hover:bg-primary/50 cursor-row-resize flex items-center justify-center transition-colors rounded-b-lg",
              isDraggingV && "bg-primary/50"
            )}
            onMouseDown={() => setIsDraggingV(true)}
          >
            <div className="w-8 h-4 flex items-center justify-center">
              <GripHorizontal className="h-4 w-4 text-muted-foreground" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
