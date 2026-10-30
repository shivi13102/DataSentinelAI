# Judge Q&A

## What problem does DataSentinel AI solve?

It compares a current CSV dataset with a baseline, detects configured data
quality changes, and applies a deterministic gate before the simulated
downstream step can run.

## Why use deterministic checks instead of letting an LLM decide?

The Python analysis and protection gate are authoritative. An LLM can explain
findings but cannot grant downstream permission. This keeps the core decision
reproducible and available when the local model is unavailable.

## What do the decisions mean?

- `ALLOW`: consistent healthy analysis; simulated downstream processing may
  run.
- `REVIEW_REQUIRED`: medium-severity or warning result; downstream remains
  blocked. A real reviewer approval path is not implemented.
- `BLOCK`: high/critical risk or an invalid/untrustworthy analysis; downstream
  remains blocked.

## Is the downstream processor real?

No. It is a simulated operation used to demonstrate enforcement. No external
production system is connected.

## Does a graph branch mean parallel processing?

No. It shows the dependency paths after the gate. The downstream route is
conditional on `ALLOW`; the AI explanation route is advisory.

## What is persisted?

Reports are written to local files. Experiment records and their event ledger
are stored locally in SQLite with isolated CSV copies. Monitored run snapshots
and their recent event history are in process memory and are lost on restart.

## Are lineage and human approvals implemented?

No. Lineage traversal, governed baseline versioning/promotion, reviewer
identity, structured investigation graphs, and approval/release workflows are
not implemented in this version. The Experiment Lab's dataset fingerprints
and recovery checks are not a general lineage service.

## What happens if Ollama is down?

AI reasoning is reported as unavailable/error, but deterministic analysis and
the gate still determine the outcome. The AI response is not a fallback
decision.

## Has Jenkins been verified?

The Jenkinsfile defines the pipeline, but Jenkins was not available in the
local validation environment. A Jenkinsfile is configuration, not evidence
that a Jenkins job ran. GitHub Actions is also only claimed as remotely
verified when the repository's actual Actions run is inspected.

## Is this production-ready?

No. This is a local demonstration. It lacks authentication, durable/distributed
run orchestration, real downstream integration, persistent general incident
history, and operational data-retention controls.

