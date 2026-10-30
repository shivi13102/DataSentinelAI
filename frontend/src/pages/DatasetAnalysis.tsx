// ============================================================
// Dataset Analysis – file upload and analysis submission
// ============================================================

import { useCallback, useContext, useRef, useState } from 'react';
import {
  Upload,
  FileText,
  X,
  CheckCircle2,
  AlertTriangle,
  Loader,
} from 'lucide-react';

import { AppContext } from '../App';
import { analyzeDatasets } from '../lib/api';
import { Card, CardHeader, CardTitle, CardBody } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { cn, formatBytes } from '../lib/utils';

type AnalysisStage =
  | 'idle'
  | 'analyzing'
  | 'done'
  | 'error';

const STAGE_LABELS: Record<AnalysisStage, string> = {
  idle:       '',
  analyzing:  'Uploading files and waiting for backend analysis…',
  done:       'Analysis complete.',
  error:      'Analysis failed.',
};

export function DatasetAnalysis() {
  const { setLatestReport, refreshReports, navigate, toast } = useContext(AppContext);

  const [baselineFile, setBaselineFile] = useState<File | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [stage, setStage] = useState<AnalysisStage>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const baselineInputRef = useRef<HTMLInputElement>(null);
  const currentInputRef = useRef<HTMLInputElement>(null);

  const isAnalysing = !['idle', 'done', 'error'].includes(stage);

  // ── File validation ────────────────────────────────────────

  function validateFile(file: File): string | null {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      return 'Only CSV files are supported.';
    }
    if (file.size === 0) {
      return 'The selected file is empty.';
    }
    if (file.size > 50 * 1024 * 1024) {
      return 'File exceeds 50 MB. Please use a smaller dataset.';
    }
    return null;
  }

  // ── Drag-and-drop helpers ──────────────────────────────────

  function handleFileDrop(
    e: React.DragEvent,
    setter: (f: File | null) => void,
  ) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const err = validateFile(file);
    if (err) { toast(err, 'error'); return; }
    setter(file);
  }

  function handleFileInput(
    e: React.ChangeEvent<HTMLInputElement>,
    setter: (f: File | null) => void,
  ) {
    const file = e.target.files?.[0];
    if (!file) return;
    const err = validateFile(file);
    if (err) { toast(err, 'error'); return; }
    setter(file);
    e.target.value = '';
  }

  // ── Submission ────────────────────────────────────────────

  const handleAnalyse = useCallback(async () => {
    if (!baselineFile || !currentFile) return;
    setErrorMsg('');

    try {
      setStage('analyzing');
      const report = await analyzeDatasets(baselineFile, currentFile);
      setLatestReport(report);
      await refreshReports();

      if (report.workflow_status !== 'success') {
        const message = report.error
          || 'Analysis did not complete successfully. Downstream processing is blocked.';
        setStage('error');
        setErrorMsg(message);
        toast(message, 'error');
        navigate('overview');
        return;
      }

      setStage('done');
      toast('Analysis complete. Report saved.', 'success');

      navigate('overview');
    } catch (err: unknown) {
      setStage('error');
      const msg = err instanceof Error ? err.message : 'Analysis failed. Check the backend.';
      setErrorMsg(msg);
      toast(msg, 'error');
    }
  }, [baselineFile, currentFile, setLatestReport, refreshReports, navigate, toast]);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[#E5EDF9] tracking-tight">Dataset Analysis</h1>
        <p className="text-sm text-[#8B9BB4] mt-0.5">
          Upload a trusted baseline and a current CSV to detect data-quality issues.
        </p>
      </div>

      {/* Instructions */}
      <Card>
        <CardBody className="flex gap-4 items-start">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-cyan-950/50 text-cyan-400">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div className="text-sm text-[#8B9BB4] space-y-1">
            <p>
              <span className="text-[#E5EDF9] font-medium">Baseline</span> — your trusted reference dataset (historical data you know is clean).
            </p>
            <p>
              <span className="text-[#E5EDF9] font-medium">Current</span> — the new dataset you want to investigate for anomalies.
            </p>
            <p>
              Python detectors run first. Gemma generates an AI investigation once analysis completes.
              Only CSV files are supported. With the default local backend, files stay on this machine.
            </p>
          </div>
        </CardBody>
      </Card>

      {/* Upload panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UploadPanel
          label="Trusted Baseline"
          description="Reference dataset — the expected state"
          file={baselineFile}
          onFile={setBaselineFile}
          onDrop={e => handleFileDrop(e, setBaselineFile)}
          onInput={e => handleFileInput(e, setBaselineFile)}
          inputRef={baselineInputRef}
          disabled={isAnalysing}
          accentColor="cyan"
        />
        <UploadPanel
          label="Current Dataset"
          description="Dataset under investigation"
          file={currentFile}
          onFile={setCurrentFile}
          onDrop={e => handleFileDrop(e, setCurrentFile)}
          onInput={e => handleFileInput(e, setCurrentFile)}
          inputRef={currentInputRef}
          disabled={isAnalysing}
          accentColor="blue"
        />
      </div>

      {/* Progress */}
      {isAnalysing && (
        <AnalysisProgress stage={stage} />
      )}

      {/* Error */}
      {stage === 'error' && errorMsg && (
        <div className="flex items-start gap-3 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-300">Analysis failed</p>
            <p className="text-xs text-red-400/80 mt-0.5">{errorMsg}</p>
          </div>
        </div>
      )}

      {/* Success */}
      {stage === 'done' && (
        <div className="flex items-center gap-3 rounded-lg border border-emerald-900/50 bg-emerald-950/30 px-4 py-3">
          <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
          <p className="text-sm text-emerald-300">Analysis complete. Navigating to overview…</p>
        </div>
      )}

      {/* Submit */}
      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          size="lg"
          onClick={() => void handleAnalyse()}
          disabled={!baselineFile || !currentFile || isAnalysing}
          loading={isAnalysing}
          className="min-w-[160px]"
        >
          {isAnalysing ? 'Analysing…' : 'Analyse Datasets'}
        </Button>
        {(stage === 'error') && (
          <Button
            variant="secondary"
            size="lg"
            onClick={() => {
              setStage('idle');
              setErrorMsg('');
            }}
          >
            Reset
          </Button>
        )}
        <p className="text-xs text-[#8B9BB4]">
          Both files must be selected before analysis can begin.
        </p>
      </div>
    </div>
  );
}

