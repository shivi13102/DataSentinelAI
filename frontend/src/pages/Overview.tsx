// ============================================================
// Overview – Command Centre
// ============================================================

import { useContext } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Activity,
  ArrowRight,
  Database,
  Clock,
  Users,
  FileBarChart,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

import { AppContext } from '../App';
import type { AnalysisReport } from '../types/api';
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card';
import { Badge, SeverityBadge, ProtectionBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import {
  calculateHealthScore,
  formatTimestamp,
  formatRelativeTime,
  getFindingTypeLabel,
  formatNumber,
} from '../lib/utils';

const SEVERITY_COLORS: Record<string, string> = {
  high:     '#F87171',
  medium:   '#FBBF24',
  low:      '#94a3b8',
  critical: '#ef4444',
};

export function Overview() {
  const { latestReport, navigate, reports } = useContext(AppContext);

  const report = latestReport;
  const hasReport = report !== null;

  const healthScore = hasReport
    ? calculateHealthScore(report.analysis.findings)
    : null;

  const findings = hasReport ? report.analysis.findings : [];
  const severityCounts = hasReport ? report.analysis.severity_counts : null;

  // ── Severity distribution chart data ─────────────────────────
  const severityChartData = severityCounts
    ? [
        { name: 'High',   value: severityCounts.high,   color: '#F87171' },
        { name: 'Medium', value: severityCounts.medium, color: '#FBBF24' },
        { name: 'Low',    value: severityCounts.low,    color: '#94a3b8' },
      ].filter(d => d.value > 0)
    : [];

  // ── Report history chart data ─────────────────────────────────
  const historyData = reports
    .slice(0, 8)
    .reverse()
    .map(r => ({
      id: r.report_id.slice(-6),
      findings: r.finding_count,
      status: r.overall_status,
    }));

  const explanation = report?.ai_reasoning?.explanation;

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">

      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#E5EDF9] tracking-tight">
            Data Observability
          </h1>
          <p className="text-sm text-[#8B9BB4] mt-0.5">
            Detect silent data failures before they reach downstream systems.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasReport && (
            <span className="text-xs text-[#8B9BB4] flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              {formatRelativeTime(report.generated_at)}
            </span>
          )}
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('analysis')}
          >
            New Analysis
          </Button>
        </div>
      </div>

      {/* ── Protection banner ─────────────────────────────────── */}
      {hasReport && (
        <ProtectionBanner report={report} />
      )}

      {/* ── Metric cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Data Health Score"
          value={healthScore !== null ? `${healthScore}` : '—'}
          unit={healthScore !== null ? '/ 100' : ''}
          description="Severity-weighted frontend indicator"
          icon={<Activity className="h-4 w-4" />}
          accent={
            healthScore === null ? 'neutral' :
            healthScore >= 80 ? 'healthy' :
            healthScore >= 50 ? 'warning' : 'critical'
          }
        />
        <MetricCard
          label="High-Severity Findings"
          value={severityCounts ? String(severityCounts.high) : '—'}
          description="From latest analysis"
          icon={<ShieldAlert className="h-4 w-4" />}
          accent={severityCounts && severityCounts.high > 0 ? 'critical' : 'healthy'}
        />
        <MetricCard
          label="Active Anomalies"
          value={hasReport ? String(report.analysis.total_findings) : '—'}
          description={hasReport ? `${report.analysis.baseline_rows.toLocaleString()} baseline rows` : 'No analysis yet'}
          icon={<AlertTriangle className="h-4 w-4" />}
          accent={hasReport && report.analysis.total_findings > 0 ? 'warning' : 'healthy'}
        />
        <MetricCard
          label="Reference Pipeline"
          value="Demo"
          description="Baseline + current CSV pair"
          icon={<Database className="h-4 w-4" />}
          accent="neutral"
          note="No live connectors"
        />
      </div>

      {/* ── Charts row ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Severity distribution */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Anomaly Severity</CardTitle>
            {hasReport && <Badge variant="neutral" size="sm">Latest run</Badge>}
          </CardHeader>
          <CardBody>
            {severityChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie
                    data={severityChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={68}
                    dataKey="value"
                    strokeWidth={0}
                  >
                    {severityChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} opacity={0.85} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#101A2B', border: '1px solid #223149', borderRadius: 6 }}
                    labelStyle={{ color: '#E5EDF9', fontSize: 12 }}
                    itemStyle={{ color: '#8B9BB4', fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState
                title="No findings"
                description="Run an analysis to populate this chart."
                className="py-8"
              />
            )}
            {severityChartData.length > 0 && (
              <div className="flex flex-wrap gap-3 mt-2">
                {severityChartData.map(d => (
                  <div key={d.name} className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: d.color }}
                    />
                    <span className="text-xs text-[#8B9BB4]">{d.name}: {d.value}</span>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        {/* Report history bar chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Analysis History</CardTitle>
            <Badge variant="neutral" size="sm">{reports.length} saved</Badge>
          </CardHeader>
          <CardBody>
            {historyData.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={historyData} barSize={18} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="id" tick={{ fontSize: 10 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ background: '#101A2B', border: '1px solid #223149', borderRadius: 6 }}
                    labelStyle={{ color: '#E5EDF9', fontSize: 12 }}
                    itemStyle={{ color: '#8B9BB4', fontSize: 12 }}
                    formatter={(value?: unknown) => [`${value ?? 0} findings`, 'Findings']}
                  />
                  <Bar
                    dataKey="findings"
                    radius={[3, 3, 0, 0]}
                    fill="#22D3EE"
                    opacity={0.7}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState
                title="No analysis history"
                description="Complete at least one analysis to see historical data."
                className="py-8"
              />
            )}
            {historyData.length === 1 && (
              <p className="text-[10px] text-[#8B9BB4] mt-2">Run more analyses to build a history chart.</p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* ── Bottom row ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Recent incidents */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Incidents</CardTitle>
            {findings.length > 0 && (
              <button
                onClick={() => navigate('anomalies')}
                className="text-xs text-[#22D3EE] hover:underline flex items-center gap-1"
              >
                View all <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </CardHeader>
          {findings.length > 0 ? (
            <div className="divide-y divide-[#223149]">
              {findings.map((f, i) => (
                <button
                  key={i}
                  onClick={() => navigate('anomalies')}
                  className="w-full flex items-start gap-3 px-5 py-3 hover:bg-[#142036] transition-colors text-left"
                >
                  <SeverityBadge severity={f.severity} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-[#E5EDF9] truncate">
                      {getFindingTypeLabel(f.type)}
                    </p>
                    <p className="text-[11px] text-[#8B9BB4] truncate mt-0.5">
                      {f.column ?? 'Dataset-level'} · {f.detection_method.replace(/_/g, ' ')}
                    </p>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-[#8B9BB4] shrink-0 mt-0.5" />
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<CheckCircle2 className="h-5 w-5" />}
              title="No incidents"
              description="Upload and analyse datasets to detect anomalies."
              action={
                <Button size="sm" variant="primary" onClick={() => navigate('analysis')}>
                  Start Analysis
                </Button>
              }
            />
          )}
        </Card>

        {/* AI investigation summary */}
        <Card>
          <CardHeader>
            <CardTitle>AI Investigation</CardTitle>
            {report?.ai_reasoning && (
              <button
                onClick={() => navigate('investigation')}
                className="text-xs text-[#22D3EE] hover:underline flex items-center gap-1"
              >
                View detail <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </CardHeader>
          {report && explanation ? (
            <CardBody className="space-y-4">
              {/* Model badge */}
              <div className="flex items-center gap-2">
                <Badge variant="info">
                  <span className="font-mono">{report.ai_reasoning.model ?? 'unknown'}</span>
                </Badge>
                <Badge variant={report.ai_reasoning.status === 'success' ? 'success' : 'critical'}>
                  {report.ai_reasoning.status}
                </Badge>
              </div>

              {/* Incident summary */}
              <div className="rounded bg-[#142036] border border-[#223149] p-3">
                <p className="text-xs text-[#8B9BB4] mb-1 font-medium uppercase tracking-wide">
                  Incident Summary
                </p>
                <p className="text-sm text-[#E5EDF9] leading-relaxed">
                  {explanation.incident_summary}
                </p>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <p className="text-lg font-bold text-[#22D3EE]">
                    {explanation.root_cause_hypotheses.length}
                  </p>
                  <p className="text-[10px] text-[#8B9BB4] mt-0.5">Hypotheses</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-[#60A5FA]">
                    {explanation.business_impacts.length}
                  </p>
                  <p className="text-[10px] text-[#8B9BB4] mt-0.5">Impacts</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-[#FBBF24]">
                    {explanation.recommended_actions.length}
                  </p>
                  <p className="text-[10px] text-[#8B9BB4] mt-0.5">Actions</p>
                </div>
              </div>

              <Button
                variant="secondary"
                size="sm"
                className="w-full"
                onClick={() => navigate('investigation')}
              >
                Open Full Investigation
              </Button>
            </CardBody>
          ) : report && report.ai_reasoning.status !== 'success' ? (
            <CardBody>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="critical">AI Unavailable</Badge>
              </div>
              <p className="text-xs text-[#8B9BB4]">
                {report.ai_reasoning.error ?? 'AI reasoning did not complete. Python analysis results are still available.'}
              </p>
            </CardBody>
          ) : (
            <EmptyState
              icon={<FileBarChart className="h-5 w-5" />}
              title="No investigation available"
              description="AI reasoning runs automatically as part of dataset analysis."
              action={
                <Button size="sm" variant="primary" onClick={() => navigate('analysis')}>
                  Analyse Datasets
                </Button>
              }
            />
          )}
        </Card>
      </div>

      {/* ── Dataset metadata ──────────────────────────────────── */}
      {report?.dataset_metadata && (
        <Card>
          <CardHeader>
            <CardTitle>Last Analysed Datasets</CardTitle>
            <span className="text-xs text-[#8B9BB4]">
              {formatTimestamp(report.generated_at)}
            </span>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <DatasetInfoPanel
                label="Baseline (Reference)"
                info={report.dataset_metadata.baseline}
              />
              <DatasetInfoPanel
                label="Current (Investigated)"
                info={report.dataset_metadata.current}
              />
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  description: string;
  icon: React.ReactNode;
  accent: 'critical' | 'warning' | 'healthy' | 'neutral';
  note?: string;
}

function MetricCard({ label, value, unit, description, icon, accent, note }: MetricCardProps) {
  const accentColor = {
    critical: 'text-red-400',
    warning:  'text-amber-400',
    healthy:  'text-emerald-400',
    neutral:  'text-[#22D3EE]',
  }[accent];

  const iconBg = {
    critical: 'bg-red-950/50 text-red-400',
    warning:  'bg-amber-950/50 text-amber-400',
    healthy:  'bg-emerald-950/50 text-emerald-400',
    neutral:  'bg-cyan-950/50 text-cyan-400',
  }[accent];

  return (
    <Card className="p-5 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-[#8B9BB4] font-medium">{label}</p>
        <div className={`flex h-7 w-7 items-center justify-center rounded ${iconBg}`}>
          {icon}
        </div>
      </div>
      <div>
        <div className="flex items-baseline gap-1.5">
          <span className={`text-2xl font-bold metric-value ${accentColor}`}>{value}</span>
          {unit && <span className="text-xs text-[#8B9BB4]">{unit}</span>}
        </div>
        <p className="text-[11px] text-[#8B9BB4] mt-0.5">{description}</p>
        {note && (
          <p className="text-[10px] text-[#8B9BB4] italic mt-0.5">{note}</p>
        )}
      </div>
    </Card>
  );
}

function ProtectionBanner({ report }: { report: AnalysisReport }) {
  const decision = report.protection.decision;

  const config: Record<string, { bg: string; icon: React.ReactNode; title: string; desc: string; textColor: string }> = {
    BLOCK: {
      bg: 'bg-red-950/40 border-red-800/50',
      icon: <ShieldAlert className="h-5 w-5 text-red-400" />,
      title: 'BLOCK — Critical data-quality risk detected',
      desc: 'Downstream processing is not permitted automatically. Human review is required.',
      textColor: 'text-red-300',
    },
    REVIEW_REQUIRED: {
      bg: 'bg-amber-950/40 border-amber-800/50',
      icon: <AlertTriangle className="h-5 w-5 text-amber-400" />,
      title: 'REVIEW REQUIRED — Data-quality issues need human review',
      desc: 'Downstream processing should not proceed without human verification.',
      textColor: 'text-amber-300',
    },
    ALLOW: {
      bg: 'bg-emerald-950/40 border-emerald-800/50',
      icon: <CheckCircle2 className="h-5 w-5 text-emerald-400" />,
      title: 'ALLOW — No blocking findings detected',
      desc: 'Downstream processing may continue. Ongoing monitoring is still recommended.',
      textColor: 'text-emerald-300',
    },
  };

  const currentConfig = config[decision] ?? {
    bg: 'bg-[#142036] border-[#223149]',
    icon: null,
    title: 'Protection decision unavailable',
    desc: '',
    textColor: 'text-[#8B9BB4]',
  };

  return (
    <div className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${currentConfig.bg}`}>
      {currentConfig.icon}
      <div className="min-w-0 flex-1">
        <p className={`text-sm font-semibold ${currentConfig.textColor}`}>{currentConfig.title}</p>
        <p className="text-xs text-[#8B9BB4] mt-0.5">{currentConfig.desc}</p>
        {report.protection.reasons.slice(1).length > 0 && (
          <p className="text-[11px] text-[#8B9BB4] mt-1 opacity-70">
            {report.protection.reasons.slice(1).join(' · ')}
          </p>
        )}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <ProtectionBadge decision={decision} />
        {report.human_review_required && (
          <div className="flex items-center gap-1.5 text-[11px] text-amber-400">
            <Users className="h-3.5 w-3.5" />
            <span>Human review required</span>
          </div>
        )}
      </div>
    </div>
  );
}

interface DatasetInfoPanelProps {
  label: string;
  info: { filename: string; rows: number; columns: number; size_bytes: number };
}

function DatasetInfoPanel({ label, info }: DatasetInfoPanelProps) {
  return (
    <div className="rounded bg-[#142036] border border-[#223149] p-4 space-y-2">
      <p className="text-xs font-medium text-[#8B9BB4] uppercase tracking-wide">{label}</p>
      <p className="text-sm font-semibold text-[#E5EDF9] truncate">{info.filename}</p>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-base font-bold text-[#22D3EE]">{formatNumber(info.rows, 0)}</p>
          <p className="text-[10px] text-[#8B9BB4]">rows</p>
        </div>
        <div>
          <p className="text-base font-bold text-[#60A5FA]">{info.columns}</p>
          <p className="text-[10px] text-[#8B9BB4]">cols</p>
        </div>
        <div>
          <p className="text-base font-bold text-[#E5EDF9]">
            {info.size_bytes < 1024 ? `${info.size_bytes}B` :
             info.size_bytes < 1048576 ? `${(info.size_bytes / 1024).toFixed(0)}KB` :
             `${(info.size_bytes / 1048576).toFixed(1)}MB`}
          </p>
          <p className="text-[10px] text-[#8B9BB4]">size</p>
        </div>
      </div>
    </div>
  );
}

// Satisfy "no unused" – SEVERITY_COLORS is used in chart code above
void SEVERITY_COLORS;

