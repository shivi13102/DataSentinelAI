# Phase 4 Validation Record

Validation was performed against the current local checkout.

## Results

| Check | Result | Notes |
|---|---|---|
| Python tests | Pass | `.\.venv\Scripts\python.exe -m pytest -q` — 177 passed on 2026-10-31. |
| Frontend lint | Pass with warnings | `npm run lint` from `frontend`; three warnings in `App.tsx` and `AnomalyExplorer.tsx`. |
| Frontend production build | Pass with warning | `npm run build` from `frontend`; Vite reports a 721.80 kB minified JS chunk. |
| Deterministic fixture matrix | Pass | All seven fixture pairs matched expected decisions and finding types in the real analysis/gate runner. |
| GitHub Actions | Local configuration only | The configured test/build commands passed locally. No hosted Actions run is asserted here. |
| Jenkins | Not run | Jenkins CLI/service was unavailable locally. |
| Demo preflight | Core checks pass; optional AI/Jenkins warnings | Temporary generic CSV fixtures produced `ALLOW`, `REVIEW_REQUIRED`, and `BLOCK`; report and LangGraph checks passed. An earlier run exceeded the 30-second health and 45-second reasoning timeouts. Jenkins connectivity was not configured; no remote job was executed. |
| Ollama/Gemma | Installed; structured inference verified | Local `gemma4:e2b` health check returned `AVAILABLE`; a synthetic structured reasoning request completed successfully in 77.47 seconds with a 120-second timeout. |

## Fixture matrix observed

| Scenario | Finding type(s) | Decision |
|---|---|---|
| `healthy` | None | `ALLOW` |
| `suspicious` | `missing_value_anomaly` | `REVIEW_REQUIRED` |
| `critical` | `schema_change` | `BLOCK` |
| `duplicate` | `duplicate_anomaly` | `REVIEW_REQUIRED` |
| `numerical_drift` | `distribution_drift` | `BLOCK` |
| `categorical_drift` | `categorical_drift` | `BLOCK` |
| `multiple` | `duplicate_anomaly`, `missing_value_anomaly` | `REVIEW_REQUIRED` |

The API integration tests additionally exercise actual monitored-run
`ALLOW`/review/block behavior, report and event access, invalid inputs, stage
failure, AI fallback behavior, and run isolation. These tests do not establish
remote CI execution or production integration.