// ── Upload panel ──────────────────────────────────────────────

interface UploadPanelProps {
  label: string;
  description: string;
  file: File | null;
  onFile: (f: File | null) => void;
  onDrop: (e: React.DragEvent) => void;
  onInput: (e: React.ChangeEvent<HTMLInputElement>) => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
  disabled: boolean;
  accentColor: 'cyan' | 'blue';
}

function UploadPanel({
  label,
  description,
  file,
  onFile,
  onDrop,
  onInput,
  inputRef,
  disabled,
  accentColor,
}: UploadPanelProps) {
  const [dragging, setDragging] = useState(false);

  const accent = accentColor === 'cyan'
    ? { border: 'border-cyan-700/60', bg: 'bg-cyan-950/20', text: 'text-cyan-400', ring: 'ring-cyan-700/40' }
    : { border: 'border-blue-700/60', bg: 'bg-blue-950/20', text: 'text-blue-400', ring: 'ring-blue-700/40' };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
        <span className={`text-[11px] ${accent.text}`}>CSV only</span>
      </CardHeader>
      <CardBody>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={onInput}
          disabled={disabled}
          aria-label={`Select ${label} CSV file`}
        />

        {file ? (
          <div className={cn(
            'flex items-center gap-3 rounded-lg border p-4',
            accent.border, accent.bg,
          )}>
            <FileText className={cn('h-5 w-5 shrink-0', accent.text)} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[#E5EDF9] truncate">{file.name}</p>
              <p className="text-xs text-[#8B9BB4] mt-0.5">{formatBytes(file.size)}</p>
            </div>
            {!disabled && (
              <button
                onClick={() => onFile(null)}
                aria-label="Remove file"
                className="shrink-0 text-[#8B9BB4] hover:text-red-400 transition-colors focus-ring rounded"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        ) : (
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { setDragging(false); onDrop(e); }}
            onClick={() => !disabled && inputRef.current?.click()}
            className={cn(
              'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors',
              dragging
                ? `${accent.border} ${accent.bg} ring-2 ${accent.ring}`
                : 'border-[#223149] hover:border-[#2d4a6e] hover:bg-[#142036]',
              disabled && 'opacity-50 pointer-events-none',
            )}
            role="button"
            tabIndex={0}
            aria-label={`Drop or click to select ${label} CSV`}
            onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
          >
            <div className={cn(
              'flex h-10 w-10 items-center justify-center rounded-full',
              dragging ? `${accent.bg} ${accent.text}` : 'bg-[#142036] text-[#8B9BB4]',
            )}>
              <Upload className="h-5 w-5" />
            </div>
            <div className="text-center">
              <p className="text-sm text-[#E5EDF9]">
                <span className={cn('font-medium', accent.text)}>Click to browse</span>
                {' '}or drag and drop
              </p>
              <p className="text-xs text-[#8B9BB4] mt-1">{description}</p>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ── Progress indicator ────────────────────────────────────────

function AnalysisProgress({ stage }: { stage: AnalysisStage }) {
  return (
    <Card elevated>
      <CardBody>
        <div className="flex items-center gap-2 mb-4">
          <Loader className="h-4 w-4 text-cyan-400 animate-spin" />
          <p className="text-sm font-medium text-[#E5EDF9]">
            {STAGE_LABELS[stage]}
          </p>
        </div>
      </CardBody>
    </Card>
  );
}
