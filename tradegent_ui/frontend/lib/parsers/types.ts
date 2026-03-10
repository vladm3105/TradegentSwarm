/**
 * AnalysisParser type — the contract every version parser must satisfy.
 */

import type { AnalysisDetail } from '@/types/analysis';
import type { AnalysisDetailResponse } from '@/lib/api';

/** Takes the raw API response and returns a fully-typed AnalysisDetail */
export type AnalysisParser = (response: AnalysisDetailResponse) => AnalysisDetail;
