# Technical Architecture and Implementation Status

## Runtime flow

```text
CSV fixture or upload
        |
        v
FastAPI monitored-run API -----> bounded in-process worker pool
        |                                  |
        |                         CSV loader and validation
        |                                  |
        |                         deterministic detectors
        |                                  |
        |                         protection gate
        |                           /          \
        |                    ALLOW only      REVIEW_REQUIRED / BLOCK
        |                       |                    |
        |               simulated downstream       withheld
        |                       \                    /
        +---- ordered events / SSE + report <-------+
        |
        +---- optional local Ollama/Gemma explanation (advisory only)
```

The React/Vite frontend calls the FastAPI API. The gate uses deterministic
analysis results and is the only authority for downstream permission. AI
reasoning is not required for a protection decision.

## Implemented surfaces

- **Analysis and gate:** Python detectors compare baseline and current CSV
  inputs; malformed or failed analysis cannot authorize downstream work.
- **Monitored execution:** FastAPI starts the real analysis pipeline, emits
  structured lifecycle events, serves snapshots/history/SSE, and persists the
  resulting report.
- **Run state limits:** The run manager is single-process and bounded. It
  retains up to 50 runs and 100 events per run, with at most four active runs
  and two workers. Restarting the process loses run state.
- **Experiment Lab:** An isolated copy of the input is modified by one of six
  controlled scenarios, analyzed through the actual detectors and gate, then
  corrected and checked using a targeted recovery verification. Experiment
  metadata/events use SQLite; CSV copies and database are local files under
  ignored `reports/`.
- **Pipeline visualization:** The frontend renders a branched dependency
  graph. The branches represent gate-dependent routes; the graph is not proof
  of parallel execution.
- **CI configuration:** GitHub Actions specifies the Python test suite and
  frontend build. Jenkins executes tests and a deterministic protection run;
  its simulated downstream stage runs only for exact `ALLOW`.

## Not implemented

The current checkout does not provide lineage traversal, versioned/governed
baseline promotion, structured investigation graphs, reviewer identity or
approval/release actions, or a durable cross-run incident dashboard. General
monitored-run state is in memory; Experiment Lab persistence does not make
pipeline run history durable.

There is no authentication/authorization layer, multi-worker shared run
store, production downstream connector, or data retention/deletion workflow.
The API is intended for local use and should not be exposed publicly.

## Important storage distinction

- Pipeline reports are files in ignored `reports/`.
- Experiment metadata and its event ledger use
  `reports/experiments.sqlite3`; associated CSV copies are in
  `reports/experiments/`.
- Live run snapshots and recent event history are process memory, not a
  durable database.

