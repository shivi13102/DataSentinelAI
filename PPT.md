# DataSentinel AI — Presentation Content

## Slide 1 — Cover

**DATASENTINEL AI**

# Reliable data in.  
# Safer pipelines out.

Deterministic data-quality guardrails with an explainable, fail-closed
protection gate.

**LOCAL DEMO / PHASE 4**

Diagram labels: **DETECTION → PROTECTION GATE → DOWNSTREAM**  
**ALLOW / HOLD / BLOCK**  
Only exact **ALLOW** proceeds.

## Slide 2 — The guardrail before downstream

**A deterministic data-quality gate**

Explainable protection before downstream processing.

- **MEASURE** — Compare current data against a baseline.
- **DECIDE** — Only a consistent ALLOW can proceed.
- **EXPLAIN** — AI is optional and advisory.

Decision authority: deterministic Python gate.

## Slide 3 — The problem

**Bad data can look like a successful run.**

Silent shifts can propagate into reports, models, and downstream systems.

- **Detect meaningful change** — Schema, missingness, duplicates, numeric
  drift, and categorical drift.
- **Make a measurable decision** — Findings and severity are computed by
  deterministic Python analysis.
- **Keep the boundary clear** — The language model does not set policy or
  authorize processing.

## Slide 4 — How it works

**A simple, enforceable decision boundary.**

Upload or fixture → measure → gate → conditionally process → report.

- **01 ANALYZE** — Run detectors on baseline and current CSVs.
- **02 GATE** — ALLOW / REVIEW_REQUIRED / BLOCK from measured findings.
- **03 ENFORCE** — Simulated downstream runs only for ALLOW; AI stays
  advisory.

## Slide 5 — Protection outcomes

**Three outcomes. One downstream rule.**

A completed analysis is not the same as permission to continue.

- **ALLOW — Continue** — Healthy, consistent result. Simulated downstream
  step may execute.
- **REVIEW_REQUIRED — Hold** — Medium-risk result. Downstream remains blocked;
  approval is not implemented.
- **BLOCK — Stop** — High/critical or untrustworthy result. Downstream remains
  blocked.

## Slide 6 — Live demonstration

**Three fixture runs make policy visible.**

Tracked, reproducible CSV pairs under `tests/fixtures/protection/`.

- **HEALTHY** — No findings → ALLOW → simulated downstream executes.
- **SUSPICIOUS** — Missing values → REVIEW_REQUIRED → downstream withheld.
- **CRITICAL** — Removed column → BLOCK → downstream withheld.

## Slide 7 — Experiment Lab

**Inject. Observe. Correct. Verify.**

A controlled experiment runs against an isolated dataset copy.

- **Six controlled scenarios** — Missing values, duplicates, schema, numeric
  drift, categorical drift, combined.
- **Real measured outcome** — Actual detectors and the same protection gate
  report findings.
- **Targeted recovery check** — Correction creates a recovered copy and
  checks the target finding again.

## Slide 8 — Honest implementation status

**What works today — and what does not.**

Phase 4 materials describe the checkout as it is, not a roadmap as shipped.

- **IMPLEMENTED** — Detectors + gate; monitored runs + SSE; reports; branched
  graph; Experiment Lab.
- **NOT IMPLEMENTED** — General lineage; governed baselines; investigation
  graph; reviewer approval/release; durable incident history.
- **DEMO BOUNDARIES** — Single-process run state; local experiment storage;
  simulated downstream; no auth or production connector.

## Slide 9 — The takeaway

**A deterministic gate. A human-readable explanation.**

The model can help explain the evidence. It cannot overrule the evidence.

- **LOCAL DEMO READY** — Show healthy, suspicious, critical, and one
  Experiment Lab recovery.
- **CI STATUS** — Python tests and frontend build pass locally. Jenkins/hosted
  Actions require service-side verification.
- **NEXT STEP** — Complete governance, lineage, approvals, and durable
  operations before production claims.
