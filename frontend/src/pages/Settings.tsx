// ============================================================
// Settings – Application & Backend Configuration
// ============================================================

import { useContext, useState } from 'react';
import {
  Cpu,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Save,
  Globe,
  ShieldCheck,
  Info,
} from 'lucide-react';

import { AppContext } from '../App';
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import {
  getApiBaseUrl,
  setApiBaseUrl,
  DEFAULT_BASE_URL,
  checkHealth,
} from '../lib/api';

export function SettingsPage() {
  const { backendStatus, healthData, toast } = useContext(AppContext);

  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  async function handleTestAndSave() {
    setTestingConnection(true);
    setTestResult(null);

    const targetUrl = apiUrl.trim().replace(/\/$/, '');
    if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
      setTestResult({
        ok: false,
        message: 'API URL must begin with http:// or https://',
      });
      setTestingConnection(false);
      return;
    }

    try {
      setApiBaseUrl(targetUrl);
      const health = await checkHealth();
      setTestResult({
        ok: true,
        message: `Successfully connected! Service: ${health.service} v${health.version}`,
      });
      toast('API configuration updated and verified', 'success');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Connection failed';
      setTestResult({
        ok: false,
        message: `Unable to reach ${targetUrl}/api/health: ${msg}`,
      });
      toast('Could not verify backend at target URL', 'error');
    } finally {
      setTestingConnection(false);
    }
  }

  function handleResetDefault() {
    setApiUrl(DEFAULT_BASE_URL);
    setApiBaseUrl(DEFAULT_BASE_URL);
    setTestResult(null);
    toast('API URL reset to default', 'info');
  }

  return (
    <div className="p-6 space-y-6 max-w-[1000px] mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[#E5EDF9] tracking-tight">
          System Configuration & Settings
        </h1>
        <p className="text-sm text-[#8B9BB4] mt-0.5">
          Manage local API endpoints, view engine telemetry, and inspect active detector configurations.
        </p>
      </div>

      {/* Backend API Connection */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-[#22D3EE]" />
            <CardTitle>FastAPI Backend Connection</CardTitle>
          </div>
          <Badge
            variant={
              backendStatus === 'online'
                ? 'success'
                : backendStatus === 'offline'
                ? 'critical'
                : 'neutral'
            }
            dot
          >
            {backendStatus.toUpperCase()}
          </Badge>
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-xs text-[#8B9BB4]">
            DataSentinel AI communicates with a local FastAPI backend running on localhost:8000 by default.
            You can modify the endpoint if running in a custom containerized environment.
          </p>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-[#8B9BB4] uppercase">
              API Base URL
            </label>
            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={apiUrl}
                onChange={e => setApiUrl(e.target.value)}
                placeholder="http://127.0.0.1:8000"
                className="flex-1 min-w-[260px] bg-[#142036] border border-[#223149] rounded px-3 py-2 text-sm text-[#E5EDF9] font-mono focus:outline-none focus:border-cyan-700/60 focus-ring"
              />
              <Button
                variant="primary"
                size="md"
                onClick={() => void handleTestAndSave()}
                loading={testingConnection}
                icon={<Save className="h-3.5 w-3.5" />}
              >
                Save & Verify
              </Button>
              <Button
                variant="secondary"
                size="md"
                onClick={handleResetDefault}
                icon={<RotateCcw className="h-3.5 w-3.5" />}
              >
                Reset Default
              </Button>
            </div>
          </div>

          {testResult && (
            <div
              className={`flex items-start gap-2 rounded-lg border p-3 text-xs ${
                testResult.ok
                  ? 'border-emerald-900/60 bg-emerald-950/30 text-emerald-300'
                  : 'border-red-900/60 bg-red-950/30 text-red-300'
              }`}
            >
              {testResult.ok ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" />
              ) : (
                <AlertTriangle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
              )}
              <div className="leading-relaxed">{testResult.message}</div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Engine Telemetry & Architecture Specifications */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-[#60A5FA]" />
            <CardTitle>Architecture & Engine Specifications</CardTitle>
          </div>
          <span className="text-xs text-[#8B9BB4]">Verified via /api/health</span>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-lg bg-[#142036] border border-[#223149] p-4 space-y-1">
              <span className="text-[10px] font-semibold text-[#8B9BB4] uppercase">
                Analysis Engine
              </span>
              <p className="text-sm font-semibold text-[#E5EDF9]">
                {healthData?.analysis_engine ?? 'Python & Pandas (Deterministic)'}
              </p>
              <p className="text-xs text-[#8B9BB4]">
                Executes Kolmogorov-Smirnov, Chi-square, and null-rate detectors in-memory.
              </p>
            </div>

            <div className="rounded-lg bg-[#142036] border border-[#223149] p-4 space-y-1">
              <span className="text-[10px] font-semibold text-[#8B9BB4] uppercase">
                Workflow Orchestrator
              </span>
              <p className="text-sm font-semibold text-[#E5EDF9]">
                {healthData?.workflow_engine ?? 'LangGraph StateGraph'}
              </p>
              <p className="text-xs text-[#8B9BB4]">
                Stateful pipeline orchestration linking detection, reasoning, and gating nodes.
              </p>
            </div>

            <div className="rounded-lg bg-[#142036] border border-[#223149] p-4 space-y-1">
              <span className="text-[10px] font-semibold text-[#8B9BB4] uppercase">
                Configured AI Model
              </span>
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-[#22D3EE] font-mono">
                  {healthData?.configured_ai_model ?? 'gemma3:1b'}
                </p>
                <Badge variant="info" size="sm">Ollama Local</Badge>
              </div>
              <p className="text-xs text-[#8B9BB4]">
                Local LLM instance queried with structured JSON schemas.
              </p>
            </div>

            <div className="rounded-lg bg-[#142036] border border-[#223149] p-4 space-y-1">
              <span className="text-[10px] font-semibold text-[#8B9BB4] uppercase">
                Protection Gate Status
              </span>
              <p className="text-sm font-semibold text-emerald-400">
                Authoritative Fail-Closed Policy
              </p>
              <p className="text-xs text-[#8B9BB4]">
                BLOCK / REVIEW_REQUIRED decisions override any LLM optimism.
              </p>
            </div>
          </div>

          <div className="mt-4 p-3 rounded-lg bg-[#101A2B] border border-[#223149] flex items-start gap-2.5 text-xs text-[#8B9BB4]">
            <Info className="h-4 w-4 text-[#22D3EE] shrink-0 mt-0.5" />
            <div>
              <span className="text-[#E5EDF9] font-medium">Model Availability Distinction:</span>{' '}
              The <span className="font-mono text-[#22D3EE]">{healthData?.configured_ai_model ?? 'gemma3:1b'}</span>{' '}
              designation confirms the model configured on the backend. True runtime availability depends on
              the Ollama daemon being active at <span className="font-mono text-[#60A5FA]">http://localhost:11434</span>.
              If Ollama is stopped, the pipeline preserves all deterministic Python findings and records an AI status notice.
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Built-in Statistical Detectors */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#34D399]" />
            <CardTitle>Registered Statistical Detectors</CardTitle>
          </div>
          <Badge variant="neutral">5 Active Detectors</Badge>
        </CardHeader>
        <CardBody className="space-y-3">
          <DetectorRow
            name="Missing Value Anomaly Detector"
            metric="Percentage Point Differential"
            method="missing_value_percentage"
            description="Flags unexpected increases in NaN / null ratios exceeding configured sensitivity thresholds."
          />
          <DetectorRow
            name="Duplicate Record Detector"
            metric="Exact Row Invariant Hash"
            method="duplicate_row_comparison"
            description="Detects duplication spikes across all shared dataset feature columns."
          />
          <DetectorRow
            name="Numerical Distribution Drift Detector"
            metric="Two-Sample Kolmogorov-Smirnov Test (KS)"
            method="summary_statistics_and_ks_test"
            description="Calculates empirical CDF divergence and mean / variance shifts across continuous numeric series."
          />
          <DetectorRow
            name="Categorical Drift Detector"
            metric="Total Variation Distance (TVD) & Pearson Chi-Square"
            method="total_variation_distance_and_chi_square"
            description="Identifies discrete distribution shifts, category emergence (e.g. 'Unknown'), and category drop-outs."
          />
          <DetectorRow
            name="Schema Change Detector"
            metric="Column Set Symmetric Difference"
            method="schema_detector"
            description="Monitors additions, removals, and structural column alterations between baseline and current data."
          />
        </CardBody>
      </Card>
    </div>
  );
}

function DetectorRow({
  name,
  metric,
  method,
  description,
}: {
  name: string;
  metric: string;
  method: string;
  description: string;
}) {
  return (
    <div className="p-3 rounded-lg bg-[#142036] border border-[#223149] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
      <div>
        <p className="text-xs font-semibold text-[#E5EDF9]">{name}</p>
        <p className="text-[11px] text-[#8B9BB4] mt-0.5">{description}</p>
      </div>
      <div className="text-left sm:text-right shrink-0">
        <span className="text-[10px] font-mono text-[#22D3EE] block">{method}</span>
        <span className="text-[10px] text-[#8B9BB4] block">{metric}</span>
      </div>
    </div>
  );
}
