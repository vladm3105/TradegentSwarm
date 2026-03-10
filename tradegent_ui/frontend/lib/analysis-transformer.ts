/**
 * analysis-transformer.ts — delegation layer
 *
 * All parsing logic has moved to lib/parsers/.
 * This file re-exports the two public functions under their original names
 * so call-sites don't need to change.
 *
 * To support a new schema version, add a parser in lib/parsers/ and
 * register it in lib/parsers/registry.ts.
 */

export { parseAnalysis as transformToAnalysisDetail, hasFullAnalysisData } from './parsers/registry';

// Legacy named exports — kept so existing imports don't need to change
export type { AnalysisDetail } from '@/types/analysis';
export type { AnalysisDetailResponse } from './api';
