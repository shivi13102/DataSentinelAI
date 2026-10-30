# DataSentinel AI Demo Readiness

## Audit summary

This audit deliberately excludes private demonstration CSVs and any
`historical_batches/` directory. Automated checks use generated temporary data
with generic column names.

### Implemented

- FastAPI CSV upload analysis and local JSON report persistence.
- Generic baseline/current CSV comparison; column names are detected from
  uploaded files rather than an e-commerce schema.
- Deterministic schema, missing-value, duplicate, numeric-drift, and
  categorical-drift detectors, followed by a fail-closed protection gate.
- Monitored pipeline runs with structured events and SSE, plus controlled
  Experiment Lab cases.
- Local Ollama reasoning using the configured `gemma3:1b` model by default.
  `DATASENTINEL_AI_MODEL`, `DATASENTINEL_OLLAMA_URL`, and
  `DATASENTINEL_AI_TIMEOUT_SECONDS` can configure it.
- The upload-report LangGraph now evaluates the deterministic gate before it
  calls optional AI reasoning. The monitored-run path already gates before
  AI. AI failure does not change deterministic decisions.
- AI health endpoint verifies Ollama reachability, exact configured model
  installation, and an actual local inference. No model is downloaded by
  application startup.
- GitHub Actions and Jenkins configuration files exist.

### Partial or limited

- Analysis is generic for each uploaded baseline/current pair. A durable
  baseline registration and promotion workflow is not implemented; users
  upload the trusted baseline for each analysis.
- Analysis reports are persisted as local JSON files and populate the Reports
  UI. Monitored run snapshots/events are bounded process memory and are lost
  when the backend restarts.
- Experiment records/events use local SQLite and copied CSV files. There is no
  retention or deletion UI.
- The branched monitoring graph visualizes dependencies; it does not mean
  detectors execute in parallel.
- Downstream processing is simulated only. There is no external production
  connector, authentication/authorization, or multi-worker run store.
- Jenkins/GitHub Actions configuration is present; this local preflight does
  not prove a hosted build/job ran.

### External connectivity and offline behavior

- Runtime AI calls default to local Ollama at `http://127.0.0.1:11434`; no
  external LLM provider is used by the current reasoning implementation.
- The default frontend API address is localhost. The backend has local CORS
  origins configured. Frontend libraries are bundled locally; the app does
  not require a CDN at runtime.
- Initial Python/npm dependency installation and pulling the Ollama model may
  require internet. They should be completed and tested at home. No dependency
  or model download is triggered when the application starts.
- Without internet and with Ollama available, analysis, protection, reports,
  monitoring, and local AI can work. Without Ollama, deterministic
  analysis/protection/reports continue and the AI status is not green.
- The browser's Vite development server and backend must both be running on
  the laptop. For a live venue demo, avoid changing the API base URL away from
  localhost.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe scripts\demo_preflight.py
.\.venv\Scripts\python.exe -m pytest -q
Push-Location frontend
npm run build
Pop-Location
```

The preflight generates independent temporary generic CSV data, checks
`ALLOW`/`REVIEW_REQUIRED`/`BLOCK`, report writing in a temporary directory,
LangGraph execution, local package/build prerequisites, and actual local AI
inference when Ollama is available. Missing Ollama/Jenkins are warnings; core
failures return a nonzero exit code.

### Current verified status

Validated on this Windows laptop on 2026-10-31. Do not treat the presence of a
workflow file as proof of a remote CI run.

- Python tests: `177 passed`.
- Frontend production build: passed; Vite reports a 721.80 kB minified
  JavaScript chunk warning.
- Frontend lint: passed with three warnings (Fast Refresh export in `App.tsx`
  and two existing `useMemo` dependency warnings in `AnomalyExplorer.tsx`).
- Demo preflight: all core checks passed; overall `READY WITH WARNINGS` because
  `DATASENTINEL_JENKINS_URL` is not configured. The latest run also passed
  schema-validated AI reasoning against one synthetic detector finding.
- Local AI: actual Ollama inference `AVAILABLE`, configured model
  `gemma3:1b`; latest health inference completed in 724.12 ms. A separate
  synthetic-finding reasoning check returned a schema-valid explanation.
- PowerShell syntax: startup and shutdown scripts parsed successfully.
  Startup was smoke-tested with pre-existing localhost services and left both
  untouched. The owned-process launch/stop path was not exercised because
  ports 8000 and 5173 were already occupied by processes not started by the
  demo script.
- Jenkins/hosted GitHub Actions: verify in their respective services; no
  remote job result is claimed by this local run.

## Before the event

- Run `ollama list` and confirm the configured model is installed.
- Run the AI health endpoint and require `AVAILABLE` before promising a live AI
  explanation.
- Run the preflight and resolve all `FAIL` items. Optional AI/Jenkins warnings
  should be understood and disclosed.
- Keep the private demo datasets outside the repository. Upload them only
  during the live demonstration from their separate location.
- Explain clearly that review approval, registered baselines, durable
  monitored-run history, and production downstream integration are not
  implemented.
