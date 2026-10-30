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
  ai_provider: string;
  analysis_engine: string;
  analysis_engine_status: 'available' | 'unavailable';
  analysis_engine_error: string | null;
  workflow_engine: string;
}

export type AIHealthStatus =
  | 'AVAILABLE'
  | 'MODEL_NOT_INSTALLED'
  | 'OLLAMA_UNAVAILABLE'
  | 'INFERENCE_FAILED'
  | 'NOT_CONFIGURED';

export interface AIHealthResponse {
  provider: string;
  model: string | null;
  status: AIHealthStatus;
  ollama_reachable: boolean;
  model_installed: boolean;
  inference_tested: boolean;
  response_time_ms: number | null;
  error: string | null;
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
  critical: number;
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
  duration_seconds?: number;
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
  run_id?: string;
  monitoring?: PipelineRunState;
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

export type PipelineRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'review_required'
  | 'blocked'
  | 'failed';

export type PipelineStageStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'blocked';

export interface PipelineFinding {
  finding_id: string;
  detector_type: string;
  severity: Severity;
  column: string | null;
  description: string;
  detection_method: string;
  baseline_metrics: Record<string, string | number | boolean | null>;
  current_metrics: Record<string, string | number | boolean | null>;
}

export interface PipelineStageState {
  stage_id: string;
  name: string;
  status: PipelineStageStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  progress: number | null;
  findings_count: number;
  findings: PipelineFinding[];
  error_category: string | null;
  message: string | null;
}

export interface PipelineRunState {
  run_id: string;
  pipeline_name: string;
  status: PipelineRunStatus;
  created_at: string;
  updated_at: string;
  current_stage: string | null;
  stages: PipelineStageState[];
  findings: PipelineFinding[];
  findings_count: number;
  protection_decision: ProtectionDecision | null;
  downstream_processing_allowed: boolean;
  downstream_executed: boolean;
  protection_reasons: string[];
  report_id: string | null;
  latest_sequence: number;
  history_truncated: boolean;
  error_category: string | null;
}

export interface PipelineEvent {
  event_id: string;
  run_id: string;
  sequence: number;
  timestamp: string;
  event_type:
    | 'pipeline_started'
    | 'stage_started'
    | 'stage_progress'
    | 'stage_completed'
    | 'stage_failed'
    | 'stage_skipped'
    | 'finding_detected'
    | 'protection_decided'
    | 'pipeline_completed'
    | 'pipeline_failed'
    | 'pipeline_blocked';
  stage_id: string | null;
  stage_name: string | null;
  status: PipelineStageStatus | null;
  progress: number | null;
  duration_ms: number | null;
  finding_count: number | null;
  finding: PipelineFinding | null;
  protection_decision: ProtectionDecision | null;
  downstream_processing_allowed: boolean | null;
  finding_counts: FindingCounts | null;
  reasons: string[] | null;
  error_category: string | null;
  message: string | null;
}

export interface ExperimentScenario {
  scenario_id: string;
  name: string;
  description: string;
  finding_type: string;
  correction: string;
}

export interface ExperimentTarget {
  finding_type: string;
  column: string | null;
}

export interface ExperimentOperation {
  kind: string;
  column?: string;
  affected_rows?: number;
  factor?: number;
  injected_category?: string;
}

export interface RecoveryVerification {
  status:
    | 'resolved'
    | 'unresolved'
    | 'injection_not_detected'
    | 'analysis_failed';
  target_findings_detected_before: boolean[];
  target_findings_detected_after: boolean[];
  unrelated_findings_remaining: number;
}

export interface ExperimentRecord {
  experiment_id: string;
  scenario_id: string;
  scenario_name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at?: string;
  dataset_name: string;
  dataset_version_before: string;
  dataset_version_after_injection: string;
  dataset_version_after_correction?: string;
  injection_parameters: ExperimentOperation[];
  targets: ExperimentTarget[];
  initial_run_id: string;
  recovery_run_id: string | null;
  findings_before: PipelineFinding[];
  protection_before: ProtectionDecision | null;
  correction_actions: string[];
  findings_after: PipelineFinding[];
  protection_after: ProtectionDecision | null;
  recovery_verification: RecoveryVerification | null;
  run_summary?: {
    run_id: string;
    status: PipelineRunStatus;
    protection_decision: ProtectionDecision | null;
    findings: PipelineFinding[];
    findings_count: number;
    report_id: string | null;
  };
  run?: PipelineRunState | null;
  ai_reasoning?: AIReasoning | null;
}

export interface ExperimentScenariosResponse {
  scenarios: ExperimentScenario[];
}

export interface ExperimentsResponse {
  experiments: ExperimentRecord[];
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
