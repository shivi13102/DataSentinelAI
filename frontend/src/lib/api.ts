// ============================================================
// DataSentinel AI – Typed API client
// All communication with FastAPI goes through this module.
// No secrets are stored here. The base URL is persisted in
// localStorage so users can adjust it in Settings.
// ============================================================

import type {
  HealthResponse,
  AnalysisReport,
  ReportsResponse,
  PipelineEvent,
  PipelineRunState,
  ExperimentRecord,
  ExperimentScenario,
  ExperimentScenariosResponse,
  ExperimentsResponse,
} from '../types/api';

const STORAGE_KEY = 'ds_api_base_url';
export const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

export function getApiBaseUrl(): string {
  return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_BASE_URL;
}

export function setApiBaseUrl(url: string): void {
  const trimmed = url.trim().replace(/\/$/, '');
  if (trimmed) {
    localStorage.setItem(STORAGE_KEY, trimmed);
  }
}

// ── Internal helpers ──────────────────────────────────────────

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status} – ${res.statusText}`;
    try {
      const body = (await res.json()) as Record<string, unknown>;
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      // Body is not JSON; use status text.
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ── Public API functions ──────────────────────────────────────

/**
 * Verify that the backend is reachable and retrieve its
 * configuration information.
 */
export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${getApiBaseUrl()}/api/health`);
  return handleResponse<HealthResponse>(res);
}

/**
 * Submit two CSV files for analysis.
 * Uses multipart/form-data; the boundary is set by the browser.
 * Do NOT manually set Content-Type on FormData requests.
 */
export async function analyzeDatasets(
  baselineFile: File,
  currentFile: File,
): Promise<AnalysisReport> {
  const form = new FormData();
  form.append('baseline_file', baselineFile);
  form.append('current_file', currentFile);

  const res = await fetch(`${getApiBaseUrl()}/api/analyze`, {
    method: 'POST',
    body: form,
  });

  return handleResponse<AnalysisReport>(res);
}

export async function createPipelineRun(
  scenario: string,
  baselineFile?: File,
  currentFile?: File,
): Promise<PipelineRunState> {
  const form = new FormData();
  form.append('scenario', scenario);
  if (baselineFile) form.append('baseline_file', baselineFile);
  if (currentFile) form.append('current_file', currentFile);

  const res = await fetch(`${getApiBaseUrl()}/api/pipeline-runs`, {
    method: 'POST',
    body: form,
  });
  return handleResponse<PipelineRunState>(res);
}

export async function fetchPipelineRun(
  runId: string,
): Promise<PipelineRunState> {
  const res = await fetch(
    `${getApiBaseUrl()}/api/pipeline-runs/${encodeURIComponent(runId)}`,
  );
  return handleResponse<PipelineRunState>(res);
}

export async function fetchExperimentScenarios(): Promise<ExperimentScenario[]> {
  const res = await fetch(`${getApiBaseUrl()}/api/experiments/scenarios`);
  const result = await handleResponse<ExperimentScenariosResponse>(res);
  return result.scenarios;
}

export async function fetchExperiments(): Promise<ExperimentRecord[]> {
  const res = await fetch(`${getApiBaseUrl()}/api/experiments?limit=20`);
  const result = await handleResponse<ExperimentsResponse>(res);
  return result.experiments;
}

export async function fetchExperiment(
  experimentId: string,
): Promise<ExperimentRecord> {
  const res = await fetch(
    `${getApiBaseUrl()}/api/experiments/${encodeURIComponent(experimentId)}`,
  );
  return handleResponse<ExperimentRecord>(res);
}

export async function createExperiment(
  scenarioId: string,
  datasetFile?: File,
): Promise<ExperimentRecord> {
  const form = new FormData();
  form.append('scenario_id', scenarioId);
  if (datasetFile) form.append('dataset_file', datasetFile);

  const res = await fetch(`${getApiBaseUrl()}/api/experiments`, {
    method: 'POST',
    body: form,
  });
  return handleResponse<ExperimentRecord>(res);
}

export async function correctExperiment(
  experimentId: string,
): Promise<ExperimentRecord> {
  const res = await fetch(
    `${getApiBaseUrl()}/api/experiments/${encodeURIComponent(experimentId)}/correct`,
    { method: 'POST' },
  );
  return handleResponse<ExperimentRecord>(res);
}

export function subscribeToPipelineRun(
  runId: string,
  afterSequence: number,
  onEvent: (event: PipelineEvent) => void,
  onReset: (state: PipelineRunState) => void,
  onConnectionChange: (connected: boolean) => void,
): EventSource {
  const url = new URL(
    `${getApiBaseUrl()}/api/pipeline-runs/${encodeURIComponent(runId)}/events`,
  );
  url.searchParams.set('after_sequence', String(afterSequence));
  const source = new EventSource(url);

  source.onopen = () => onConnectionChange(true);
  source.onerror = () => onConnectionChange(false);
  source.addEventListener('pipeline', (message: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(message.data) as PipelineEvent);
    } catch {
      onConnectionChange(false);
    }
  });
  source.addEventListener('reset', (message: MessageEvent<string>) => {
    try {
      onReset(JSON.parse(message.data) as PipelineRunState);
    } catch {
      onConnectionChange(false);
    }
  });
  return source;
}

/**
 * Retrieve saved report summaries (newest first).
 */
export async function fetchReports(): Promise<ReportsResponse> {
  const res = await fetch(`${getApiBaseUrl()}/api/reports`);
  return handleResponse<ReportsResponse>(res);
}

/**
 * Retrieve the full JSON of a specific saved report.
 */
export async function fetchReport(reportId: string): Promise<AnalysisReport> {
  const res = await fetch(`${getApiBaseUrl()}/api/reports/${reportId}`);
  return handleResponse<AnalysisReport>(res);
}

/**
 * Download a saved report as a Blob for file-system export.
 */
export async function downloadReportBlob(reportId: string): Promise<Blob> {
  const res = await fetch(`${getApiBaseUrl()}/api/reports/${reportId}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.blob();
}
