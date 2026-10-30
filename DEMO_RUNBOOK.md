# DataSentinel AI Demo Runbook

## Before the event

1. Install Python and Node dependencies while internet is available.
2. Install Ollama and manually pull `gemma3:1b` if local AI will be shown.
3. Run the preflight and tests:

   ```powershell
   .\.venv\Scripts\python.exe scripts\demo_preflight.py
   .\.venv\Scripts\python.exe -m pytest -q
   ```

4. Confirm real model inference with
   `Invoke-RestMethod http://127.0.0.1:8000/api/health/ai` after startup.
5. Keep the final private demo datasets outside the repository. This project
   preparation does not need to access them.

## Start (Windows PowerShell)

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_demo.ps1
```

The script checks the virtual environment and frontend dependencies, imports
the backend, checks ports, starts only missing local services, and reports
actual local AI health. It will not stop an unrelated process occupying a
required port. Started processes are recorded under ignored `.demo-runtime/`.

Open:

- Frontend: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:8000/api/health`
- AI health (actual inference check): `http://127.0.0.1:8000/api/health/ai`
- API documentation: `http://127.0.0.1:8000/docs`

## Demo sequence

1. Explain that Python detectors measure changes and the deterministic gate
   controls downstream permission.
2. Upload a trusted baseline and current CSV pair using Dataset Analysis.
   The workflow is generic and does not require predefined column names.
3. Show measured findings, decision, report, and AI status.
4. If time permits, show Pipeline Monitor and an Experiment Lab recovery.
5. State explicitly that downstream is simulated; review approval,
   registered/governed baselines, and persistent monitored-run history are not
   implemented.

## AI fallback

If local AI reports unavailable, missing model, or inference failure, say:

> Local AI investigation is currently unavailable. Deterministic data-quality
> analysis and pipeline protection are operating normally.

Continue the demo with measured findings, gate decision, and report. Do not
present a template or guessed explanation as a Gemma response.

Judge explanation:

> DataSentinel separates deterministic pipeline protection from AI-assisted
> investigation. The protection gate is rule-based and does not depend on an
> LLM. Our local Gemma model provides additional root-cause investigation, so
> even if the model is unavailable, the pipeline remains protected.

## Stop

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_demo.ps1
```

The stop script terminates only process IDs recorded by `start_demo.ps1` whose
executable and command line still match the recorded DataSentinel service. It
leaves externally started or mismatched processes untouched.

## Troubleshooting

- **Port occupied:** Identify the service yourself. The scripts intentionally
  do not kill processes they did not start.
- **Backend imports fail:** Activate `.venv`, install `requirements.txt`, and
  rerun preflight.
- **Frontend is missing:** Run `npm ci` in `frontend` while internet is
  available.
- **AI unavailable:** Start Ollama; use `ollama list`; confirm the configured
  tag; run the `/api/health/ai` inference check.
- **Backend restarts lose a monitored run:** This is expected; monitored run
  state is in-process memory. Persisted analysis report files remain available.
- **Network is restricted:** Keep API and Ollama URLs on `127.0.0.1`; continue
  with deterministic analysis if Ollama cannot run.
