// ============================================================
// Pipeline Monitor – Visual data pipeline observability view
// ============================================================

import { useContext, useState } from 'react';
import {
  Database,
  ArrowRight,
  ShieldAlert,
  Brain,
  Sliders,
  AlertTriangle,
  Info,
  Server,
  Layers,
} from 'lucide-react';

import { AppContext } from '../App';
import type { AnalysisReport, Finding } from '../types/api';
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card';
import { Badge, ProtectionBadge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { cn, formatNumber, formatTimestamp } from '../lib/utils';

type PipelineStageId = 'source' | 'transform' | 'validation' | 'ai_investigation' | 'downstream';

interface StageMeta {
  id: PipelineStageId;
  name: string;
  category: string;
  icon: React.ElementType;
  description: string;
}

const STAGES: StageMeta[] = [
  {
    id: 'source',
    name: 'Source Dataset',
    category: 'Ingestion Layer',
    icon: Database,
    description: 'Baseline reference and current CSV ingestion',
  },
  {
    id: 'transform',
    name: 'Transformation',
    category: 'Reference Stage',
    icon: Sliders,
    description: 'Logical staging boundary (not a live orchestrator)',
  },
  {
    id: 'validation',
    name: 'Data Validation',
    category: 'Quality Gate',
    icon: Layers,
    description: 'Python deterministic anomaly & drift detectors',
  },
  {
    id: 'ai_investigation',
    name: 'AI Investigation',
    category: 'Reasoning Agent',
    icon: Brain,
    description: 'Local Gemma model root-cause hypothesis generation',
  },
  {
    id: 'downstream',
    name: 'Downstream Analytics',
    category: 'Protection Gate',
    icon: ShieldAlert,
    description: 'Authoritative evaluation gate (ALLOW / REVIEW / BLOCK)',
  },
];

export function PipelineMonitor() {
  const { latestReport, navigate } = useContext(AppContext);
  const [selectedStage, setSelectedStage] = useState<PipelineStageId>('validation');

  const report = latestReport;
  const hasReport = report !== null;

  // Determine dynamic statuses
  const stageStatuses: Record<PipelineStageId, {
    status: 'healthy' | 'warning' | 'critical' | 'neutral';
    label: string;
    summary: string;
  }> = {
    source: hasReport
      ? {
          status: 'healthy',
          label: 'Ingested',
          summary: `${report.analysis.baseline_rows.toLocaleString()} baseline rows · ${report.analysis.current_rows.toLocaleString()} current rows`,
        }
      : {
          status: 'neutral',
          label: 'Pending Ingestion',
          summary: 'Awaiting baseline and current CSV upload',
        },
    transform: hasReport
      ? {
          status: 'healthy',
          label: 'Standardized',
          summary: 'Logical reference normalization applied',
        }
      : {
          status: 'neutral',
          label: 'Standby',
          summary: 'Awaiting incoming source batches',
        },
    validation: hasReport
      ? report.analysis.overall_status === 'critical'
        ? {
            status: 'critical',
            label: 'Risk Detected',
            summary: `${report.analysis.total_findings} data-quality anomalies detected`,
          }
        : report.analysis.overall_status === 'warning'
        ? {
            status: 'warning',
            label: 'Degraded',
            summary: `${report.analysis.total_findings} warnings flagged`,
          }
        : {
            status: 'healthy',
            label: 'Passed',
            summary: 'Zero anomalies detected',
          }
      : {
          status: 'neutral',
          label: 'Not Executed',
          summary: 'Awaiting execution trigger',
        },
    ai_investigation: hasReport
      ? report.ai_reasoning.status === 'success'
        ? {
            status: 'healthy',
            label: 'Complete',
            summary: `${report.ai_reasoning.model ?? 'Gemma'} produced ${report.ai_reasoning.explanation?.root_cause_hypotheses.length ?? 0} hypotheses`,
          }
        : report.ai_reasoning.status === 'skipped'
        ? {
            status: 'neutral',
            label: 'Skipped',
            summary: 'Reasoning skipped or not required',
          }
        : {
            status: 'warning',
            label: 'Failed',
            summary: 'Reasoning agent error; Python findings preserved',
          }
      : {
          status: 'neutral',
          label: 'Idle',
          summary: 'Local Ollama reasoning agent in standby',
        },
    downstream: hasReport
      ? report.protection.decision === 'BLOCK'
        ? {
            status: 'critical',
            label: 'BLOCKED',
            summary: 'Downstream distribution halted by Protection Gate',
          }
        : report.protection.decision === 'REVIEW_REQUIRED'
        ? {
            status: 'warning',
            label: 'REVIEW REQUIRED',
            summary: 'Human verification required before consumption',
          }
        : {
            status: 'healthy',
            label: 'ALLOWED',
            summary: 'Dataset released for downstream consumption',
          }
      : {
          status: 'neutral',
          label: 'Protected',
          summary: 'Protection gate active (fail-closed)',
        },
  };

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#E5EDF9] tracking-tight">
            Data Pipeline Monitor
          </h1>
          <p className="text-sm text-[#8B9BB4] mt-0.5">
            Logical pipeline architecture & data observability gate view.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasReport && (
            <Badge variant="neutral" size="sm">
              Report ID: {report.report_id.slice(-8)}
            </Badge>
          )}
          <Button variant="secondary" size="sm" onClick={() => navigate('analysis')}>
            Run Pipeline Analysis
          </Button>
        </div>
      </div>

      {/* Observability Disclaimer Notice */}
      <div className="flex items-start gap-3 rounded-lg border border-[#223149] bg-[#101A2B] p-4">
        <Info className="h-4 w-4 text-[#22D3EE] shrink-0 mt-0.5" />
        <div className="text-xs text-[#8B9BB4] leading-relaxed">
          <span className="text-[#E5EDF9] font-medium">Logical Observability Model:</span>{' '}
          This topology models the flow of data across stages in DataSentinel AI. While data validation and
          protection gates execute deterministically via Python and LangGraph, this interface represents
          the verification boundary for imported datasets rather than a live production orchestrator
          connector (e.g. Airflow or Dagster).
        </div>
      </div>

      {/* Connected Nodes View */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 relative">
        {STAGES.map((stage, idx) => {
          const Icon = stage.icon;
          const statusInfo = stageStatuses[stage.id];
          const isSelected = selectedStage === stage.id;

          return (
            <div key={stage.id} className="flex flex-col relative">
              <button
                onClick={() => setSelectedStage(stage.id)}
                className={cn(
                  'w-full text-left rounded-lg border p-4 transition-all focus-ring relative z-10 flex flex-col justify-between h-full min-h-[145px]',
                  isSelected
                    ? 'border-[#22D3EE] bg-[#142036] shadow-lg shadow-cyan-950/20'
                    : 'border-[#223149] bg-[#101A2B] hover:border-[#2d4a6e] hover:bg-[#121c2e]',
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div
                      className={cn(
                        'flex h-8 w-8 items-center justify-center rounded',
                        statusInfo.status === 'critical'
                          ? 'bg-red-950/60 text-red-400'
                          : statusInfo.status === 'warning'
                          ? 'bg-amber-950/60 text-amber-400'
                          : statusInfo.status === 'healthy'
                          ? 'bg-emerald-950/60 text-emerald-400'
                          : 'bg-slate-800/60 text-slate-400',
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <span
                      className={cn(
                        'text-[10px] font-semibold px-2 py-0.5 rounded border tracking-wide uppercase',
                        statusInfo.status === 'critical'
                          ? 'border-red-800/60 bg-red-950/40 text-red-400'
                          : statusInfo.status === 'warning'
                          ? 'border-amber-800/60 bg-amber-950/40 text-amber-400'
                          : statusInfo.status === 'healthy'
                          ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-400'
                          : 'border-slate-800 bg-slate-900/40 text-slate-400',
                      )}
                    >
                      {statusInfo.label}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-[#E5EDF9]">{stage.name}</p>
                  <p className="text-[10px] text-[#8B9BB4] mt-0.5">{stage.category}</p>
                </div>

                <div className="mt-3 pt-2 border-t border-[#1a2d45]">
                  <p className="text-[11px] text-[#8B9BB4] truncate">{statusInfo.summary}</p>
                </div>
              </button>

              {/* Connecting line on desktop */}
              {idx < STAGES.length - 1 && (
                <div className="hidden lg:flex absolute top-1/2 -right-3 -translate-y-1/2 z-0 pointer-events-none text-[#223149]">
                  <ArrowRight className="h-4 w-4 text-[#223149]" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Stage Detail Panel on Selection */}
      <Card elevated>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-cyan-950/50 text-[#22D3EE] border border-cyan-800/30">
              <Server className="h-3.5 w-3.5" />
            </div>
            <div>
              <CardTitle>
                Stage Inspection: {STAGES.find(s => s.id === selectedStage)?.name}
              </CardTitle>
              <p className="text-xs text-[#8B9BB4]">
                {STAGES.find(s => s.id === selectedStage)?.description}
              </p>
            </div>
          </div>
          <span className="text-xs text-[#8B9BB4] font-mono">
            Node ID: {selectedStage}
          </span>
        </CardHeader>
        <CardBody>
          {selectedStage === 'source' && (
            <SourceStageDetail report={report} onNavigateAnalysis={() => navigate('analysis')} />
          )}
          {selectedStage === 'transform' && (
            <TransformStageDetail report={report} />
          )}
          {selectedStage === 'validation' && (
            <ValidationStageDetail report={report} onNavigateAnomalies={() => navigate('anomalies')} />
          )}
          {selectedStage === 'ai_investigation' && (
            <AIStageDetail report={report} onNavigateInvestigation={() => navigate('investigation')} />
          )}
          {selectedStage === 'downstream' && (
            <DownstreamStageDetail report={report} />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

// ── Detail Panels for each stage ─────────────────────────────

function SourceStageDetail({
  report,
  onNavigateAnalysis,
}: {
  report: AnalysisReport | null;
  onNavigateAnalysis: () => void;
}) {
  if (!report) {
    return (
      <EmptyState
        icon={<Database className="h-5 w-5" />}
        title="No dataset ingested"
        description="Upload a baseline and current dataset to populate ingestion evidence."
        action={
          <Button variant="primary" size="sm" onClick={onNavigateAnalysis}>
            Upload CSVs
          </Button>
        }
      />
    );
  }

  const { baseline, current } = report.dataset_metadata;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg bg-[#101A2B] border border-[#223149] p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#8B9BB4] uppercase">Baseline Reference</span>
            <Badge variant="info">Trusted</Badge>
          </div>
          <p className="text-sm font-semibold text-[#E5EDF9] font-mono">{baseline.filename}</p>
          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#1a2d45] text-center">
            <div>
              <p className="text-base font-bold text-[#22D3EE]">{formatNumber(baseline.rows, 0)}</p>
              <p className="text-[10px] text-[#8B9BB4]">Rows</p>
            </div>
            <div>
              <p className="text-base font-bold text-[#60A5FA]">{baseline.columns}</p>
              <p className="text-[10px] text-[#8B9BB4]">Columns</p>
            </div>
            <div>
              <p className="text-base font-bold text-[#E5EDF9]">{(baseline.size_bytes / 1024).toFixed(1)} KB</p>
              <p className="text-[10px] text-[#8B9BB4]">Payload</p>
            </div>
          </div>
        </div>

        <div className="rounded-lg bg-[#101A2B] border border-[#223149] p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#8B9BB4] uppercase">Current Batch</span>
            <Badge variant="warning">Investigated</Badge>
          </div>
          <p className="text-sm font-semibold text-[#E5EDF9] font-mono">{current.filename}</p>
          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#1a2d45] text-center">
            <div>
              <p className="text-base font-bold text-[#22D3EE]">{formatNumber(current.rows, 0)}</p>
              <p className="text-[10px] text-[#8B9BB4]">Rows</p>
            </div>
            <div>
              <p className="text-base font-bold text-[#60A5FA]">{current.columns}</p>
              <p className="text-[10px] text-[#8B9BB4]">Columns</p>
            </div>
            <div>
              <p className="text-base font-bold text-[#E5EDF9]">{(current.size_bytes / 1024).toFixed(1)} KB</p>
              <p className="text-[10px] text-[#8B9BB4]">Payload</p>
            </div>
          </div>
        </div>
      </div>
      <p className="text-xs text-[#8B9BB4]">
        Ingestion completed at <span className="text-[#E5EDF9]">{formatTimestamp(report.generated_at)}</span>. Both datasets validated successfully into Pandas memory frames.
      </p>
    </div>
  );
}

function TransformStageDetail({
  report,
}: {
  report: AnalysisReport | null;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-[#101A2B] border border-[#223149] p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-[#8B9BB4] uppercase">Transformation Status</span>
          <Badge variant="success">Standard Reference</Badge>
        </div>
        <p className="text-sm text-[#E5EDF9]">
          Data Sentinel processes immutable in-memory DataFrame mirrors. No underlying row manipulation or lossy transformations occur during inspection.
        </p>
        <div className="pt-2 border-t border-[#1a2d45] grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-[#8B9BB4]">
          <div>
            <span className="text-[#E5EDF9] font-medium block">Header Parsing</span>
            Strict CSV UTF-8 decoding
          </div>
          <div>
            <span className="text-[#E5EDF9] font-medium block">Numeric Normalization</span>
            Coerced float64 for statistical tests
          </div>
          <div>
            <span className="text-[#E5EDF9] font-medium block">Category Indexing</span>
            Contingency union alignment
          </div>
        </div>
      </div>
      <p className="text-xs text-[#8B9BB4]">
        {report ? 'Reference transformation passed without schema errors.' : 'Stage on standby.'}
      </p>
    </div>
  );
}

function ValidationStageDetail({
  report,
  onNavigateAnomalies,
}: {
  report: AnalysisReport | null;
  onNavigateAnomalies: () => void;
}) {
  if (!report) {
    return (
      <EmptyState
        icon={<AlertTriangle className="h-5 w-5" />}
        title="Validation not yet run"
        description="Run an analysis to execute deterministic quality detectors."
      />
    );
  }

  const { overall_status, total_findings, severity_counts, findings } = report.analysis;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-[#101A2B] border border-[#223149]">
        <div className="flex items-center gap-3">
          <StatusBadge status={overall_status} />
          <span className="text-sm font-semibold text-[#E5EDF9]">
            {total_findings} Anomaly Finding{total_findings === 1 ? '' : 's'} Emitted
          </span>
        </div>
        <Button variant="secondary" size="sm" onClick={onNavigateAnomalies}>
          Open Anomaly Explorer
        </Button>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-lg bg-[#101A2B] border border-red-900/30 p-3">
          <p className="text-xl font-bold text-red-400">{severity_counts.high}</p>
          <p className="text-xs text-[#8B9BB4] mt-0.5">High Severity</p>
        </div>
        <div className="rounded-lg bg-[#101A2B] border border-amber-900/30 p-3">
          <p className="text-xl font-bold text-amber-400">{severity_counts.medium}</p>
          <p className="text-xs text-[#8B9BB4] mt-0.5">Medium Severity</p>
        </div>
        <div className="rounded-lg bg-[#101A2B] border border-slate-800 p-3">
          <p className="text-xl font-bold text-slate-400">{severity_counts.low}</p>
          <p className="text-xs text-[#8B9BB4] mt-0.5">Low Severity</p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold text-[#8B9BB4] uppercase">Detector Findings Preview</p>
        <div className="divide-y divide-[#1a2d45] rounded-lg border border-[#223149] bg-[#101A2B]">
          {findings.map((f: Finding, i: number) => (
            <div key={i} className="flex items-center justify-between p-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[#60A5FA]">{f.column ?? 'Global'}</span>
                <span className="text-[#8B9BB4]">·</span>
                <span className="text-[#E5EDF9]">{f.description}</span>
              </div>
              <span className="text-[11px] font-mono text-[#8B9BB4] shrink-0 ml-2">
                {f.detection_method.replace(/_/g, ' ')}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AIStageDetail({
  report,
  onNavigateInvestigation,
}: {
  report: AnalysisReport | null;
  onNavigateInvestigation: () => void;
}) {
  if (!report) {
    return (
      <EmptyState
        icon={<Brain className="h-5 w-5" />}
        title="AI investigation not triggered"
        description="Reasoning agent triggers automatically after validation completes."
      />
    );
  }

  const { status, model, explanation, error } = report.ai_reasoning;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between p-3 rounded-lg bg-[#101A2B] border border-[#223149]">
        <div className="flex items-center gap-3">
          <Badge variant={status === 'success' ? 'success' : 'warning'}>
            Status: {status.toUpperCase()}
          </Badge>
          <span className="text-xs font-mono text-[#22D3EE]">Model: {model ?? 'gemma3:1b'}</span>
        </div>
        <Button variant="secondary" size="sm" onClick={onNavigateInvestigation}>
          View Investigation Workspace
        </Button>
      </div>

      {status === 'success' && explanation ? (
        <div className="rounded-lg bg-[#101A2B] border border-[#223149] p-4 space-y-3">
          <div>
            <p className="text-xs font-semibold text-[#8B9BB4] uppercase">Model Incident Summary</p>
            <p className="text-sm text-[#E5EDF9] mt-1">{explanation.incident_summary}</p>
          </div>
          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#1a2d45]">
            <div>
              <span className="text-xs text-[#8B9BB4]">Root Cause Hypotheses:</span>
              <p className="text-base font-bold text-[#60A5FA]">
                {explanation.root_cause_hypotheses.length} generated
              </p>
            </div>
            <div>
              <span className="text-xs text-[#8B9BB4]">Action Checklist:</span>
              <p className="text-base font-bold text-[#FBBF24]">
                {explanation.recommended_actions.length} recommendations
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-lg bg-red-950/20 border border-red-900/40 text-xs text-red-300">
          Reasoning agent error: {error ?? 'Could not contact local Ollama service.'}
        </div>
      )}
    </div>
  );
}

function DownstreamStageDetail({
  report,
}: {
  report: AnalysisReport | null;
}) {
  if (!report) {
    return (
      <EmptyState
        icon={<ShieldAlert className="h-5 w-5" />}
        title="Gate status pending"
        description="Gate evaluates deterministically once validation results exist."
      />
    );
  }

  const { decision, downstream_processing_allowed, human_review_required, reasons } =
    report.protection;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between p-4 rounded-lg bg-[#101A2B] border border-[#223149]">
        <div className="flex items-center gap-3">
          <ProtectionBadge decision={decision} />
          <span className="text-sm font-semibold text-[#E5EDF9]">
            {decision === 'BLOCK'
              ? 'Downstream Pipeline Ingestion Terminated'
              : decision === 'REVIEW_REQUIRED'
              ? 'Downstream Ingestion Paused For Review'
              : 'Downstream Ingestion Authorized'}
          </span>
        </div>
        <Badge variant={downstream_processing_allowed ? 'success' : 'critical'}>
          {downstream_processing_allowed ? 'Allowed' : 'Halted'}
        </Badge>
      </div>

      <div className="rounded-lg bg-[#101A2B] border border-[#223149] p-4 space-y-3">
        <p className="text-xs font-semibold text-[#8B9BB4] uppercase">Protection Reasons</p>
        <ul className="space-y-2 text-xs text-[#E5EDF9]">
          {reasons.map((r: string, i: number) => (
            <li key={i} className="flex items-start gap-2">
              <span className="text-[#22D3EE] font-mono">•</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="p-3 rounded-lg bg-[#142036] border border-[#223149] flex items-center justify-between text-xs text-[#8B9BB4]">
        <span>Human Review Enforcement:</span>
        <span className={human_review_required ? 'text-amber-400 font-semibold' : 'text-emerald-400 font-semibold'}>
          {human_review_required ? 'Required (Mandatory)' : 'Not Required'}
        </span>
      </div>
    </div>
  );
}
