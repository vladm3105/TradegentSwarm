/**
 * Parser registry — dispatches to the correct version-specific parser.
 *
 * Registration keys: "<analysis-type>:<major.minor>"
 *   e.g. "stock-analysis:2.7", "earnings-analysis:2.5"
 *
 * Resolution order:
 *   1. Exact match on (type, major.minor)
 *   2. Console warning + nearest fallback for the same type
 *   3. stockParserV26 as last resort
 *
 * To add a new version: import the parser and add one REGISTRY.set() line.
 */

import type { AnalysisParser } from './types';
import type { AnalysisDetailResponse } from '@/lib/api';
import type { AnalysisDetail } from '@/types/analysis';

import { stockParserV26 }    from './stock/v2.6';
import { stockParserV27 }    from './stock/v2.7';
import { earningsParserV23 } from './earnings/v2.3';
import { earningsParserV25 } from './earnings/v2.5';
import { earningsParserV26 } from './earnings/v2.6';

type RegistryKey = string;

const REGISTRY = new Map<RegistryKey, AnalysisParser>([
  ['stock-analysis:2.6',    stockParserV26],
  ['stock-analysis:2.7',    stockParserV27],
  ['stock-analysis:2.8',    stockParserV27],
  ['earnings-analysis:2.3', earningsParserV23],
  ['earnings-analysis:2.5', earningsParserV25],
  ['earnings-analysis:2.6', earningsParserV26],
  ['earnings-analysis:2.8', earningsParserV26],
]);

// Fallback parsers by type if exact version is not registered
const TYPE_FALLBACKS: Record<string, AnalysisParser> = {
  'stock-analysis':    stockParserV27,
  'earnings-analysis': earningsParserV26,
};

function resolveType(yaml: Record<string, unknown>): string {
  const meta = yaml._meta as Record<string, unknown> | undefined;
  const raw  = String(yaml.analysis_type || meta?.type || '').toLowerCase();
  if (raw.includes('earnings')) return 'earnings-analysis';
  return 'stock-analysis';
}

function resolveMajorMinor(response: AnalysisDetailResponse): string {
  const yaml    = response.yaml_content as Record<string, unknown>;
  const meta    = yaml._meta as Record<string, unknown> | undefined;
  const version = String(response.schema_version || meta?.version || '2.6');
  return version.match(/^(\d+\.\d+)/)?.[1] ?? version;
}

/**
 * Parse an analysis API response using the registered version-specific parser.
 * Falls back gracefully when the exact version is not registered.
 */
export function parseAnalysis(response: AnalysisDetailResponse): AnalysisDetail {
  const yaml        = response.yaml_content as Record<string, unknown>;
  const type        = resolveType(yaml);
  const majorMinor  = resolveMajorMinor(response);
  const key: RegistryKey = `${type}:${majorMinor}`;

  const parser = REGISTRY.get(key);
  if (parser) return parser(response);

  // Unknown version — log warning and use type fallback
  console.warn(`[parsers] No parser registered for "${key}". Using fallback for type "${type}".`);
  const fallback = TYPE_FALLBACKS[type] ?? stockParserV26;
  return fallback(response);
}

/**
 * Check whether the analysis response has enough data for full visualization.
 * Uses the same version-aware resolver to find data wherever it lives in the YAML.
 */
export function hasFullAnalysisData(response: AnalysisDetailResponse): boolean {
  const yaml = response.yaml_content as Record<string, unknown>;
  const type = resolveType(yaml);

  // Promoted DB columns are the fastest check
  if (response.recommendation && response.gate_result) return true;

  // Version-aware fallback paths
  if (type === 'earnings-analysis') {
    const decision = yaml.decision as Record<string, unknown> | undefined;
    const p7       = yaml.phase7_decision as Record<string, unknown> | undefined;
    const gate     = yaml.do_nothing_gate as Record<string, unknown> | undefined;
    const p7gate   = p7?.do_nothing_gate  as Record<string, unknown> | undefined;

    const hasRec  = Boolean(decision?.recommendation || p7);
    const hasGate = Boolean(gate?.gate_result || p7gate?.gate_result);
    return hasRec && hasGate;
  }

  // Stock: recommendation and do_nothing_gate.gate_result at root
  const gate = yaml.do_nothing_gate as Record<string, unknown> | undefined;
  return Boolean(yaml.recommendation && gate?.gate_result);
}
