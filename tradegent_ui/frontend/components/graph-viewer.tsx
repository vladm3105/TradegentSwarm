'use client';

import { useCallback, useRef, useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import type { GraphNode, GraphData, GraphNodeType } from '@/types/graph';

// Dynamic import to avoid SSR issues with canvas
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  ),
});

// Node type color mapping - exported for use in filter badges
export const NODE_COLORS: Record<GraphNodeType, string> = {
  Ticker: '#3b82f6',    // Blue
  Company: '#6366f1',   // Indigo
  Sector: '#8b5cf6',    // Purple
  Industry: '#a855f7',  // Purple lighter
  Product: '#14b8a6',   // Teal
  Strategy: '#06b6d4',  // Cyan
  Pattern: '#22c55e',   // Green
  Bias: '#f97316',      // Orange
  Signal: '#eab308',    // Yellow
  Risk: '#ef4444',      // Red
  Executive: '#ec4899', // Pink
  Analyst: '#f472b6',   // Pink lighter
  Analysis: '#64748b',  // Slate
  Trade: '#0ea5e9',     // Sky
  Learning: '#10b981',  // Emerald
  Document: '#6b7280',  // Gray
  Catalyst: '#f59e0b',  // Amber
  EarningsEvent: '#84cc16', // Lime
  MacroEvent: '#06b6d4', // Cyan
  Structure: '#78716c', // Stone
};

const DEFAULT_COLOR = '#6b7280';

// Edge/relationship type color mapping - exported for tooltip use
export const EDGE_COLORS: Record<string, string> = {
  THREATENS: '#ef4444',       // Red
  AFFECTED_BY: '#f97316',     // Orange
  INDICATES: '#eab308',       // Yellow
  USES: '#3b82f6',            // Blue
  WORKS_FOR: '#8b5cf6',       // Purple
  OBSERVED_IN: '#06b6d4',     // Cyan
  HAS_EARNINGS: '#22c55e',    // Green
  EXTRACTED_FROM: '#64748b',  // Slate
  DETECTED_IN: '#6366f1',     // Indigo
  COMPETES_WITH: '#ec4899',   // Pink
  PEER_OF: '#14b8a6',         // Teal
  RELATED_TO: '#9ca3af',      // Gray
  HAS_SIGNAL: '#eab308',      // Yellow
  HAS_PATTERN: '#22c55e',     // Green
  HAS_BIAS: '#f97316',        // Orange
  HAS_RISK: '#ef4444',        // Red
  HAS_CATALYST: '#f59e0b',    // Amber
};

interface GraphViewerProps {
  data: GraphData;
  onNodeClick?: (node: GraphNode) => void;
  onNodeHover?: (node: GraphNode | null) => void;
  height?: number;
  width?: number;
  highlightedNodeId?: string | null;
}

// Helper to truncate labels
const truncateLabel = (label: string, maxLength: number = 12): string => {
  if (label.length <= maxLength) return label;
  return label.substring(0, maxLength - 1) + '…';
};

// Helper to get link node ID (handles both string and object)
const getLinkNodeId = (node: string | { id?: string } | any): string => {
  if (typeof node === 'string') return node;
  if (node && typeof node === 'object' && 'id' in node) return node.id;
  return String(node);
};

