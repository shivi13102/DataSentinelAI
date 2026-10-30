// ============================================================
// AI Investigation – enterprise incident analysis workspace
// ============================================================

import { useContext, useState } from 'react';
import {
  Brain,
  AlertTriangle,
  ShieldAlert,
  CheckSquare,
  Square,
  Info,
  Users,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

import { AppContext } from '../App';
import type { Finding, RootCauseHypothesis } from '../types/api';
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card';
import { Badge, SeverityBadge, ProtectionBadge, StatusBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import {
  cn,
  formatTimestamp,
  formatNumber,
  formatPercent,
  formatPValue,
  getFindingTypeLabel,
} from '../lib/utils';

export function AIInvestigation() {
  const { latestReport, navigate } = useContext(AppContext);

  if (!latestReport) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<Brain className="h-6 w-6" />}
          title="No investigation available"
          description="Run a dataset analysis to generate an AI investigation report."
          action={
            <Button variant="primary" size="sm" onClick={() => navigate('analysis')}>
              Analyse Datasets
            </Button>
          }
        />
      </div>
    );
  }

  const { ai_reasoning, analysis, protection, report_id, generated_at } = latestReport;
  const explanation = ai_reasoning.explanation;
  const aiSucceeded = ai_reasoning.status === 'success' && explanation != null;

  return (
    <div className="p-6 space-y-6 max-w-[1200px] mx-auto">

      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-[#E5EDF9] tracking-tight">AI Investigation</h1>
            <StatusBadge status={ai_reasoning.status} />
          </div>
          <p className="text-xs text-[#8B9BB4] font-mono">ID: {report_id}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {ai_reasoning.model && (
            <Badge variant="info" size="md">
              <Brain className="h-3 w-3 mr-1" />
              <span className="font-mono">{ai_reasoning.model}</span>
            </Badge>
          )}
          <SeverityBadge severity={
            analysis.overall_status === 'critical' ? 'high' :
            analysis.overall_status === 'warning' ? 'medium' : 'low'
          } />
          <span className="text-xs text-[#8B9BB4]">{formatTimestamp(generated_at)}</span>
        </div>
      </div>

      {/* ── AI unavailable banner ─────────────────────────────── */}
      {!aiSucceeded && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-900/50 bg-amber-950/20 px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-300">
              AI investigation {ai_reasoning.status === 'skipped' ? 'was skipped' : 'failed'}
            </p>
            <p className="text-xs text-amber-400/80 mt-0.5">
              {ai_reasoning.error ?? 'AI reasoning did not complete. Python analysis results are still available below.'}
            </p>
          </div>
        </div>
      )}

      {/* ── Observed Evidence ─────────────────────────────────── */}
      <Section
        label="A"
        title="Observed Evidence"
        description="Facts calculated by Python detectors. These are measured values, not AI estimates."
      >
        {analysis.findings.length === 0 ? (
          <p className="text-sm text-[#8B9BB4]">No findings in the latest analysis.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {analysis.findings.map((f, i) => (
              <EvidenceCard key={i} finding={f} index={i + 1} />
            ))}
          </div>
        )}
      </Section>

      {/* ── Root-Cause Hypotheses ─────────────────────────────── */}
      <Section
        label="B"
        title="Root-Cause Hypotheses"
        description="AI-generated. Treat these as hypotheses requiring human verification, not confirmed root causes."
        aiGenerated
      >
        {aiSucceeded ? (
          <div className="space-y-3">
            {explanation.root_cause_hypotheses.map((h, i) => (
              <HypothesisCard key={i} hypothesis={h} index={i + 1} />
            ))}
          </div>
        ) : (
          <AIUnavailablePlaceholder />
        )}
      </Section>

      {/* ── Business Impact ───────────────────────────────────── */}
      <Section
        label="C"
        title="Business Impact"
        description="AI-generated assessment of potential downstream effects."
        aiGenerated
      >
        {aiSucceeded ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {explanation.business_impacts.map((impact, i) => (
              <div
                key={i}
                className="flex items-start gap-3 rounded-lg border border-[#223149] bg-[#142036] p-3"
              >
                <div className="h-5 w-5 shrink-0 rounded-full bg-red-950/50 flex items-center justify-center">
                  <ShieldAlert className="h-3 w-3 text-red-400" />
                </div>
                <p className="text-sm text-[#E5EDF9] leading-relaxed">{impact}</p>
              </div>
            ))}
          </div>
        ) : (
          <AIUnavailablePlaceholder />
        )}
      </Section>

      {/* ── Recommended Actions ───────────────────────────────── */}
      <Section
        label="D"
        title="Recommended Corrective Actions"
        description="AI-suggested steps. Mark items as reviewed locally. This does not execute any remediation."
        aiGenerated
      >
        {aiSucceeded ? (
          <ActionChecklist actions={explanation.recommended_actions} />
        ) : (
          <AIUnavailablePlaceholder />
        )}
      </Section>

      {/* ── Uncertainty & Limits ──────────────────────────────── */}
      <Section
        label="E"
        title="Uncertainty & Human Review"
        description="Limitations of this investigation."
      >
        <div className="space-y-3">
          <LimitRow
            title="Measured evidence is deterministic"
            detail="The findings listed in Section A are calculated by Python and reflect the actual data. They are not AI estimates."
          />
          <LimitRow
            title="Root causes require verification"
            detail="Hypotheses in Section B are generated by a language model and must be confirmed against your data pipeline and source systems."
          />
          <LimitRow
            title="AI model limitations"
            detail={`This investigation used ${ai_reasoning.model ?? 'an AI model'} running locally via Ollama. The model may produce plausible-sounding but incorrect explanations.`}
          />
          {aiSucceeded && (
            <LimitRow
              title="Human review required"
              detail="AI investigation explicitly flagged that human review is mandatory before any production data changes."
            />
          )}
        </div>
      </Section>

      {/* ── Protection Gate ───────────────────────────────────── */}
      <Section
        label="F"
        title="Investigation Status & Protection Gate"
        description="The protection decision is made deterministically by Python. The AI cannot override it."
      >
        <div className="space-y-4">

          {/* Decision card */}
          <div className={cn(
            'flex items-center justify-between gap-4 rounded-lg border p-4',
            protection.decision === 'BLOCK'           ? 'border-red-900/50 bg-red-950/30' :
            protection.decision === 'REVIEW_REQUIRED' ? 'border-amber-900/50 bg-amber-950/30' :
                                                        'border-emerald-900/50 bg-emerald-950/30',
          )}>
            <div>
              <ProtectionBadge decision={protection.decision} />
              <p className="text-sm text-[#E5EDF9] mt-2">
                {protection.reasons[0] ?? 'No protection reason provided.'}
              </p>
              <p className={cn(
                'text-xs mt-1',
                protection.downstream_processing_allowed ? 'text-emerald-400' : 'text-red-400',
              )}>
                Downstream processing:{' '}
                {protection.downstream_processing_allowed ? 'Permitted' : 'Not permitted automatically'}
              </p>
            </div>
            {protection.human_review_required && (
              <div className="flex items-center gap-2 text-amber-400 shrink-0">
                <Users className="h-4 w-4" />
                <span className="text-xs font-medium">Human review required</span>
              </div>
            )}
          </div>

          {/* Findings summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'High', count: protection.finding_counts.high, color: 'text-red-400' },
              { label: 'Medium', count: protection.finding_counts.medium, color: 'text-amber-400' },
              { label: 'Low', count: protection.finding_counts.low, color: 'text-slate-400' },
              { label: 'Total', count: protection.finding_counts.total, color: 'text-[#22D3EE]' },
            ].map(({ label, count, color }) => (
              <div key={label} className="text-center rounded-lg bg-[#142036] border border-[#223149] p-3">
                <p className={cn('text-xl font-bold', color)}>{count}</p>
                <p className="text-[11px] text-[#8B9BB4] mt-0.5">{label}</p>
              </div>
            ))}
          </div>

          {/* Gate reasons */}
          {protection.reasons.length > 1 && (
            <div className="space-y-1">
              {protection.reasons.slice(1).map((r, i) => (
                <p key={i} className="text-xs text-[#8B9BB4] pl-3 border-l-2 border-[#223149]">{r}</p>
              ))}
            </div>
          )}
        </div>
      </Section>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

