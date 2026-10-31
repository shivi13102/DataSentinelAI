# DataSentinel AI Demo Runbook

## What this demo proves

This local demo shows the checked-in data-quality detectors, the deterministic
protection gate, monitored pipeline execution, and the Experiment Lab's
controlled injection and recovery workflow. The simulated downstream step is
not a production integration. Lineage traversal, governed baseline promotion,
review approvals, and durable incident history are not implemented.

## Requirements

- Python 3.11 or newer
- Node.js 20 and npm
- Dependencies installed from `requirements.txt` and `frontend/package-lock.json`
- Optional: Ollama with `gemma4:e2b` (Gemma 4 E2B); the deterministic gate
  does not require it

## Start the application (Windows PowerShell)

From the repository root, open two terminals.

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2:

```powershell
Set-Location frontend
npm run dev
```

Open `http://127.0.0.1:5173`. The API documentation is at
`http://127.0.0.1:8000/docs`.

## Demo sequence (about 5-7 minutes)

1. **Healthy / safe to continue**
   - In Pipeline Monitor, select `healthy` and start a run.
   - Expected: `ALLOW`; the simulated downstream stage runs.
2. **Suspicious / hold for review**
   - Select `suspicious`.
   - Expected: `REVIEW_REQUIRED`; downstream is blocked. There is no approval
     action in the current product.
3. **Critical / block**
   - Select `critical`.
   - Expected: `BLOCK`; downstream is blocked.
4. **Inspect evidence**
   - Open the run's stages, event history, findings, and report.
   - Explain that the AI investigation is advisory; the deterministic gate
     decides whether downstream can run.
5. **Experiment Lab**
   - Create a missing-values experiment against the sample dataset.
   - Review the measured detector result, apply the controlled correction, and
     run recovery verification.
   - Expected: the targeted missing-value finding is measured before
     correction and is absent for that target after correction. Other findings
     are reported separately.

If time is short, steps 1-4 are the core demo. Do not claim that a pipeline
graph branch means independent parallel execution; it visualizes the
gate-dependent paths and their dependencies.

## Reproducible fixture set

The fixture pairs are tracked in `tests/fixtures/protection/`; their expected
finding types and decisions are in `evaluation_manifest.json`. Seven scenarios
are available: healthy, suspicious, critical, duplicate, numerical drift,
categorical drift, and multiple anomalies.

Regenerate the deterministic fixture set and validate it:

```powershell
python scripts\generate_protection_fixtures.py
python -m pytest tests\test_protection_scenarios.py tests\test_run_pipeline.py -v
```

The generator writes only those named fixture files. Do not point it at
`data/raw/` or replace a user's data.

On Windows with desktop PowerPoint installed, regenerate the presentation with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_phase4_presentation.ps1
```

## Reset and data handling

- Stop the API and frontend with `Ctrl+C`.
- Start a fresh monitored run; run state is in process memory and is discarded
  when the API process stops.
- Experiment records and copied CSVs persist under ignored `reports/`.
  There is no reset or retention UI. Treat uploaded experiment CSVs as
  sensitive. Back up anything needed before manually removing only the
  experiment database and files that belong to your demo:
  `reports/experiments.sqlite3`, its SQLite `-wal`/`-shm` sidecars if present,
  and `reports/experiments/`.
- Do not delete `data/raw/`, the repository, or the whole `reports/` folder as
  a general reset step. Reports and local experiment data may belong to the
  user.
