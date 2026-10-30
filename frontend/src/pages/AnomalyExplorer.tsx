// ============================================================
// Anomaly Explorer – filterable findings table with evidence drawer
// ============================================================

import { useContext, useMemo, useState } from 'react';
import { Search, X, ChevronRight, Info } from 'lucide-react';

import { AppContext } from '../App';
import type { Finding } from '../types/api';
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card';
import { Badge, SeverityBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import {
  cn,
  formatNumber,
  formatPercent,
  formatPValue,
  getFindingTypeLabel,
  getSeverityLabel,
} from '../lib/utils';

const SEVERITY_ORDER: Record<string, number> = { high: 0, critical: 1, medium: 2, low: 3 };

export function AnomalyExplorer() {
  const { latestReport, navigate } = useContext(AppContext);

  const [searchQuery, setSearchQuery] = useState('');
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [sortField, setSortField] = useState<'severity' | 'type'>('severity');
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  const findings = latestReport?.analysis.findings ?? [];

  const findingTypes = useMemo(
    () => Array.from(new Set(findings.map(f => f.type))),
    [findings],
  );

  const filtered = useMemo(() => {
    let result = [...findings];

    if (filterSeverity !== 'all') {
      result = result.filter(f => f.severity === filterSeverity);
    }
    if (filterType !== 'all') {
      result = result.filter(f => f.type === filterType);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(f =>
        (f.column ?? '').toLowerCase().includes(q) ||
        getFindingTypeLabel(f.type).toLowerCase().includes(q) ||
        f.description.toLowerCase().includes(q),
      );
    }

    result.sort((a, b) => {
      if (sortField === 'severity') {
        return (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9);
      }
      return a.type.localeCompare(b.type);
    });

    return result;
  }, [findings, filterSeverity, filterType, searchQuery, sortField]);

  const hasFilters =
    filterSeverity !== 'all' || filterType !== 'all' || searchQuery !== '';

  return (
    <div className="p-6 space-y-5 max-w-[1400px] mx-auto">

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#E5EDF9] tracking-tight">Anomaly Explorer</h1>
          <p className="text-sm text-[#8B9BB4] mt-0.5">
            Inspect and filter data-quality findings from the latest analysis.
          </p>
        </div>
        {findings.length > 0 && (
          <Badge variant="neutral" size="md">
            {findings.length} finding{findings.length !== 1 ? 's' : ''} detected
          </Badge>
        )}
      </div>

      {/* No analysis state */}
      {!latestReport && (
        <Card>
          <EmptyState
            icon={<Search className="h-5 w-5" />}
            title="No analysis results"
            description="Upload a baseline and current CSV to detect anomalies."
            action={
              <Button variant="primary" size="sm" onClick={() => navigate('analysis')}>
                Analyse Datasets
              </Button>
            }
          />
        </Card>
      )}

      {latestReport && (
        <div className="flex gap-4">

          {/* Table side */}
          <div className="flex-1 min-w-0 space-y-4">

            {/* Filters */}
            <Card>
              <CardBody className="flex flex-wrap gap-3">
                {/* Search */}
                <div className="relative flex-1 min-w-[180px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8B9BB4]" />
                  <input
                    type="text"
                    placeholder="Search findings…"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="w-full bg-[#142036] border border-[#223149] rounded pl-8 pr-3 py-1.5 text-sm text-[#E5EDF9] placeholder-[#8B9BB4] focus:outline-none focus:border-cyan-700/60 focus-ring"
                  />
                </div>

                {/* Severity filter */}
                <select
                  value={filterSeverity}
                  onChange={e => setFilterSeverity(e.target.value)}
                  className="bg-[#142036] border border-[#223149] rounded px-3 py-1.5 text-sm text-[#E5EDF9] focus:outline-none focus:border-cyan-700/60 focus-ring"
                  aria-label="Filter by severity"
                >
                  <option value="all">All severities</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>

                {/* Type filter */}
                <select
                  value={filterType}
                  onChange={e => setFilterType(e.target.value)}
                  className="bg-[#142036] border border-[#223149] rounded px-3 py-1.5 text-sm text-[#E5EDF9] focus:outline-none focus:border-cyan-700/60 focus-ring"
                  aria-label="Filter by anomaly type"
                >
                  <option value="all">All types</option>
                  {findingTypes.map(t => (
                    <option key={t} value={t}>{getFindingTypeLabel(t)}</option>
                  ))}
                </select>

                {/* Sort */}
                <select
                  value={sortField}
                  onChange={e => setSortField(e.target.value as 'severity' | 'type')}
                  className="bg-[#142036] border border-[#223149] rounded px-3 py-1.5 text-sm text-[#E5EDF9] focus:outline-none focus:border-cyan-700/60 focus-ring"
                  aria-label="Sort findings"
                >
                  <option value="severity">Sort: Severity</option>
                  <option value="type">Sort: Type</option>
                </select>

                {/* Reset */}
                {hasFilters && (
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<X className="h-3.5 w-3.5" />}
                    onClick={() => {
                      setSearchQuery('');
                      setFilterSeverity('all');
                      setFilterType('all');
                    }}
                  >
                    Reset
                  </Button>
                )}
              </CardBody>
            </Card>

            {/* Table */}
            <Card>
              <CardHeader>
                <CardTitle>Findings</CardTitle>
                <span className="text-xs text-[#8B9BB4]">
                  {filtered.length} of {findings.length}
                </span>
              </CardHeader>

              {filtered.length === 0 ? (
                <EmptyState
                  title="No matching findings"
                  description="Try adjusting or resetting your filters."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#223149]">
                        {['Severity', 'Type', 'Column', 'Baseline', 'Current', 'Method', ''].map(h => (
                          <th
                            key={h}
                            className="px-4 py-2.5 text-left text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider whitespace-nowrap"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1a2d45]">
                      {filtered.map((f, i) => (
                        <tr
                          key={i}
                          onClick={() => setSelectedFinding(f === selectedFinding ? null : f)}
                          className={cn(
                            'cursor-pointer transition-colors hover:bg-[#142036]',
                            f === selectedFinding && 'bg-cyan-950/20',
                          )}
                        >
                          <td className="px-4 py-3 whitespace-nowrap">
                            <SeverityBadge severity={f.severity} />
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="text-xs text-[#E5EDF9]">
                              {getFindingTypeLabel(f.type)}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="font-mono text-xs text-[#60A5FA]">
                              {f.column ?? '—'}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <FindingValueCell finding={f} side="baseline" />
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <FindingValueCell finding={f} side="current" />
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-[11px] text-[#8B9BB4]">
                              {f.detection_method.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <ChevronRight className={cn(
                              'h-3.5 w-3.5 transition-transform',
                              f === selectedFinding ? 'text-cyan-400 rotate-90' : 'text-[#8B9BB4]',
                            )} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>

          {/* Evidence drawer */}
          {selectedFinding && (
            <div className="w-[360px] shrink-0">
              <EvidenceDrawer
                finding={selectedFinding}
                hypotheses={latestReport?.ai_reasoning?.explanation?.root_cause_hypotheses ?? []}
                allFindings={findings}
                onClose={() => setSelectedFinding(null)}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Evidence drawer ───────────────────────────────────────────

interface EvidenceDrawerProps {
  finding: Finding;
  hypotheses: Array<{ hypothesis: string; supporting_evidence: string; confidence: string }>;
  allFindings: Finding[];
  onClose: () => void;
}

function EvidenceDrawer({ finding, hypotheses, allFindings, onClose }: EvidenceDrawerProps) {
  // Find the hypothesis that corresponds to this finding's index
  const findingIdx = allFindings.indexOf(finding);
  const relatedHypothesis = hypotheses[findingIdx];

  return (
    <div className="drawer-slide-in sticky top-4">
      <Card elevated>
        <CardHeader>
          <CardTitle>Evidence Detail</CardTitle>
          <button
            onClick={onClose}
            aria-label="Close evidence panel"
            className="text-[#8B9BB4] hover:text-[#E5EDF9] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </CardHeader>
        <div className="p-5 space-y-5 overflow-y-auto max-h-[calc(100vh-200px)]">

          {/* Finding meta */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <SeverityBadge severity={finding.severity} />
              <Badge variant="info">{getFindingTypeLabel(finding.type)}</Badge>
            </div>
            {finding.column && (
              <p className="text-xs text-[#8B9BB4]">
                Column: <span className="font-mono text-[#60A5FA]">{finding.column}</span>
              </p>
            )}
            <p className="text-sm text-[#E5EDF9] leading-relaxed">{finding.description}</p>
          </div>

          <Divider />

          {/* Finding-specific evidence */}
          <FindingEvidence finding={finding} />

          {/* AI hypothesis */}
          {relatedHypothesis && (
            <>
              <Divider />
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-[#8B9BB4] uppercase tracking-wide">
                    AI Hypothesis
                  </p>
                  <Badge variant="warning" size="sm">Unverified</Badge>
                </div>
                <div className="rounded bg-amber-950/20 border border-amber-900/30 p-3 space-y-2">
                  <p className="text-xs text-[#E5EDF9] leading-relaxed">{relatedHypothesis.hypothesis}</p>
                  <p className="text-[11px] text-[#8B9BB4]">
                    Evidence: {relatedHypothesis.supporting_evidence}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-[#8B9BB4]">Confidence:</span>
                    <ConfidenceBar confidence={relatedHypothesis.confidence} />
                  </div>
                </div>
                <p className="text-[10px] text-[#8B9BB4] flex items-start gap-1">
                  <Info className="h-3 w-3 shrink-0 mt-0.5" />
                  AI hypotheses require verification. They are not confirmed root causes.
                </p>
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── Finding-type-specific evidence ────────────────────────────

function FindingEvidence({ finding }: { finding: Finding }) {
  if (finding.type === 'missing_value_anomaly') {
    const bv = finding.baseline_value as Record<string, number>;
    const cv = finding.current_value as Record<string, number>;
    return (
      <EvidenceTable rows={[
        { label: 'Baseline missing', value: `${bv.missing_count?.toLocaleString() ?? '—'} rows (${formatPercent(bv.missing_percentage ?? 0)})` },
        { label: 'Current missing', value: `${cv.missing_count?.toLocaleString() ?? '—'} rows (${formatPercent(cv.missing_percentage ?? 0)})`, highlight: true },
        { label: 'Increase', value: finding.change_percentage_points != null ? `+${formatPercent(finding.change_percentage_points)} pp` : '—', highlight: true },
        { label: 'Detection method', value: finding.detection_method.replace(/_/g, ' ') },
      ]} />
    );
  }

  if (finding.type === 'duplicate_anomaly') {
    const bv = finding.baseline_value as Record<string, number>;
    const cv = finding.current_value as Record<string, number>;
    return (
      <div className="space-y-3">
        <EvidenceTable rows={[
          { label: 'Baseline duplicates', value: `${bv.duplicate_count?.toLocaleString() ?? '—'} (${formatPercent(bv.duplicate_percentage ?? 0)})` },
          { label: 'Current duplicates', value: `${cv.duplicate_count?.toLocaleString() ?? '—'} (${formatPercent(cv.duplicate_percentage ?? 0)})`, highlight: true },
          { label: 'Increase', value: finding.change_percentage_points != null ? `+${formatPercent(finding.change_percentage_points)} pp` : '—', highlight: true },
          { label: 'Detection method', value: finding.detection_method.replace(/_/g, ' ') },
        ]} />
        {finding.compared_columns && (
          <div>
            <p className="text-xs text-[#8B9BB4] mb-1">Compared columns:</p>
            <div className="flex flex-wrap gap-1">
              {finding.compared_columns.map(c => (
                <span key={c} className="font-mono text-[10px] bg-[#142036] border border-[#223149] rounded px-1.5 py-0.5 text-[#60A5FA]">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (finding.type === 'distribution_drift') {
    const bv = finding.baseline_value as Record<string, number>;
    const cv = finding.current_value as Record<string, number>;
    return (
      <EvidenceTable rows={[
        { label: 'Baseline mean', value: formatNumber(bv.mean ?? 0) },
        { label: 'Current mean', value: formatNumber(cv.mean ?? 0), highlight: true },
        { label: 'Baseline std', value: formatNumber(bv.std ?? 0) },
        { label: 'Current std', value: formatNumber(cv.std ?? 0) },
        { label: 'Relative mean change', value: finding.relative_mean_change != null ? `${(finding.relative_mean_change * 100).toFixed(1)}%` : '—', highlight: true },
        { label: 'KS statistic', value: finding.ks_statistic != null ? formatNumber(finding.ks_statistic, 4) : '—' },
        { label: 'KS p-value', value: finding.ks_p_value != null ? formatPValue(finding.ks_p_value) : '—' },
        { label: 'Significance level α', value: finding.alpha != null ? String(finding.alpha) : '—' },
        { label: 'Detection method', value: finding.detection_method.replace(/_/g, ' ') },
      ]} />
    );
  }

  if (finding.type === 'categorical_drift') {
    const bv = finding.baseline_value as Record<string, Record<string, number>>;
    const cv = finding.current_value as Record<string, Record<string, number>>;
    return (
      <div className="space-y-3">
        <EvidenceTable rows={[
          { label: 'TVD', value: finding.total_variation_distance != null ? formatNumber(finding.total_variation_distance, 4) : '—', highlight: true },
          { label: 'χ² statistic', value: finding.chi2_statistic != null ? formatNumber(finding.chi2_statistic, 4) : '—' },
          { label: 'p-value', value: finding.p_value != null ? formatPValue(finding.p_value) : '—' },
          { label: 'Significance level α', value: finding.alpha != null ? String(finding.alpha) : '—' },
          { label: 'Detection method', value: finding.detection_method.replace(/_/g, ' ') },
        ]} />

        {finding.new_categories && finding.new_categories.length > 0 && (
          <div>
            <p className="text-xs text-[#8B9BB4] mb-1">New categories:</p>
            <div className="flex flex-wrap gap-1">
              {finding.new_categories.map(c => (
                <span key={c} className="font-mono text-[10px] bg-red-950/30 border border-red-900/30 rounded px-1.5 py-0.5 text-red-400">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        {finding.removed_categories && finding.removed_categories.length > 0 && (
          <div>
            <p className="text-xs text-[#8B9BB4] mb-1">Removed categories:</p>
            <div className="flex flex-wrap gap-1">
              {finding.removed_categories.map(c => (
                <span key={c} className="font-mono text-[10px] bg-amber-950/30 border border-amber-900/30 rounded px-1.5 py-0.5 text-amber-400">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        {bv.counts && cv.counts && (
          <div>
            <p className="text-xs text-[#8B9BB4] mb-2">Category counts:</p>
            <div className="space-y-1">
              {Object.keys({ ...bv.counts, ...cv.counts }).sort().map(cat => (
                <div key={cat} className="flex items-center justify-between text-xs">
                  <span className="font-mono text-[#60A5FA] truncate mr-2">{cat}</span>
                  <span className="text-[#8B9BB4] shrink-0">
                    {bv.counts?.[cat] ?? 0} → {cv.counts?.[cat] ?? 0}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Generic fallback
  return (
    <EvidenceTable rows={[
      { label: 'Description', value: finding.description },
      { label: 'Detection method', value: finding.detection_method.replace(/_/g, ' ') },
      { label: 'Severity', value: getSeverityLabel(finding.severity) },
    ]} />
  );
}

// ── Evidence table ────────────────────────────────────────────

interface EvidenceRow {
  label: string;
  value: string;
  highlight?: boolean;
}

function EvidenceTable({ rows }: { rows: EvidenceRow[] }) {
  return (
    <div className="space-y-1">
      {rows.map((r, i) => (
        <div key={i} className="flex items-start justify-between gap-3 py-1.5 border-b border-[#1a2d45] last:border-0">
          <span className="text-xs text-[#8B9BB4] shrink-0">{r.label}</span>
          <span className={cn(
            'text-xs text-right',
            r.highlight ? 'text-[#E5EDF9] font-medium' : 'text-[#E5EDF9]',
          )}>
            {r.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Confidence bar ────────────────────────────────────────────

function ConfidenceBar({ confidence }: { confidence: string }) {
  const pct = confidence === 'high' ? 85 : confidence === 'medium' ? 55 : 25;
  const color = confidence === 'high' ? 'bg-amber-400' : confidence === 'medium' ? 'bg-amber-600' : 'bg-slate-500';

  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="flex-1 h-1.5 bg-[#1a2d45] rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full confidence-bar-fill', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] text-[#8B9BB4] capitalize">{confidence}</span>
    </div>
  );
}

function Divider() {
  return <div className="border-t border-[#223149]" />;
}

function FindingValueCell({ finding, side }: { finding: Finding; side: 'baseline' | 'current' }) {
  const val = side === 'baseline' ? finding.baseline_value : finding.current_value;

  if (!val || typeof val !== 'object') return <span className="text-xs text-[#8B9BB4]">—</span>;

  const v = val as Record<string, unknown>;

  if (typeof v.missing_percentage === 'number') {
    return <span className="text-xs text-[#E5EDF9]">{formatPercent(v.missing_percentage as number)}</span>;
  }
  if (typeof v.duplicate_percentage === 'number') {
    return <span className="text-xs text-[#E5EDF9]">{formatPercent(v.duplicate_percentage as number)}</span>;
  }
  if (typeof v.mean === 'number') {
    return <span className="text-xs text-[#E5EDF9]">μ {formatNumber(v.mean as number)}</span>;
  }
  if (typeof v.sample_count === 'number' && v.counts) {
    return <span className="text-xs text-[#8B9BB4]">{(v.sample_count as number).toLocaleString()} samples</span>;
  }

  return <span className="text-xs text-[#8B9BB4]">—</span>;
}

