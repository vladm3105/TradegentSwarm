// Graph node types matching Neo4j entity types
export type GraphNodeType =
  | 'Ticker'
  | 'Company'
  | 'Sector'
  | 'Industry'
  | 'Product'
  | 'Strategy'
  | 'Pattern'
  | 'Bias'
  | 'Signal'
  | 'Risk'
  | 'Executive'
  | 'Analyst'
  | 'Analysis'
  | 'Trade'
  | 'Learning'
  | 'Document'
  | 'Catalyst'
  | 'EarningsEvent'
  | 'MacroEvent'
  | 'Structure';

export interface GraphNode {
  id: string;
  label: string;
  type: GraphNodeType;
  properties?: Record<string, unknown>;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface GraphStats {
  node_count: number;
  edge_count: number;
  node_types: Record<string, number>;
  last_extraction: string | null;
}

export interface GraphContext {
  ticker: string;
  peers: Array<{ peer: string; company: string; sector: string }>;
  competitors: Array<{ competitor: string; ticker: string }>;
  risks: Array<{ name: string; description: string }>;
  patterns: Array<{ name: string; description: string }>;
  signals: Array<{ name: string; description: string }>;
  biases: Array<{ name: string; occurrences: number }>;
  strategies: Array<{ strategy: string; avg_win_rate: number }>;
}
