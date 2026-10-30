import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  LoaderCircle,
  RotateCcw,
  ShieldAlert,
} from 'lucide-react';

import {
  correctExperiment,
  createExperiment,
  fetchExperiment,
  fetchExperimentScenarios,
  fetchExperiments,
} from '../lib/api';
import type {
  ExperimentRecord,
  ExperimentScenario,
  PipelineFinding,
} from '../types/api';
import { Button } from '../components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '../components/ui/Card';
import { cn, formatTimestamp, getFindingTypeLabel } from '../lib/utils';

function isRunActive(status: string) {
  return status === 'running' || status === 'recovery_running';
}

function upsertExperiment(
  records: ExperimentRecord[],
  next: ExperimentRecord,
) {
  return [
    next,
    ...records.filter((record) => record.experiment_id !== next.experiment_id),
  ].slice(0, 20);
}

export function ExperimentLab() {
  const [scenarios, setScenarios] = useState<ExperimentScenario[]>([]);
  const [history, setHistory] = useState<ExperimentRecord[]>([]);
  const [experiment, setExperiment] = useState<ExperimentRecord | null>(null);
  const [scenarioId, setScenarioId] = useState('missing_values');
  const [datasetMode, setDatasetMode] = useState<'sample' | 'upload'>('sample');
  const [datasetFile, setDatasetFile] = useState<File | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyExperiment = useCallback((record: ExperimentRecord) => {
    setExperiment(record);
    setHistory((previous) => upsertExperiment(previous, record));
  }, []);

  const loadHistory = useCallback(async () => {
    const records = await fetchExperiments();
    setHistory(records);
  }, []);

  useEffect(() => {
    Promise.all([fetchExperimentScenarios(), fetchExperiments()])
      .then(([scenarioList, records]) => {
        setScenarios(scenarioList);
        setHistory(records);
        if (records.length > 0) setExperiment(records[0]);
      })
      .catch((reason: unknown) => {
        setError(
          reason instanceof Error
            ? reason.message
            : 'Unable to load experiment data.',
        );
      });
  }, []);

  useEffect(() => {
    if (!experiment || !isRunActive(experiment.status)) return;
    const intervalId = window.setInterval(() => {
      fetchExperiment(experiment.experiment_id)
        .then(applyExperiment)
        .catch((reason: unknown) => {
          setError(
            reason instanceof Error
              ? reason.message
              : 'Unable to refresh experiment status.',
          );
        });
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [applyExperiment, experiment]);

  const start = async () => {
    if (loading) return;
    if (datasetMode === 'upload' && !datasetFile) {
      setError('Choose a CSV dataset before starting the experiment.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await createExperiment(
        scenarioId,
        datasetMode === 'upload' ? datasetFile : undefined,
      );
      applyExperiment(result);
      try {
        await loadHistory();
      } catch {
        setError(
          'The experiment started, but the history list could not be refreshed.',
        );
      }
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Unable to start experiment.',
      );
    } finally {
      setLoading(false);
    }
  };

  const recover = async () => {
    if (!experiment || loading) return;
    setLoading(true);
    setError(null);
    try {
      applyExperiment(await correctExperiment(experiment.experiment_id));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Unable to apply the controlled correction.',
      );
    } finally {
      setLoading(false);
    }
  };

  const selectHistory = async (experimentId: string) => {
    setError(null);
    try {
      applyExperiment(await fetchExperiment(experimentId));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Unable to load experiment.',
      );
    }
  };

  const selectedScenario = scenarios.find(
    (scenario) => scenario.scenario_id === scenarioId,
  );
  const runActive = experiment ? isRunActive(experiment.status) : false;
  const recoverable = experiment?.status === 'experiment_completed';

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6">
      <header>
        <div className="flex items-center gap-2">
          <FlaskConical className="h-5 w-5 text-cyan-300" />
          <h1 className="text-xl font-bold tracking-tight text-[#E5EDF9]">
            Anomaly Injection & Recovery Lab
          </h1>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-[#8B9BB4]">
          Reproduce a controlled data issue on an isolated copy, inspect actual
          detector and protection-gate results, then validate a targeted correction.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Configure an experiment</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-xs text-[#8B9BB4]">
              Anomaly scenario
              <select
                value={scenarioId}
                onChange={(event) => setScenarioId(event.target.value)}
                className="rounded border border-[#2a3a52] bg-[#0B1423] px-3 py-2 text-sm text-[#E5EDF9]"
              >
                {scenarios.map((scenario) => (
                  <option
                    value={scenario.scenario_id}
                    key={scenario.scenario_id}
                  >
                    {scenario.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-xs text-[#8B9BB4]">
              Dataset
              <select
                value={datasetMode}
                onChange={(event) =>
                  setDatasetMode(event.target.value as 'sample' | 'upload')
                }
                className="rounded border border-[#2a3a52] bg-[#0B1423] px-3 py-2 text-sm text-[#E5EDF9]"
              >
                <option value="sample">Built-in transaction sample</option>
                <option value="upload">Upload a CSV for isolated testing</option>
              </select>
            </label>
          </div>

          {datasetMode === 'upload' && (
            <label className="mt-4 flex max-w-xl flex-col gap-1.5 text-xs text-[#8B9BB4]">
              CSV dataset
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(event) =>
                  setDatasetFile(event.target.files?.[0])
                }
                className="rounded border border-[#2a3a52] bg-[#0B1423] p-2 text-xs text-[#E5EDF9]"
              />
            </label>
          )}

          {selectedScenario && (
            <div className="mt-4 rounded border border-[#223149] bg-[#0B1423] p-4">
              <p className="text-sm font-semibold text-[#E5EDF9]">
                {selectedScenario.name}
              </p>
              <p className="mt-1 text-sm text-[#9BAAC0]">
                {selectedScenario.description}
              </p>
              <p className="mt-2 text-xs text-[#71829B]">
                Scenario prediction, not a measured result: the{' '}
                {getFindingTypeLabel(selectedScenario.finding_type)} detector
                will inspect evidence from the modified copy. Detection is
                verified only after the actual run finishes.
              </p>
              <p className="mt-2 text-xs text-[#71829B]">
                Controlled correction: {selectedScenario.correction}
              </p>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              disabled={loading || runActive || scenarios.length === 0}
              onClick={() => void start()}
            >
              {loading || runActive ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FlaskConical className="mr-2 h-4 w-4" />
              )}
              {runActive ? 'Experiment running…' : 'Run experiment'}
            </Button>
            <p className="text-xs text-[#71829B]">
              The source dataset is preserved. Isolated CSV versions and
              metadata are stored locally under reports/experiments.
            </p>
          </div>
          {error && (
            <p role="alert" className="mt-3 text-sm text-red-300">
              {error}
            </p>
          )}
        </CardBody>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {experiment ? (
            <ExperimentResult
              experiment={experiment}
              runActive={runActive}
              recoverable={Boolean(recoverable)}
              loading={loading}
              onRecover={() => void recover()}
            />
          ) : (
            <Card>
              <CardBody>
                <p className="py-8 text-sm text-[#8B9BB4]">
                  Run an experiment or select a previous experiment to inspect
                  its measured findings and recovery result.
                </p>
              </CardBody>
            </Card>
          )}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Experiment history</CardTitle>
          </CardHeader>
          <CardBody className="space-y-2">
            {history.length === 0 ? (
              <p className="text-sm text-[#8B9BB4]">
                No experiments have been recorded yet.
              </p>
            ) : (
              history.map((record) => (
                <button
                  key={record.experiment_id}
                  type="button"
                  aria-current={
                    experiment?.experiment_id === record.experiment_id
                      ? 'true'
                      : undefined
                  }
                  onClick={() => void selectHistory(record.experiment_id)}
                  className={cn(
                    'w-full rounded border p-3 text-left transition-colors hover:border-cyan-700',
                    experiment?.experiment_id === record.experiment_id
                      ? 'border-cyan-700 bg-cyan-950/30'
                      : 'border-[#223149] bg-[#0B1423]',
                  )}
                >
                  <span className="block text-xs font-semibold text-[#E5EDF9]">
                    {record.scenario_name}
                  </span>
                  <span className="mt-1 block text-[10px] text-[#71829B]">
                    {formatTimestamp(record.created_at)}
                  </span>
                  <span className="mt-2 inline-block rounded border border-[#2a3a52] px-2 py-0.5 text-[10px] text-[#9BAAC0]">
                    {record.status.replaceAll('_', ' ')}
                  </span>
                </button>
              ))
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function ExperimentResult({
  experiment,
  runActive,
  recoverable,
  loading,
  onRecover,
}: {
  experiment: ExperimentRecord;
  runActive: boolean;
  recoverable: boolean;
  loading: boolean;
  onRecover: () => void;
}) {
  const run = experiment.run;
  const runSummary = experiment.run_summary;
  const completedStages =
    run?.stages.filter((stage) => stage.status === 'completed').length ?? 0;
  const currentStage = run?.stages.find(
    (stage) => stage.stage_id === run.current_stage,
  );

  return (
    <>
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Experiment execution</CardTitle>
            <p className="mt-1 font-mono text-[10px] text-[#71829B]">
              {experiment.experiment_id}
            </p>
          </div>
          <span className="rounded border border-[#2a3a52] px-2 py-1 text-xs capitalize text-[#9BAAC0]">
            {experiment.status.replaceAll('_', ' ')}
          </span>
        </CardHeader>
        <CardBody>
          <p className="text-sm font-semibold text-[#E5EDF9]">
            {experiment.scenario_name}
          </p>
          <p className="mt-1 text-xs text-[#9BAAC0]">
            Dataset: {experiment.dataset_name}
          </p>
          {runActive ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-cyan-200">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              {currentStage
                ? `Running ${currentStage.name}`
                : `${completedStages} stages completed`}
            </div>
          ) : run ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Metric label="Measured stages" value={completedStages} />
              <Metric label="Actual findings" value={run.findings_count} />
              <Metric
                label="Protection decision"
                value={run.protection_decision ?? 'NOT DECIDED'}
              />
            </div>
          ) : runSummary ? (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <Metric label="Actual findings" value={runSummary.findings_count} />
                <Metric
                  label="Protection decision"
                  value={runSummary.protection_decision ?? 'NOT DECIDED'}
                />
                <Metric label="Persisted run" value={runSummary.status.toUpperCase()} />
              </div>
              <p className="mt-2 text-xs text-[#71829B]">
                The live run snapshot is no longer retained by this API process;
                the completed experiment outcome is persisted.
              </p>
            </>
          ) : (
            <p role="alert" className="mt-4 text-sm text-amber-200">
              The run snapshot is not available in this API process. Stored
              experiment metadata remains available, but its live run state was
              held in memory.
            </p>
          )}
        </CardBody>
      </Card>

      <FindingPanel
        title="Measured findings before correction"
        findings={experiment.findings_before}
        emptyMessage={
          runActive
            ? 'Findings will appear after detector stages complete.'
            : 'The completed run reported no detector findings.'
        }
      />

      {experiment.protection_before && (
        <ProtectionPanel
          decision={experiment.protection_before}
          label="Protection decision before correction"
        />
      )}

      {experiment.ai_reasoning && (
        <Card>
          <CardHeader>
            <CardTitle>Gemma explanation (advisory)</CardTitle>
          </CardHeader>
          <CardBody>
            {experiment.ai_reasoning.status === 'success' &&
            experiment.ai_reasoning.explanation ? (
              <>
                <p className="text-sm text-[#B8C5D8]">
                  {experiment.ai_reasoning.explanation.incident_summary}
                </p>
                <div className="mt-3 space-y-2">
                  {experiment.ai_reasoning.explanation.root_cause_hypotheses.map(
                    (hypothesis, index) => (
                      <p
                        key={`${index}-${hypothesis.hypothesis}`}
                        className="rounded border border-[#223149] p-3 text-xs text-[#9BAAC0]"
                      >
                        Hypothesis ({hypothesis.confidence} confidence):{' '}
                        {hypothesis.hypothesis}
                      </p>
                    ),
                  )}
                </div>
              </>
            ) : experiment.ai_reasoning.status === 'skipped' ? (
              <p className="text-sm text-[#9BAAC0]">
                There were no measured findings to explain, so the AI
                investigation was skipped.
              </p>
            ) : (
              <p className="text-sm text-[#9BAAC0]">
                AI assistance is unavailable for this run. Deterministic
                findings and the protection decision remain available.
              </p>
            )}
          </CardBody>
        </Card>
      )}

      {recoverable && (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-[#E5EDF9]">
                Recovery is ready to verify
              </p>
              <p className="mt-1 text-xs text-[#8B9BB4]">
                The correction restores only controlled changes on the isolated
                copy and runs the same detector and protection pipeline again.
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={loading}
              onClick={onRecover}
            >
              {loading ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RotateCcw className="mr-2 h-4 w-4" />
              )}
              Apply correction and rerun
            </Button>
          </CardBody>
        </Card>
      )}

      {experiment.recovery_run_id && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Recovery verification</CardTitle>
            </CardHeader>
            <CardBody>
              {experiment.recovery_verification ? (
                <div
                  role="status"
                  className={cn(
                    'flex items-start gap-3 rounded border p-3',
                    experiment.recovery_verification.status === 'resolved'
                      ? 'border-emerald-800 bg-emerald-950/30 text-emerald-200'
                      : 'border-amber-800 bg-amber-950/30 text-amber-100',
                  )}
                >
                  {experiment.recovery_verification.status === 'resolved' ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  ) : (
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  )}
                  <div>
                    <p className="text-sm font-semibold">
                      {experiment.recovery_verification.status.replaceAll(
                        '_',
                        ' ',
                      )}
                    </p>
                    <p className="mt-1 text-xs">
                      Verification checks the targeted detector and column
                      before and after correction; unrelated findings are
                      reported separately.
                    </p>
                    <p className="mt-1 text-xs">
                      Unrelated findings remaining:{' '}
                      {
                        experiment.recovery_verification
                          .unrelated_findings_remaining
                      }
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[#9BAAC0]">
                  The corrected dataset is being analyzed; verification will
                  use the actual detector output.
                </p>
              )}
              {experiment.correction_actions.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-[#9BAAC0]">
                  {experiment.correction_actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>

          <FindingPanel
            title="Measured findings after correction"
            findings={experiment.findings_after}
            emptyMessage={
              experiment.recovery_verification
                ? 'The recovery run reported no detector findings.'
                : 'Findings will appear after detector stages complete.'
            }
          />

          {experiment.protection_after && (
            <ProtectionPanel
              decision={experiment.protection_after}
              label="Protection decision after correction"
            />
          )}
        </>
      )}
    </>
  );
}

function FindingPanel({
  title,
  findings,
  emptyMessage,
}: {
  title: string;
  findings: PipelineFinding[];
  emptyMessage: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardBody className="space-y-3">
        {findings.length === 0 ? (
          <p className="text-sm text-[#8B9BB4]">{emptyMessage}</p>
        ) : (
          findings.map((finding) => (
            <article
              key={finding.finding_id}
              className="rounded border border-[#223149] bg-[#0B1423] p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-[#E5EDF9]">
                  {getFindingTypeLabel(finding.detector_type)}
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
              <p className="mt-2 text-sm text-[#B8C5D8]">
                {finding.description}
              </p>
              <p className="mt-2 text-xs text-[#71829B]">
                {finding.detection_method}
              </p>
            </article>
          ))
        )}
      </CardBody>
    </Card>
  );
}

function ProtectionPanel({
  decision,
  label,
}: {
  decision: string;
  label: string;
}) {
  const blocked = decision === 'BLOCK';
  const review = decision === 'REVIEW_REQUIRED';
  return (
    <Card>
      <CardBody className="flex items-center gap-3">
        <ShieldAlert
          className={cn(
            'h-5 w-5',
            blocked ? 'text-red-300' : review ? 'text-amber-300' : 'text-emerald-300',
          )}
        />
        <div>
          <p className="text-xs text-[#71829B]">{label}</p>
          <p
            className={cn(
              'mt-1 text-sm font-bold',
              blocked
                ? 'text-red-200'
                : review
                  ? 'text-amber-200'
                  : 'text-emerald-200',
            )}
          >
            {decision}
          </p>
        </div>
      </CardBody>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-[#223149] px-3 py-2">
      <p className="font-semibold text-[#E5EDF9]">{value}</p>
      <p className="text-[10px] text-[#71829B]">{label}</p>
    </div>
  );
}