interface SectionProps {
  label: string;
  title: string;
  description?: string;
  children: React.ReactNode;
  aiGenerated?: boolean;
}

function Section({ label, title, description, children, aiGenerated }: SectionProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-[#142036] text-[11px] font-bold text-[#22D3EE] border border-[#223149]">
            {label}
          </span>
          <div>
            <CardTitle>{title}</CardTitle>
            {description && <p className="text-xs text-[#8B9BB4] mt-0.5">{description}</p>}
          </div>
        </div>
        {aiGenerated && (
          <Badge variant="warning" size="sm">AI Generated</Badge>
        )}
      </CardHeader>
      <CardBody>{children}</CardBody>
    </Card>
  );
}

function EvidenceCard({ finding, index }: { finding: Finding; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-[#223149] bg-[#142036] p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-bold text-[#8B9BB4]">#{index}</span>
          <SeverityBadge severity={finding.severity} />
          <Badge variant="info" size="sm">{getFindingTypeLabel(finding.type)}</Badge>
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-[#8B9BB4] hover:text-[#E5EDF9] transition-colors"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>
      </div>
      {finding.column && (
        <p className="text-xs text-[#8B9BB4]">
          Column: <span className="font-mono text-[#60A5FA]">{finding.column}</span>
        </p>
      )}
      <p className="text-xs text-[#E5EDF9] leading-relaxed">{finding.description}</p>
      {expanded && <EvidenceDetail finding={finding} />}
    </div>
  );
}

function EvidenceDetail({ finding }: { finding: Finding }) {
  if (finding.type === 'distribution_drift') {
    const bv = finding.baseline_value as Record<string, number>;
    const cv = finding.current_value as Record<string, number>;
    return (
      <div className="pt-2 border-t border-[#223149] space-y-1 text-xs">
        <DetailRow label="Baseline mean" value={formatNumber(bv.mean ?? 0)} />
        <DetailRow label="Current mean" value={formatNumber(cv.mean ?? 0)} highlight />
        <DetailRow label="KS p-value" value={finding.ks_p_value != null ? formatPValue(finding.ks_p_value) : '—'} />
      </div>
    );
  }
  if (finding.type === 'missing_value_anomaly') {
    const bv = finding.baseline_value as Record<string, number>;
    const cv = finding.current_value as Record<string, number>;
    return (
      <div className="pt-2 border-t border-[#223149] space-y-1 text-xs">
        <DetailRow label="Baseline" value={formatPercent(bv.missing_percentage ?? 0)} />
        <DetailRow label="Current" value={formatPercent(cv.missing_percentage ?? 0)} highlight />
        <DetailRow label="Change" value={finding.change_percentage_points != null ? `+${formatPercent(finding.change_percentage_points)} pp` : '—'} />
      </div>
    );
  }
  if (finding.type === 'duplicate_anomaly') {
    const cv = finding.current_value as Record<string, number>;
    return (
      <div className="pt-2 border-t border-[#223149] space-y-1 text-xs">
        <DetailRow label="Duplicate rows" value={(cv.duplicate_count ?? 0).toLocaleString()} highlight />
        <DetailRow label="Duplicate rate" value={formatPercent(cv.duplicate_percentage ?? 0)} />
      </div>
    );
  }
  if (finding.type === 'categorical_drift') {
    return (
      <div className="pt-2 border-t border-[#223149] space-y-1 text-xs">
        <DetailRow label="TVD" value={finding.total_variation_distance != null ? formatNumber(finding.total_variation_distance, 4) : '—'} highlight />
        <DetailRow label="p-value" value={finding.p_value != null ? formatPValue(finding.p_value) : '—'} />
        {finding.new_categories && finding.new_categories.length > 0 && (
          <DetailRow label="New categories" value={finding.new_categories.join(', ')} />
        )}
      </div>
    );
  }
  return null;
}

function DetailRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-[#8B9BB4]">{label}</span>
      <span className={highlight ? 'text-[#E5EDF9] font-medium' : 'text-[#E5EDF9]'}>{value}</span>
    </div>
  );
}

function HypothesisCard({ hypothesis, index }: { hypothesis: RootCauseHypothesis; index: number }) {
  const confidenceColor = {
    high: 'text-amber-400 border-amber-900/40 bg-amber-950/20',
    medium: 'text-orange-400 border-orange-900/40 bg-orange-950/20',
    low: 'text-slate-400 border-slate-700/40 bg-slate-800/20',
  }[hypothesis.confidence] ?? 'text-slate-400 border-slate-700 bg-slate-800/20';

  return (
    <div className={cn('rounded-lg border p-4 space-y-3', confidenceColor)}>
      <div className="flex items-start justify-between gap-3">
        <span className="text-[10px] font-bold opacity-60">HYPOTHESIS {index}</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] opacity-70">Confidence:</span>
          <Badge variant="warning" size="sm">{hypothesis.confidence}</Badge>
        </div>
      </div>
      <p className="text-sm text-[#E5EDF9] leading-relaxed font-medium">{hypothesis.hypothesis}</p>
      <p className="text-xs opacity-70 leading-relaxed">
        Supporting evidence: {hypothesis.supporting_evidence}
      </p>
      <p className="text-[10px] text-[#8B9BB4] flex items-start gap-1">
        <Info className="h-3 w-3 shrink-0 mt-0.5" />
        This is an AI hypothesis. Verify against your data pipeline before acting.
      </p>
    </div>
  );
}

