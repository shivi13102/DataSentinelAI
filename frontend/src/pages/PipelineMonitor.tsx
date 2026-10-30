import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock3,
  Database,
  Download,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';

import {
  createPipelineRun,
  fetchPipelineRun,
  getApiBaseUrl,
  subscribeToPipelineRun,
} from '../lib/api';
import type {
  PipelineRunState,
  PipelineStageState,
  PipelineStageStatus,
} from '../types/api';
import { Button } from '../components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '../components/ui/Card';
import { cn, formatTimestamp } from '../lib/utils';

const STORAGE_KEY = 'ds_active_pipeline_run';

const SCENARIOS = [
  ['healthy', 'Healthy fixture'],
  ['suspicious', 'Suspicious fixture (review required)'],
  ['critical', 'Critical fixture (block)'],
  ['duplicate', 'Duplicate anomaly fixture'],
  ['numerical_drift', 'Numerical drift fixture'],
  ['categorical_drift', 'Categorical drift fixture'],
  ['multiple', 'Multiple anomalies fixture'],
] as const;

const GRAPH_NODES = [
  { stageId: 'dataset_loading', row: 1, column: 2 },
  { stageId: 'input_validation', row: 2, column: 2 },
  { stageId: 'schema_analysis', row: 3, column: 2 },
  { stageId: 'missing_value_analysis', row: 4, column: 2 },
  { stageId: 'duplicate_analysis', row: 5, column: 2 },
  { stageId: 'numerical_drift_analysis', row: 6, column: 2 },
  { stageId: 'categorical_drift_analysis', row: 7, column: 2 },
  { stageId: 'findings_aggregation', row: 8, column: 2 },
  { stageId: 'protection_gate', row: 9, column: 2 },
  { stageId: 'ai_investigation', row: 10, column: 1 },
  { stageId: 'downstream_execution', row: 10, column: 3 },
  { stageId: 'report_generation', row: 11, column: 2 },
] as const;

const GRAPH_EDGES = [
  ['dataset_loading', 'input_validation'],
  ['input_validation', 'schema_analysis'],
  ['schema_analysis', 'missing_value_analysis'],
  ['missing_value_analysis', 'duplicate_analysis'],
  ['duplicate_analysis', 'numerical_drift_analysis'],
  ['numerical_drift_analysis', 'categorical_drift_analysis'],
  ['categorical_drift_analysis', 'findings_aggregation'],
  ['findings_aggregation', 'protection_gate'],
  ['protection_gate', 'ai_investigation'],
  ['protection_gate', 'downstream_execution'],
  ['ai_investigation', 'report_generation'],
  ['downstream_execution', 'report_generation'],
] as const;

const STATUS_LABELS: Record<PipelineStageStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  skipped: 'Skipped',
  blocked: 'Blocked',
};

const STATUS_STYLES: Record<PipelineStageStatus, string> = {
  pending: 'border-slate-700 bg-slate-900/50 text-slate-400',
  running: 'border-cyan-700 bg-cyan-950/50 text-cyan-300',
  completed: 'border-emerald-800 bg-emerald-950/50 text-emerald-300',
  failed: 'border-red-800 bg-red-950/50 text-red-300',
  skipped: 'border-slate-700 bg-slate-900/50 text-slate-400',
  blocked: 'border-amber-800 bg-amber-950/50 text-amber-300',
};

function StageIcon({ status }: { status: PipelineStageStatus }) {
  if (status === 'running') {
    return <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />;
  }
  if (status === 'completed') {
    return <CheckCircle2 aria-hidden="true" className="h-4 w-4" />;
  }
  if (status === 'failed') {
    return <XCircle aria-hidden="true" className="h-4 w-4" />;
  }
  if (status === 'blocked') {
    return <ShieldAlert aria-hidden="true" className="h-4 w-4" />;
  }
  return <Circle aria-hidden="true" className="h-4 w-4" />;
}

function formatDuration(duration: number | null, status: PipelineStageStatus) {
  if (duration !== null) return `${duration.toFixed(1)} ms`;
  if (status === 'running') return 'Measured on completion';
  return 'Not measured';
}

