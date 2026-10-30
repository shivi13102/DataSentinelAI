// ============================================================
// DataSentinel AI – API response types
// Derived from the actual FastAPI schema (api.py) and the
// verified analysis report. Do not add invented fields.
// ============================================================

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  configured_ai_model: string;
  analysis_engine: string;
  workflow_engine: string;
}

// ── Finding value shapes ────────────────────────────────────

export interface MissingValueDetail {
  missing_count: number;
  missing_percentage: number;
}

export interface DuplicateDetail {
  duplicate_count: number;
  duplicate_percentage: number;
}

export interface DistributionDetail {
  mean: number;
  std: number;
  min: number;
  max: number;
  sample_count: number;
}

export interface CategoricalDetail {
  counts: Record<string, number>;
  sample_count: number;
}

// A finding's baseline_value / current_value is one of the above.
// We use a loose union so TS doesn't force casts everywhere.
export type FindingValueDetail =
  | MissingValueDetail
  | DuplicateDetail
  | DistributionDetail
  | CategoricalDetail
  | Record<string, unknown>;

// ── Severity / type unions ──────────────────────────────────

export type Severity = 'low' | 'medium' | 'high' | 'critical';

export type FindingType =
  | 'missing_value_anomaly'
  | 'duplicate_anomaly'
  | 'distribution_drift'
  | 'categorical_drift'
  | 'schema_change';

// ── Finding ─────────────────────────────────────────────────

export interface Finding {
  type: FindingType;
  category: string;
  column: string | null;
  description: string;
  baseline_value: FindingValueDetail;
  current_value: FindingValueDetail;
  severity: Severity;
  detection_method: string;

  // missing_value_anomaly
  change_percentage_points?: number;

  // distribution_drift
  relative_mean_change?: number | null;
  ks_statistic?: number;
  ks_p_value?: number;
  alpha?: number;
  evidence?: string[];

  // categorical_drift
  total_variation_distance?: number;
  chi2_statistic?: number;
  p_value?: number;
  new_categories?: string[];
  removed_categories?: string[];

  // duplicate_anomaly
  compared_columns?: string[];
}

// ── Analysis ─────────────────────────────────────────────────

export interface SeverityCounts {
  high: number;
  medium: number;
  low: number;
}

export interface Analysis {
  analysis_timestamp: string;
  baseline_rows: number;
  current_rows: number;
  baseline_columns: number;
  current_columns: number;
  total_findings: number;
  overall_status: string;
  severity_counts: SeverityCounts;
  findings_by_type: Record<string, number>;
  findings: Finding[];
}

// ── AI Reasoning ─────────────────────────────────────────────

export interface RootCauseHypothesis {
  hypothesis: string;
  supporting_evidence: string;
  confidence: 'low' | 'medium' | 'high';
}

export interface AIExplanation {
  incident_summary: string;
  root_cause_hypotheses: RootCauseHypothesis[];
  business_impacts: string[];
  recommended_actions: string[];
  human_review_required: boolean;
}

export interface AIReasoning {
  status: 'success' | 'error' | 'skipped';
  model?: string;
  analysis_status?: string;
  explanation?: AIExplanation;
  error?: string;
}

// ── Protection Gate ───────────────────────────────────────────

export type ProtectionDecision = 'ALLOW' | 'REVIEW_REQUIRED' | 'BLOCK';

export interface FindingCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface Protection {
  decision: ProtectionDecision;
  downstream_processing_allowed: boolean;
  human_review_required: boolean;
  finding_counts: FindingCounts;
  reasons: string[];
}

// ── Dataset Metadata ──────────────────────────────────────────

export interface DatasetInfo {
  filename: string;
  rows: number;
  columns: number;
  size_bytes: number;
}

export interface DatasetMetadata {
  baseline: DatasetInfo;
  current: DatasetInfo;
}

// ── Full Analysis Report ──────────────────────────────────────

export interface AnalysisReport {
  report_id: string;
  workflow_status: string;
  overall_status: string;
  analysis: Analysis;
  ai_reasoning: AIReasoning;
  protection: Protection;
  human_review_required: boolean;
  error: string;
  dataset_metadata: DatasetMetadata;
  generated_at: string;
}

// ── Report List ───────────────────────────────────────────────

export interface ReportSummary {
  report_id: string;
  generated_at: string | null;
  overall_status: string;
  workflow_status: string;
  protection_decision: string;
  finding_count: number;
  baseline_filename: string | null;
  current_filename: string | null;
}

export interface ReportsResponse {
  reports: ReportSummary[];
  total: number;
}

