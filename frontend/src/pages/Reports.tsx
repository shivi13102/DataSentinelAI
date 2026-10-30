// ============================================================
// Reports & Audit Logs – View and export saved analysis reports
// ============================================================

import { useContext, useState, useMemo } from 'react';
import {
  FileText,
  Download,
  Search,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';

import { AppContext } from '../App';
import type { ReportSummary } from '../types/api';
import { fetchReport, downloadReportBlob } from '../lib/api';
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card';
import { StatusBadge, ProtectionBadge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import {
  formatTimestamp,
  formatRelativeTime,
  triggerDownload,
  cn,
} from '../lib/utils';

export function Reports() {
  const { reports, refreshReports, setLatestReport, navigate, toast } =
    useContext(AppContext);

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [decisionFilter, setDecisionFilter] = useState<string>('all');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [loadingReportId, setLoadingReportId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // ── Filters & Search ───────────────────────────────────────
  const filteredReports = useMemo(() => {
    let result = [...reports];

    if (statusFilter !== 'all') {
      result = result.filter(r => r.overall_status.toLowerCase() === statusFilter.toLowerCase());
    }

    if (decisionFilter !== 'all') {
      result = result.filter(
        r => r.protection_decision.toUpperCase() === decisionFilter.toUpperCase(),
      );
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        r =>
          r.report_id.toLowerCase().includes(q) ||
          (r.baseline_filename ?? '').toLowerCase().includes(q) ||
          (r.current_filename ?? '').toLowerCase().includes(q) ||
          r.overall_status.toLowerCase().includes(q) ||
          r.protection_decision.toLowerCase().includes(q),
      );
    }

    result.sort((a, b) => {
      const timeA = a.generated_at ? new Date(a.generated_at).getTime() : 0;
      const timeB = b.generated_at ? new Date(b.generated_at).getTime() : 0;
      return sortOrder === 'desc' ? timeB - timeA : timeA - timeB;
    });

    return result;
  }, [reports, statusFilter, decisionFilter, searchQuery, sortOrder]);

  // ── Actions ────────────────────────────────────────────────
  async function handleRefresh() {
    setIsRefreshing(true);
    try {
      await refreshReports();
      toast('Reports refreshed', 'success');
    } catch {
      toast('Failed to refresh reports from backend', 'error');
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleLoadReport(reportSummary: ReportSummary) {
    setLoadingReportId(reportSummary.report_id);
    try {
      const fullReport = await fetchReport(reportSummary.report_id);
      setLatestReport(fullReport);
      toast(`Loaded report ${reportSummary.report_id.slice(-8)} into workspace`, 'success');
      navigate('overview');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load report';
      toast(msg, 'error');
    } finally {
      setLoadingReportId(null);
    }
  }

  async function handleDownloadReport(reportId: string) {
    setDownloadingId(reportId);
    try {
      const blob = await downloadReportBlob(reportId);
      triggerDownload(blob, `datasentinel_report_${reportId}.json`);
      toast(`Downloaded datasentinel_report_${reportId}.json`, 'success');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Download failed';
      toast(msg, 'error');
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#E5EDF9] tracking-tight">
            Reports & Audit Logs
          </h1>
          <p className="text-sm text-[#8B9BB4] mt-0.5">
            Immutable JSON audit ledger of all dataset investigations and protection decisions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin')} />}
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
          >
            Refresh Logs
          </Button>
          <Button variant="primary" size="sm" onClick={() => navigate('analysis')}>
            New Analysis
          </Button>
        </div>
      </div>

      {/* Filter and Search Controls */}
      <Card>
        <CardBody className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8B9BB4]" />
            <input
              type="text"
              placeholder="Search by Report ID, filenames, or status…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-[#142036] border border-[#223149] rounded pl-9 pr-3 py-1.5 text-sm text-[#E5EDF9] placeholder-[#8B9BB4] focus:outline-none focus:border-cyan-700/60 focus-ring"
            />
          </div>

          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="bg-[#142036] border border-[#223149] rounded px-3 py-1.5 text-sm text-[#E5EDF9] focus:outline-none focus:border-cyan-700/60 focus-ring"
            aria-label="Filter by overall status"
          >
            <option value="all">All Statuses</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="healthy">Healthy</option>
          </select>

          <select
            value={decisionFilter}
            onChange={e => setDecisionFilter(e.target.value)}
            className="bg-[#142036] border border-[#223149] rounded px-3 py-1.5 text-sm text-[#E5EDF9] focus:outline-none focus:border-cyan-700/60 focus-ring"
            aria-label="Filter by protection decision"
          >
            <option value="all">All Decisions</option>
            <option value="BLOCK">BLOCK</option>
            <option value="REVIEW_REQUIRED">REVIEW REQUIRED</option>
            <option value="ALLOW">ALLOW</option>
          </select>

          <select
            value={sortOrder}
            onChange={e => setSortOrder(e.target.value as 'desc' | 'asc')}
            className="bg-[#142036] border border-[#223149] rounded px-3 py-1.5 text-sm text-[#E5EDF9] focus:outline-none focus:border-cyan-700/60 focus-ring"
            aria-label="Sort order"
          >
            <option value="desc">Newest First</option>
            <option value="asc">Oldest First</option>
          </select>
        </CardBody>
      </Card>

      {/* Reports Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-[#22D3EE]" />
            <CardTitle>Audit Trail Registry</CardTitle>
          </div>
          <span className="text-xs text-[#8B9BB4]">
            Showing {filteredReports.length} of {reports.length} report{reports.length === 1 ? '' : 's'}
          </span>
        </CardHeader>

        {filteredReports.length === 0 ? (
          <EmptyState
            icon={<FileText className="h-6 w-6" />}
            title="No reports match your filters"
            description={
              reports.length === 0
                ? 'No saved analyses were found in the backend reports directory.'
                : 'Try adjusting your search query or reset your filters.'
            }
            action={
              reports.length === 0 ? (
                <Button variant="primary" size="sm" onClick={() => navigate('analysis')}>
                  Create First Report
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#223149]">
                  <th className="px-5 py-3 text-left text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider">
                    Report ID
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider">
                    Generated At
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider">
                    Overall Status
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider">
                    Findings
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider">
                    Protection Decision
                  </th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider">
                    Datasets (Baseline / Current)
                  </th>
                  <th className="px-5 py-3 text-right text-[11px] font-semibold text-[#8B9BB4] uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1a2d45]">
                {filteredReports.map(report => (
                  <tr
                    key={report.report_id}
                    className="hover:bg-[#142036] transition-colors group"
                  >
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-[#22D3EE]">
                          {report.report_id}
                        </span>
                      </div>
                    </td>

                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="text-xs text-[#E5EDF9]">
                          {report.generated_at ? formatTimestamp(report.generated_at) : '—'}
                        </span>
                        {report.generated_at && (
                          <span className="text-[10px] text-[#8B9BB4]">
                            {formatRelativeTime(report.generated_at)}
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <StatusBadge status={report.overall_status} />
                    </td>

                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <span className="text-xs font-mono font-medium text-[#E5EDF9]">
                        {report.finding_count} detected
                      </span>
                    </td>

                    <td className="px-4 py-3.5 whitespace-nowrap">
                      <ProtectionBadge decision={report.protection_decision} />
                    </td>

                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5 text-xs text-[#8B9BB4] font-mono">
                        <span className="text-[#60A5FA] truncate max-w-[120px]">
                          {report.baseline_filename ?? 'baseline.csv'}
                        </span>
                        <span>/</span>
                        <span className="text-[#E5EDF9] truncate max-w-[120px]">
                          {report.current_filename ?? 'current.csv'}
                        </span>
                      </div>
                    </td>

                    <td className="px-5 py-3.5 whitespace-nowrap text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={<ExternalLink className="h-3 w-3" />}
                          onClick={() => void handleLoadReport(report)}
                          loading={loadingReportId === report.report_id}
                          title="Load this report into active workspace"
                        >
                          Inspect
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={<Download className="h-3.5 w-3.5" />}
                          onClick={() => void handleDownloadReport(report.report_id)}
                          loading={downloadingId === report.report_id}
                          title="Download JSON report"
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