export function GraphViewer({
  data,
  onNodeClick,
  onNodeHover,
  height = 700,
  width,
  highlightedNodeId,
}: GraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<any | null>(null);

  // Compute connected nodes and links for highlighting
  const connectedNodes = useCallback((nodeId: string | null) => {
    if (!nodeId) return new Set<string>();
    const connected = new Set<string>([nodeId]);
    data.links.forEach((link) => {
      const sourceId = getLinkNodeId(link.source);
      const targetId = getLinkNodeId(link.target);
      if (sourceId === nodeId) connected.add(targetId);
      if (targetId === nodeId) connected.add(sourceId);
    });
    return connected;
  }, [data.links]);

  const connectedLinks = useCallback((nodeId: string | null) => {
    if (!nodeId) return new Set<string>();
    const links = new Set<string>();
    data.links.forEach((link) => {
      const sourceId = getLinkNodeId(link.source);
      const targetId = getLinkNodeId(link.target);
      if (sourceId === nodeId || targetId === nodeId) {
        links.add(`${sourceId}-${targetId}`);
      }
    });
    return links;
  }, [data.links]);

  const activeNodeId = hoveredNode || highlightedNodeId;
  const highlightNodes = connectedNodes(activeNodeId || null);
  const highlightLinks = connectedLinks(activeNodeId || null);

  // Handle container resize
  useEffect(() => {
    if (!containerRef.current) return;

    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: width || containerRef.current.clientWidth,
          height,
        });
      }
    };

    updateDimensions();
    const observer = new ResizeObserver(updateDimensions);
    observer.observe(containerRef.current);

    return () => observer.disconnect();
  }, [width, height]);

  // Node color based on type with highlight support
  const getNodeColor = useCallback((node: any) => {
    const baseColor = NODE_COLORS[node.type as GraphNodeType] || DEFAULT_COLOR;
    if (activeNodeId && !highlightNodes.has(node.id)) {
      return '#e5e7eb'; // Dimmed color for non-connected nodes
    }
    return baseColor;
  }, [activeNodeId, highlightNodes]);

  // Node size based on connections - kept small for readability
  const getNodeSize = useCallback((node: any) => {
    const links = data.links.filter((l) => {
      const sourceId = getLinkNodeId(l.source);
      const targetId = getLinkNodeId(l.target);
      return sourceId === node.id || targetId === node.id;
    });
    // Smaller sizes: Ticker 5-8, others 2-5
    const baseSize = node.type === 'Ticker' ? 5 : 2;
    const connectionBonus = Math.min(3, links.length * 0.3);
    return baseSize + connectionBonus;
  }, [data.links]);

  // Handle node click
  const handleNodeClick = useCallback(
    (node: any) => {
      if (onNodeClick) {
        onNodeClick(node as GraphNode);
      }
    },
    [onNodeClick]
  );

  // Handle node hover
  const handleNodeHover = useCallback(
    (node: any) => {
      setHoveredNode(node ? node.id : null);
      if (onNodeHover) {
        onNodeHover(node as GraphNode | null);
      }
    },
    [onNodeHover]
  );

  // Handle link hover
  const handleLinkHover = useCallback((link: any) => {
    setHoveredLink(link);
  }, []);

  // Get edge color based on relationship type with highlight support
  const getLinkColor = useCallback((link: any) => {
    const relType = link.type || 'RELATED_TO';
    const baseColor = EDGE_COLORS[relType] || '#9ca3af';
    const sourceId = getLinkNodeId(link.source);
    const targetId = getLinkNodeId(link.target);
    const linkKey = `${sourceId}-${targetId}`;

    if (activeNodeId && !highlightLinks.has(linkKey)) {
      return '#e5e7eb40'; // Very dimmed for non-connected edges
    }
    if (highlightLinks.has(linkKey)) {
      return baseColor; // Full color for connected edges
    }
    return baseColor + '80'; // Slightly transparent by default
  }, [activeNodeId, highlightLinks]);

  // Get link width based on highlight
  const getLinkWidth = useCallback((link: any) => {
    const sourceId = getLinkNodeId(link.source);
    const targetId = getLinkNodeId(link.target);
    const linkKey = `${sourceId}-${targetId}`;

    if (highlightLinks.has(linkKey)) {
      return 2.5; // Thicker for highlighted
    }
    return 1;
  }, [highlightLinks]);

  if (data.nodes.length === 0) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center h-full text-muted-foreground">
          No graph data available. Search for a ticker to visualize relationships.
        </CardContent>
      </Card>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full bg-background rounded-lg border relative">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        width={dimensions.width}
        height={dimensions.height}
        nodeColor={getNodeColor}
        nodeVal={getNodeSize}
        nodeLabel=""
        linkColor={getLinkColor}
        linkWidth={getLinkWidth}
        linkLabel=""
        linkDirectionalArrowLength={2}
        linkDirectionalArrowRelPos={1}
        linkCurvature={0.05}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        onLinkHover={handleLinkHover}
        cooldownTicks={100}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.4}
        d3AlphaMin={0.001}
        nodeCanvasObjectMode={() => 'after'}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const nodeSize = getNodeSize(node);
          const label = node.label || node.id;
          const isHighlighted = activeNodeId === node.id;
          const isConnected = highlightNodes.has(node.id);
          const isDimmed = activeNodeId && !isConnected;

          // Smaller font sizes for compact display
          const baseFontSize = isHighlighted ? 10 : (node.type === 'Ticker' ? 9 : 7);
          const fontSize = baseFontSize / globalScale;
          const displayLabel = truncateLabel(label, isHighlighted ? 18 : 12);

          // Only show labels when zoomed in enough or for important nodes
          const shouldShowLabel = globalScale > 0.8 || isHighlighted || node.type === 'Ticker';

          if (shouldShowLabel && (!isDimmed || globalScale > 1.5)) {
            ctx.font = `${isHighlighted ? 'bold ' : ''}${fontSize}px Inter, system-ui, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';

            // Draw text background for readability
            const textWidth = ctx.measureText(displayLabel).width;
            const padding = 1.5 / globalScale;
            const bgHeight = fontSize + padding * 2;

            // Background
            ctx.fillStyle = isDimmed ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.9)';
            ctx.fillRect(
              node.x - textWidth / 2 - padding,
              node.y + nodeSize + 1 / globalScale,
              textWidth + padding * 2,
              bgHeight
            );

            // Text
            ctx.fillStyle = isDimmed ? '#9ca3af' : '#1f2937';
            ctx.fillText(displayLabel, node.x, node.y + nodeSize + 1 / globalScale + padding);
          }

          // Draw highlight ring for hovered/selected node
          if (isHighlighted) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, nodeSize + 2, 0, 2 * Math.PI);
            ctx.strokeStyle = NODE_COLORS[node.type as GraphNodeType] || DEFAULT_COLOR;
            ctx.lineWidth = 1.5 / globalScale;
            ctx.stroke();
          }
        }}
        linkCanvasObjectMode={() => 'after'}
        linkCanvasObject={(link: any, ctx, globalScale) => {
          // Only show edge label when hovering on the link or connected node
          const sourceId = getLinkNodeId(link.source);
          const targetId = getLinkNodeId(link.target);
          const linkKey = `${sourceId}-${targetId}`;
          const isHighlighted = highlightLinks.has(linkKey);

          if ((hoveredLink === link || (isHighlighted && activeNodeId)) && link.source.x !== undefined) {
            const relType = link.type || 'RELATED_TO';
            const midX = (link.source.x + link.target.x) / 2;
            const midY = (link.source.y + link.target.y) / 2;

            const fontSize = 8 / globalScale;
            ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // Background
            const textWidth = ctx.measureText(relType).width;
            const padding = 2 / globalScale;
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            ctx.fillRect(
              midX - textWidth / 2 - padding,
              midY - fontSize / 2 - padding,
              textWidth + padding * 2,
              fontSize + padding * 2
            );

            // Border
            ctx.strokeStyle = EDGE_COLORS[relType] || '#9ca3af';
            ctx.lineWidth = 1 / globalScale;
            ctx.strokeRect(
              midX - textWidth / 2 - padding,
              midY - fontSize / 2 - padding,
              textWidth + padding * 2,
              fontSize + padding * 2
            );

            // Text
            ctx.fillStyle = '#374151';
            ctx.fillText(relType, midX, midY);
          }
        }}
      />

      {/* Hover tooltip */}
      {hoveredNode && (
        <div className="absolute top-2 left-2 bg-popover border rounded-lg shadow-lg p-3 text-sm max-w-xs z-10">
          {(() => {
            const node = data.nodes.find(n => n.id === hoveredNode);
            if (!node) return null;
            const connections = data.links.filter(l => {
              const sourceId = getLinkNodeId(l.source);
              const targetId = getLinkNodeId(l.target);
              return sourceId === node.id || targetId === node.id;
            }).length;
            return (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: NODE_COLORS[node.type as GraphNodeType] || DEFAULT_COLOR }}
                  />
                  <span className="font-semibold">{node.label}</span>
                </div>
                <div className="text-muted-foreground text-xs">
                  <span className="inline-block px-1.5 py-0.5 bg-muted rounded mr-2">{node.type}</span>
                  {connections} connection{connections !== 1 ? 's' : ''}
                </div>
                {node.properties && Object.keys(node.properties).length > 0 && (
                  <div className="mt-2 pt-2 border-t text-xs">
                    {Object.entries(node.properties).slice(0, 3).map(([key, value]) => (
                      <div key={key} className="truncate">
                        <span className="text-muted-foreground">{key}:</span> {String(value)}
                      </div>
                    ))}
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

// Compact legend component showing key node and edge types
export function GraphLegend({ compact = false }: { compact?: boolean }) {
  // Group node types by category for compact display
  const nodeGroups = {
    'Core': ['Ticker', 'Company', 'Sector'],
    'Analysis': ['Pattern', 'Signal', 'Bias', 'Risk'],
    'Events': ['Catalyst', 'EarningsEvent', 'MacroEvent'],
    'Other': ['Strategy', 'Executive', 'Document'],
  };

  const keyEdgeTypes = ['THREATENS', 'INDICATES', 'PEER_OF', 'HAS_PATTERN', 'HAS_RISK'];

  if (compact) {
    return (
      <div className="flex items-center gap-3 px-3 py-1.5 text-xs border-b bg-muted/20 overflow-x-auto">
        {Object.entries(nodeGroups).flatMap(([, types]) =>
          types.filter(t => NODE_COLORS[t as GraphNodeType]).slice(0, 2).map(type => (
            <div key={type} className="flex items-center gap-1 shrink-0">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: NODE_COLORS[type as GraphNodeType] }}
              />
              <span className="text-muted-foreground">{type}</span>
            </div>
          ))
        )}
        <span className="text-muted-foreground/50 mx-1">|</span>
        {keyEdgeTypes.slice(0, 3).map(type => (
          <div key={type} className="flex items-center gap-1 shrink-0">
            <div
              className="w-3 h-0.5 rounded"
              style={{ backgroundColor: EDGE_COLORS[type] }}
            />
            <span className="text-muted-foreground text-[10px]">{type}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 px-3 py-2 text-xs border-b bg-muted/20">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-muted-foreground font-medium">Nodes:</span>
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            <span className="text-muted-foreground">{type}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-muted-foreground font-medium">Edges:</span>
        {Object.entries(EDGE_COLORS).slice(0, 10).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1">
            <div
              className="w-3 h-0.5 rounded"
              style={{ backgroundColor: color }}
            />
            <span className="text-muted-foreground text-[10px]">{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
