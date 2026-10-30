// ============================================================
// Topbar – page title, backend status, quick actions
// ============================================================

import { useContext } from 'react';
import { Plus, RefreshCw, Wifi, WifiOff, Loader } from 'lucide-react';
import { AppContext } from '../../App';
import type { Page } from '../../App';
import { Button } from '../ui/Button';
import { cn } from '../../lib/utils';

const PAGE_LABELS: Record<Page, { title: string; breadcrumb: string[] }> = {
  overview:      { title: 'Overview',           breadcrumb: ['DataSentinel AI', 'Overview'] },
  pipeline:      { title: 'Pipeline Monitor',   breadcrumb: ['DataSentinel AI', 'Pipeline Monitor'] },
  analysis:      { title: 'Dataset Analysis',   breadcrumb: ['DataSentinel AI', 'Dataset Analysis'] },
  anomalies:     { title: 'Anomaly Explorer',   breadcrumb: ['DataSentinel AI', 'Anomaly Explorer'] },
  investigation: { title: 'AI Investigation',   breadcrumb: ['DataSentinel AI', 'AI Investigation'] },
  reports:       { title: 'Reports & Audit Logs', breadcrumb: ['DataSentinel AI', 'Reports & Audit Logs'] },
  settings:      { title: 'Settings',           breadcrumb: ['DataSentinel AI', 'Settings'] },
};

interface TopbarProps {
  onRefresh?: () => void;
  refreshing?: boolean;
}

export function Topbar({ onRefresh, refreshing = false }: TopbarProps) {
  const { currentPage, navigate, backendStatus, latestReport } = useContext(AppContext);
  const meta = PAGE_LABELS[currentPage];

  return (
    <header className="sticky top-0 z-20 bg-[#080D18]/90 backdrop-blur-sm border-b border-[#223149] flex items-center gap-4 px-6 h-14 shrink-0">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs text-[#8B9BB4] min-w-0">
        {meta.breadcrumb.map((crumb, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <span className="opacity-40">/</span>}
            <span className={cn(
              'truncate',
              i === meta.breadcrumb.length - 1 ? 'text-[#E5EDF9] font-medium' : '',
            )}>
              {crumb}
            </span>
          </span>
        ))}
      </div>

      {/* Analysis status pill */}
      {latestReport && currentPage !== 'analysis' && (
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded border text-[10px] font-medium tracking-wide border-[#223149] bg-[#101A2B]">
          <span className={cn(
            'h-1.5 w-1.5 rounded-full',
            latestReport.overall_status === 'critical' ? 'bg-red-400' :
            latestReport.overall_status === 'warning'  ? 'bg-amber-400' : 'bg-emerald-400',
          )} />
          <span className="text-[#8B9BB4]">Last analysis:</span>
          <span className={cn(
            latestReport.overall_status === 'critical' ? 'text-red-400' :
            latestReport.overall_status === 'warning'  ? 'text-amber-400' : 'text-emerald-400',
          )}>
            {latestReport.overall_status.toUpperCase()}
          </span>
        </div>
      )}

      <div className="ml-auto flex items-center gap-2">
        {/* Backend status indicator */}
        <BackendIndicator status={backendStatus} />

        {/* Refresh */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Refresh"
            className="flex h-8 w-8 items-center justify-center rounded text-[#8B9BB4] hover:text-[#E5EDF9] hover:bg-[#142036] transition-colors focus-ring disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
          </button>
        )}

        {/* New analysis */}
        <Button
          variant="primary"
          size="sm"
          icon={<Plus className="h-3.5 w-3.5" />}
          onClick={() => navigate('analysis')}
          aria-label="Start new analysis"
        >
          <span className="hidden sm:inline">New Analysis</span>
        </Button>
      </div>
    </header>
  );
}

function BackendIndicator({ status }: { status: 'checking' | 'online' | 'offline' }) {
  const config = {
    checking: {
      icon: <Loader className="h-3 w-3 animate-spin" />,
      label: 'Checking',
      className: 'text-[#8B9BB4] border-[#223149]',
    },
    online: {
      icon: <Wifi className="h-3 w-3" />,
      label: 'API Online',
      className: 'text-emerald-400 border-emerald-900/50 bg-emerald-950/30',
    },
    offline: {
      icon: <WifiOff className="h-3 w-3" />,
      label: 'API Offline',
      className: 'text-red-400 border-red-900/50 bg-red-950/30',
    },
  }[status];

  return (
    <div
      className={cn(
        'hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] font-medium',
        config.className,
      )}
      aria-label={`Backend status: ${config.label}`}
      title={`Backend status: ${config.label}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </div>
  );
}