export function PipelineMonitor() {
  const [run, setRun] = useState<PipelineRunState | null>(null);
  const [scenario, setScenario] = useState<string>('healthy');
  const [baselineFile, setBaselineFile] = useState<File | undefined>();
  const [currentFile, setCurrentFile] = useState<File | undefined>();
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState<
    'connecting' | 'connected' | 'reconnecting' | 'closed'
  >('closed');
  const eventSource = useRef<EventSource | null>(null);
  const latestSequence = useRef(0);
  const activeRunId = useRef<string | null>(null);

  const applySnapshot = useCallback((snapshot: PipelineRunState) => {
    if (snapshot.run_id !== activeRunId.current) return;
    if (snapshot.latest_sequence < latestSequence.current) return;
    latestSequence.current = snapshot.latest_sequence;
    setRun(snapshot);
  }, []);

  const refreshSnapshot = useCallback(
    async (runId: string) => {
      try {
        const snapshot = await fetchPipelineRun(runId);
        applySnapshot(snapshot);
      } catch (reason) {
        setError(
          reason instanceof Error ? reason.message : 'Unable to retrieve run state.',
        );
      }
    },
    [applySnapshot],
  );

  const connectToRun = useCallback(
    (runId: string, afterSequence: number) => {
      eventSource.current?.close();
      activeRunId.current = runId;
      setConnection('connecting');
      eventSource.current = subscribeToPipelineRun(
        runId,
        afterSequence,
        (event) => {
          if (event.run_id !== activeRunId.current) return;
          if (event.sequence <= latestSequence.current) return;
          latestSequence.current = event.sequence;
          void refreshSnapshot(runId);
        },
        applySnapshot,
        (connected) => {
          setConnection((current) => {
            if (connected) return 'connected';
            return current === 'closed' ? 'closed' : 'reconnecting';
          });
          if (!connected) void refreshSnapshot(runId);
        },
      );
    },
    [applySnapshot, refreshSnapshot],
  );

  useEffect(() => {
    const savedRunId = localStorage.getItem(STORAGE_KEY);
    if (!savedRunId) return;

    activeRunId.current = savedRunId;
    void fetchPipelineRun(savedRunId)
      .then((snapshot) => {
        applySnapshot(snapshot);
        if (
          snapshot.status === 'queued' ||
          snapshot.status === 'running'
        ) {
          connectToRun(savedRunId, snapshot.latest_sequence);
        }
      })
      .catch(() => {
        localStorage.removeItem(STORAGE_KEY);
        activeRunId.current = null;
      });

    return () => {
      eventSource.current?.close();
      eventSource.current = null;
    };
  }, [applySnapshot, connectToRun]);

  useEffect(() => {
    if (run && ['completed', 'review_required', 'blocked', 'failed'].includes(run.status)) {
      eventSource.current?.close();
      eventSource.current = null;
    }
  }, [run]);

  const startRun = async () => {
    if (creating || runActive) return;
    if (scenario === 'custom' && (!baselineFile || !currentFile)) {
      setError('Select both baseline and current CSV files.');
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const newRun = await createPipelineRun(
        scenario,
        scenario === 'custom' ? baselineFile : undefined,
        scenario === 'custom' ? currentFile : undefined,
      );
      localStorage.setItem(STORAGE_KEY, newRun.run_id);
      activeRunId.current = newRun.run_id;
      latestSequence.current = newRun.latest_sequence;
      setRun(newRun);
      setSelectedStageId(null);
      connectToRun(newRun.run_id, newRun.latest_sequence);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Unable to start the pipeline.',
      );
    } finally {
      setCreating(false);
    }
  };

  const reconnect = async () => {
    if (!run) return;
    setError(null);
    await refreshSnapshot(run.run_id);
    connectToRun(run.run_id, latestSequence.current);
  };

  const selectedStage =
    run?.stages.find((stage) => stage.stage_id === selectedStageId) ?? null;
  const finishedStages =
    run?.stages.filter((stage) => stage.status === 'completed').length ?? 0;
  const failedStages =
    run?.stages.filter((stage) => stage.status === 'failed').length ?? 0;
  const skippedStages =
    run?.stages.filter(
      (stage) => stage.status === 'skipped' || stage.status === 'blocked',
    ).length ?? 0;
  const runActive = run?.status === 'queued' || run?.status === 'running';
  const displayedConnection =
    run && ['completed', 'review_required', 'blocked', 'failed'].includes(run.status)
      ? 'closed'
      : connection;

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#E5EDF9]">
            Live Pipeline Monitor
          </h1>
          <p className="mt-1 text-sm text-[#8B9BB4]">
            Stage states and findings are streamed from the actual backend run.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {run && (
            <span className="rounded border border-[#223149] px-3 py-2 font-mono text-xs text-[#8B9BB4]">
              {run.run_id}
            </span>
          )}
          {run && (
            <Button variant="secondary" size="sm" onClick={reconnect}>
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              Reconnect
            </Button>
          )}
        </div>
      </header>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-cyan-300" />
            <CardTitle>Start a monitored run</CardTitle>
          </div>
        </CardHeader>
        <CardBody>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-64 flex-col gap-1 text-xs text-[#8B9BB4]">
              Dataset source
              <select
                value={scenario}
                onChange={(event) => setScenario(event.target.value)}
                className="rounded border border-[#2a3a52] bg-[#0B1423] px-3 py-2 text-sm text-[#E5EDF9]"
              >
                {SCENARIOS.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
                <option value="custom">Upload custom CSV pair</option>
              </select>
            </label>

            {scenario === 'custom' && (
              <>
                <label className="flex min-w-56 flex-col gap-1 text-xs text-[#8B9BB4]">
                  Baseline CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) =>
                      setBaselineFile(event.target.files?.[0])
                    }
                    className="max-w-72 text-xs text-[#E5EDF9]"
                  />
                </label>
                <label className="flex min-w-56 flex-col gap-1 text-xs text-[#8B9BB4]">
                  Current CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) =>
                      setCurrentFile(event.target.files?.[0])
                    }
                    className="max-w-72 text-xs text-[#E5EDF9]"
                  />
                </label>
              </>
            )}

            <Button
              variant="primary"
              size="sm"
              disabled={creating || runActive}
              onClick={() => void startRun()}
            >
              {creating ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {creating ? 'Starting…' : runActive ? 'Run in progress' : 'Start pipeline'}
            </Button>
          </div>
          <p className="mt-3 text-xs text-[#71829B]">
            Fixture scenarios are deterministic examples. Custom CSV contents
            are analyzed in memory and are not included in the live event stream.
          </p>
          {error && (
            <p role="alert" className="mt-3 text-sm text-red-300">
              {error}
            </p>
          )}
        </CardBody>
      </Card>

      {run ? (
        <>
          <RunSummary
            run={run}
            connection={displayedConnection}
            finishedStages={finishedStages}
            failedStages={failedStages}
            skippedStages={skippedStages}
          />

          <PipelineDag
            stages={run.stages}
            selectedStageId={selectedStageId}
            onSelect={setSelectedStageId}
          />

          {selectedStage && <StageDetails stage={selectedStage} />}

          {run.protection_reasons.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-amber-300" />
                  <CardTitle>Protection gate reasons</CardTitle>
                </div>
              </CardHeader>
              <CardBody>
                <ul className="list-disc space-y-1 pl-5 text-sm text-[#C2CCDA]">
                  {run.protection_reasons.map((reason, index) => (
                    <li key={`${index}-${reason}`}>{reason}</li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}

          {run.report_id && run.status !== 'running' && run.status !== 'queued' && (
            <a
              href={`${getApiBaseUrl()}/api/pipeline-runs/${run.run_id}/report`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200"
            >
              <Download className="h-4 w-4" />
              Open final run report
            </a>
          )}
        </>
      ) : (
        <Card>
          <CardBody>
            <div className="flex items-center gap-3 py-8 text-[#8B9BB4]">
              <Clock3 className="h-5 w-5" />
              <p>Start a run to view its backend-reported stages and events.</p>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

function PipelineDag({
  stages,
  selectedStageId,
  onSelect,
}: {
  stages: PipelineStageState[];
  selectedStageId: string | null;
  onSelect: (stageId: string) => void;
}) {
  const stageById = new Map(stages.map((stage) => [stage.stage_id, stage]));
  const nodeById = new Map(GRAPH_NODES.map((node) => [node.stageId, node]));
  const xPosition = (column: number) => [0, 167, 500, 833][column];
  const yCenter = (row: number) => 40 + (row - 1) * 100;

  return (
    <section aria-label="Pipeline dependency graph">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-[#8B9BB4]">
          Directed dependencies · branch outcomes join in the final report
        </p>
        <div className="flex flex-wrap gap-3 text-[10px] text-[#8B9BB4]">
          {(['completed', 'running', 'failed', 'pending'] as const).map((status) => (
            <span className="flex items-center gap-1.5" key={status}>
              <span
                className={cn(
                  'h-2 w-2 rounded-full',
                  status === 'completed' && 'bg-emerald-400',
                  status === 'running' && 'bg-cyan-300',
                  status === 'failed' && 'bg-red-400',
                  status === 'pending' && 'bg-slate-500',
                )}
              />
              {STATUS_LABELS[status]}
            </span>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-[#223149] bg-[#080F1C] p-3">
        <div className="relative mx-auto min-w-[700px] max-w-5xl">
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox="0 0 1000 1080"
            preserveAspectRatio="none"
          >
            <defs>
              <marker
                id="pipeline-arrow"
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
              >
                <path d="M0,0 L0,6 L6,3 z" fill="#64748B" />
              </marker>
            </defs>
            {GRAPH_EDGES.map(([sourceId, targetId]) => {
              const source = nodeById.get(sourceId);
              const target = nodeById.get(targetId);
              if (!source || !target) return null;
              const sourceStage = stageById.get(sourceId);
              const targetStage = stageById.get(targetId);
              const startX = xPosition(source.column);
              const endX = xPosition(target.column);
              const startY = yCenter(source.row) + 40;
              const endY = yCenter(target.row) - 40;
              const curveY = (startY + endY) / 2;
              const isComplete =
                sourceStage?.status === 'completed' &&
                targetStage?.status === 'completed';

              return (
                <path
                  key={`${sourceId}-${targetId}`}
                  d={`M ${startX} ${startY} C ${startX} ${curveY}, ${endX} ${curveY}, ${endX} ${endY}`}
                  fill="none"
                  stroke={isComplete ? '#10B981' : '#40516B'}
                  strokeWidth="2"
                  markerEnd="url(#pipeline-arrow)"
                />
              );
            })}
          </svg>
          <div className="grid h-[1080px] grid-cols-3 grid-rows-[repeat(11,80px)] gap-y-5">
            {GRAPH_NODES.map(({ stageId, row, column }) => {
              const stage = stageById.get(stageId);
              if (!stage) return null;
              return (
                <button
                  key={stage.stage_id}
                  type="button"
                  aria-label={`${stage.name}: ${STATUS_LABELS[stage.status]}`}
                  aria-pressed={selectedStageId === stage.stage_id}
                  onClick={() => onSelect(stage.stage_id)}
                  style={{
                    gridColumn: column,
                    gridRow: row,
                  }}
                  className={cn(
                    'z-10 mx-2 flex min-w-0 flex-col justify-center rounded-lg border px-3 py-2 text-left shadow-lg transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400',
                    STATUS_STYLES[stage.status],
                    selectedStageId === stage.stage_id
                      ? 'ring-2 ring-cyan-400'
                      : 'hover:border-cyan-700',
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2 text-xs font-semibold">
                      <StageIcon status={stage.status} />
                      <span className="truncate">{stage.name}</span>
                    </span>
                    {stage.findings_count > 0 && (
                      <span className="shrink-0 rounded bg-amber-950 px-1.5 py-0.5 text-[10px] text-amber-200">
                        {stage.findings_count}
                      </span>
                    )}
                  </span>
                  <span className="mt-2 truncate text-[10px] text-[#9BAAC0]">
                    {formatDuration(stage.duration_ms, stage.status)}
                    {stage.message ? ` · ${stage.message}` : ''}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function RunSummary({
  run,
  connection,
  finishedStages,
  failedStages,
  skippedStages,
}: {
  run: PipelineRunState;
  connection: string;
  finishedStages: number;
  failedStages: number;
  skippedStages: number;
}) {
  const decisionStyle =
    run.protection_decision === 'BLOCK'
      ? 'text-red-300 border-red-800 bg-red-950/40'
      : run.protection_decision === 'REVIEW_REQUIRED'
        ? 'text-amber-200 border-amber-800 bg-amber-950/40'
        : run.protection_decision === 'ALLOW'
          ? 'text-emerald-200 border-emerald-800 bg-emerald-950/40'
          : 'text-slate-300 border-slate-700 bg-slate-900/40';

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-[#71829B]">
              Pipeline run status
            </p>
            <p className="mt-1 text-lg font-bold text-[#E5EDF9]">
              {run.status.replaceAll('_', ' ').toUpperCase()}
            </p>
            <p className="mt-1 text-xs text-[#8B9BB4]">
              {run.current_stage
                ? `Current stage: ${run.stages.find((stage) => stage.stage_id === run.current_stage)?.name ?? run.current_stage}`
                : 'No stage is currently running'}
              {' · '}
              Stream: {connection}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Metric label="Stages complete" value={finishedStages} />
            <Metric label="Stages failed" value={failedStages} />
            <Metric label="Stages blocked/skipped" value={skippedStages} />
            <Metric label="Actual findings" value={run.findings_count} />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-[#223149] pt-4">
          <span className={cn('rounded border px-3 py-1.5 text-xs font-bold', decisionStyle)}>
            Protection: {run.protection_decision ?? 'NOT DECIDED'}
          </span>
          <span className="text-xs text-[#9BAAC0]">
            Downstream permitted: {run.downstream_processing_allowed ? 'Yes' : 'No'}
            {' · '}
            Executed: {run.downstream_executed ? 'Yes' : 'No'}
          </span>
        </div>

        {run.status === 'blocked' && (
          <p role="status" className="mt-3 flex items-center gap-2 text-sm text-red-200">
            <AlertTriangle className="h-4 w-4" />
            The protection policy blocked downstream execution.
          </p>
        )}
        {run.status === 'review_required' && (
          <p role="status" className="mt-3 flex items-center gap-2 text-sm text-amber-200">
            <AlertTriangle className="h-4 w-4" />
            Downstream work is withheld pending human review; no approval is implemented.
          </p>
        )}
        {run.status === 'failed' && (
          <p role="alert" className="mt-3 text-sm text-red-200">
            Run failed ({run.error_category ?? 'unknown error'}). Downstream execution was not authorized.
          </p>
        )}
        {run.history_truncated && (
          <p className="mt-3 text-xs text-amber-200">
            Earlier event history was evicted; this view reflects the latest authoritative state snapshot.
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-[#223149] px-3 py-2">
      <p className="font-semibold text-[#E5EDF9]">{value}</p>
      <p className="text-[10px] text-[#71829B]">{label}</p>
    </div>
  );
}

function StageDetails({ stage }: { stage: PipelineStageState }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{stage.name}</CardTitle>
          <p className="mt-1 font-mono text-xs text-[#71829B]">{stage.stage_id}</p>
        </div>
        <span className={cn('rounded border px-2 py-1 text-xs', STATUS_STYLES[stage.status])}>
          {STATUS_LABELS[stage.status]}
        </span>
      </CardHeader>
      <CardBody>
        <div className="grid gap-3 text-xs text-[#9BAAC0] sm:grid-cols-3">
          <p>Started: {stage.started_at ? formatTimestamp(stage.started_at) : 'Not started'}</p>
          <p>Completed: {stage.completed_at ? formatTimestamp(stage.completed_at) : 'Not completed'}</p>
          <p>Measured duration: {formatDuration(stage.duration_ms, stage.status)}</p>
        </div>
        {stage.progress !== null && (
          <p className="mt-3 text-xs text-cyan-200">
            Reported progress: {stage.progress}%
          </p>
        )}
        {stage.error_category && (
          <p className="mt-3 text-sm text-red-300">
            Safe error category: {stage.error_category}
          </p>
        )}
        {stage.findings.length > 0 && (
          <div className="mt-4 space-y-3">
            <h3 className="text-sm font-semibold text-[#E5EDF9]">
              Actual detector findings
            </h3>
            {stage.findings.map((finding) => (
              <article
                key={finding.finding_id}
                className="rounded border border-[#2a3a52] bg-[#0B1423] p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-[#E5EDF9]">
                    {finding.detector_type}
                  </span>
                  <span className="rounded border border-amber-800 px-2 py-0.5 text-[10px] uppercase text-amber-200">
                    {finding.severity}
                  </span>
                  {finding.column && (
                    <span className="font-mono text-xs text-cyan-200">
                      {finding.column}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm text-[#B8C5D8]">{finding.description}</p>
                <p className="mt-2 text-xs text-[#71829B]">
                  Rule: {finding.detection_method}
                </p>
                <MetricList label="Baseline measurements" values={finding.baseline_metrics} />
                <MetricList label="Current measurements" values={finding.current_metrics} />
              </article>
            ))}
          </div>
        )}
        {stage.status === 'pending' && (
          <p className="mt-3 text-xs text-[#71829B]">
            This stage has not started; duration and findings are not yet measured.
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function MetricList({
  label,
  values,
}: {
  label: string;
  values: Record<string, string | number | boolean | null>;
}) {
  const entries = Object.entries(values);
  if (entries.length === 0) return null;
  return (
    <p className="mt-2 text-xs text-[#9BAAC0]">
      {label}:{' '}
      {entries.map(([key, value]) => `${key}=${String(value)}`).join(' · ')}
    </p>
  );
}
