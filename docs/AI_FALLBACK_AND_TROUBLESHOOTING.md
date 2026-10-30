# AI Fallback and Troubleshooting

## AI behavior

AI reasoning is an optional explanation layer. Deterministic detectors and
the protection gate remain authoritative when Ollama/Gemma is not installed,
stopped, or unable to answer. An AI failure must not be described as a
successful investigation, and an AI response must not be described as
approval.

Optional local setup:

```powershell
ollama pull gemma3:1b
ollama serve
```

Keep the Ollama process running in a separate terminal. If the model or service
is unavailable, continue the deterministic demo and show the reported AI
error/skipped status.

## Common issues

| Symptom | Check / action |
|---|---|
| Frontend cannot reach the API | Start `uvicorn api:app --host 127.0.0.1 --port 8000 --reload`; check `http://127.0.0.1:8000/docs`. |
| Frontend dependency resolution failure | From `frontend`, run `npm ci` to install the lockfile's dependencies, then restart Vite. |
| A fixture scenario is unknown | Use one of the checked-in IDs in `tests/fixtures/protection/evaluation_manifest.json`. |
| `REVIEW_REQUIRED`/`BLOCK` is not green in Jenkins | This is an intentional protection outcome: tests/analysis may pass while Jenkins is marked unstable and downstream is withheld. |
| AI investigation fails | Check that Ollama is running and `gemma3:1b` is available. The gate result remains deterministic; continue without AI. |
| A run cannot be found after backend restart | Run state is in memory and does not survive restart. Start a new run. |
| A stage fails | Inspect the run state/report for the safe error category. The failure path does not authorize downstream work. |
| Experiment data remains after restart | Experiment records and copied CSVs persist under ignored `reports/`; this is expected. Back up before targeted cleanup. |
| Production use is requested | Do not expose this local demo API publicly. Authentication, durable shared state, production downstream integration, and retention controls are absent. |