function ActionChecklist({ actions }: { actions: string[] }) {
  const [checked, setChecked] = useState<Set<number>>(new Set());

  function toggle(i: number) {
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  }

  return (
    <div className="space-y-2">
      {actions.map((action, i) => (
        <button
          key={i}
          onClick={() => toggle(i)}
          className="w-full flex items-start gap-3 rounded-lg border border-[#223149] bg-[#142036] p-3 text-left hover:border-[#2d4a6e] transition-colors focus-ring"
          aria-pressed={checked.has(i)}
        >
          {checked.has(i) ? (
            <CheckSquare className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
          ) : (
            <Square className="h-4 w-4 text-[#8B9BB4] shrink-0 mt-0.5" />
          )}
          <span className={cn(
            'text-sm leading-relaxed',
            checked.has(i) ? 'text-[#8B9BB4] line-through' : 'text-[#E5EDF9]',
          )}>
            {action}
          </span>
        </button>
      ))}
      {checked.size > 0 && (
        <p className="text-[10px] text-[#8B9BB4] flex items-center gap-1 pt-1">
          <Info className="h-3 w-3" />
          Checkboxes record local review state only. No remediation has been executed.
        </p>
      )}
    </div>
  );
}

function LimitRow({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-[#223149] bg-[#142036] p-3">
      <Info className="h-4 w-4 text-[#8B9BB4] shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-medium text-[#E5EDF9]">{title}</p>
        <p className="text-xs text-[#8B9BB4] mt-0.5 leading-relaxed">{detail}</p>
      </div>
    </div>
  );
}

function AIUnavailablePlaceholder() {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-[#223149] bg-[#142036] p-4">
      <AlertTriangle className="h-4 w-4 text-[#8B9BB4] shrink-0" />
      <p className="text-sm text-[#8B9BB4]">
        AI reasoning is unavailable for this report. Python analysis results in Section A are unaffected.
      </p>
    </div>
  );
}

// Avoid unused import warning
void formatNumber;

