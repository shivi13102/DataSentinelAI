# Offline Setup

## What works without internet

With dependencies already installed, the frontend and backend run on
localhost. CSV loading, deterministic analysis, protection decisions,
report files, monitored-run events, and Experiment Lab operations are local.
Charts use bundled frontend dependencies and do not require a CDN.

Local AI works offline only when Ollama is running and the configured model is
already installed. If Ollama is unavailable, analysis, reports, and
`ALLOW`/`REVIEW_REQUIRED`/`BLOCK` decisions continue; AI is reported as
unavailable and no substitute explanation is fabricated.

## What needs internet beforehand

- Installing Python packages from `requirements.txt`.
- Installing frontend dependencies with `npm ci`.
- Downloading the Ollama installer and pulling a model for the first time.
- Remote GitHub Actions or Jenkins services, if those are part of the demo.

Complete those steps and verify the laptop at home. Application startup does
not install packages, download weights, or call a hosted model.

## Prepare local services (Windows PowerShell)

From the repository root, install project dependencies if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Push-Location frontend
npm ci
Pop-Location
```

Install Ollama separately if needed, then pull the configured model while
internet is available:

```powershell
ollama pull gemma4:e2b
ollama list
```

Set optional runtime configuration in the PowerShell session before starting
the app:

```powershell
$env:DATASENTINEL_AI_PROVIDER = 'ollama'
$env:DATASENTINEL_AI_MODEL = 'gemma4:e2b'
$env:DATASENTINEL_OLLAMA_URL = 'http://127.0.0.1:11434'
$env:DATASENTINEL_AI_TIMEOUT_SECONDS = '120'
```

The model, URL, and timeout have defaults; do not set a cloud provider for the
offline demonstration.

## Verify offline readiness

```powershell
.\.venv\Scripts\python.exe scripts\demo_preflight.py
```

The preflight performs local checks and a real Ollama inference when the
service/model is available. It uses generated temporary generic data and does
not read demo CSVs. A missing AI service is reported as a warning because the
deterministic pipeline remains functional.

The frontend's default API URL is `http://127.0.0.1:8000`; the UI is served at
`http://127.0.0.1:5173`. Both services should run on the demo laptop. Do not
use a CDN, remote font, or hosted model as a demo prerequisite.
