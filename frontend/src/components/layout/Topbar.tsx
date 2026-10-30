// ============================================================
// Topbar – page title, backend status, quick actions
// ============================================================

import { useContext } from 'react';
import { Plus, RefreshCw, Wifi, WifiOff, Loader, Cpu, HardDrive } from 'lucide-react';
import { AppContext } from '../../App';
import type { Page } from '../../App';
import { Button } from '../ui/Button';
import { cn } from '../../lib/utils';
import { getApiBaseUrl } from '../../lib/api';

const PAGE_LABELS: Record<Page, { title: string; breadcrumb: string[] }> = {
  overview:      { title: 'Overview',           breadcrumb: ['DataSentinel AI', 'Overview'] },
  pipeline:      { title: 'Pipeline Monitor',   breadcrumb: ['DataSentinel AI', 'Pipeline Monitor'] },
  experiments:   { title: 'Experiment Lab',     breadcrumb: ['DataSentinel AI', 'Experiment Lab'] },
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
  const {
    currentPage,
    navigate,
    backendStatus,
    healthData,
    latestReport,
    aiHealth,
  } = useContext(AppContext);
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
        <LocalModeIndicator />
        <AnalysisIndicator
          status={healthData?.analysis_engine_status ?? null}
          engine={healthData?.analysis_engine ?? null}
        />
        <AIIndicator
          status={aiHealth?.status ?? null}
          model={aiHealth?.model ?? null}
        />

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

function AnalysisIndicator({
  status,
  engine,
}: {
  status: 'available' | 'unavailable' | null;
  engine: string | null;
}) {
  const available = status === 'available';
  const label = status === null
    ? 'Analysis Not Checked'
    : available
      ? 'Analysis Verified'
      : 'Analysis Unavailable';
  const className = available
    ? 'text-emerald-400 border-emerald-900/50 bg-emerald-950/30'
    : status === null
      ? 'text-[#8B9BB4] border-[#223149]'
      : 'text-red-300 border-red-900/50 bg-red-950/30';

  return (
    <div
      className={cn(
        'hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] font-medium',
        className,
      )}
      aria-label={`Analysis engine status: ${label}`}
      title={`${label}${engine ? ` · ${engine}` : ''}. Verified using a generic synthetic dataset and the protection gate.`}
    >
      <Cpu className="h-3 w-3" />
      <span>{label}</span>
    </div>
  );
}

function LocalModeIndicator() {
  let local = false;
  try {
    const hostname = new URL(getApiBaseUrl()).hostname;
    local = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
  } catch {
    local = false;
  }
  if (!local) return null;

  return (
    <div
      className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] font-medium text-cyan-300 border-cyan-900/50 bg-cyan-950/30"
      title="The configured API is on this machine. Deterministic analysis does not require internet; local AI availability is checked separately."
      aria-label="Local API mode"
    >
      <HardDrive className="h-3 w-3" />
      <span>Local API</span>
    </div>
  );
}

function AIIndicator({
  status,
  model,
}: {
  status: string | null;
  model: string | null;
}) {
  const available = status === 'AVAILABLE';
  const label = status === null
    ? 'AI Not Checked'
    : status === 'AVAILABLE'
      ? 'AI Verified'
      : status === 'MODEL_NOT_INSTALLED'
        ? 'Model Missing'
        : status === 'OLLAMA_UNAVAILABLE'
          ? 'AI Unavailable'
          : status === 'NOT_CONFIGURED'
            ? 'AI Not Configured'
            : 'AI Inference Failed';
  const className = available
    ? 'text-emerald-400 border-emerald-900/50 bg-emerald-950/30'
    : status === null
      ? 'text-[#8B9BB4] border-[#223149]'
      : 'text-amber-300 border-amber-900/50 bg-amber-950/30';

  return (
    <div
      className={cn(
        'hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] font-medium',
        className,
      )}
      aria-label={`Local AI status: ${label}`}
      title={`${label}${model ? ` · ${model}` : ''}. AI availability is based on a real local inference check; deterministic analysis and protection do not depend on AI.`}
    >
      <Cpu className="h-3 w-3" />
      <span>{label}</span>
      {model && <span className="font-mono opacity-80">{model}</span>}
    </div>
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
