# DataSentinel AI

> **AI-Powered Data Observability & Pipeline Protection Platform**  
> *Detect silent data failures before they reach downstream analytics, ML models, and executive dashboards.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-FF6F00?style=flat)](https://github.com/langchain-ai/langgraph)
[![Ollama](https://img.shields.io/badge/Ollama-Gemma_3_1B-white?style=flat&logo=ollama&logoColor=black)](https://ollama.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v4-38B2AC?style=flat&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-pytest-success?style=flat&logo=pytest&logoColor=white)](https://docs.pytest.org/)

---

## 1. Executive Summary

In enterprise environments, data moves through complex ETL/ELT pipelines before feeding business dashboards, automated fraud engines, financial reports, and AI/ML algorithms.

A pipeline can execute with exit code `0` (Success) while the **data itself is severely corrupted**:
- **Silent Distribution Shift:** Transaction amounts previously denominated in INR are inadvertently ingested in USD, distorting financial calculations 80-fold.
- **Null Invariant Ruptures:** Critical features (e.g. `customer_age`) experience sudden null spikes due to an unannounced upstream schema migration.
- **Duplication Spikes:** Ingestion retry loops replay records without deduplication, inflating metric volumes.
- **Category Drift:** Unhandled enum tokens (e.g., `'Unknown'`) bypass upstream validation, contaminating downstream segmentation.

**DataSentinel AI** provides data observability by comparing uploaded datasets against trusted reference baselines. It pairs **deterministic detectors** (Kolmogorov-Smirnov, Chi-square, and Total Variation Distance) with an optional **LangGraph-orchestrated reasoning agent powered by Gemma 3 1B**, enforcing an **authoritative, fail-closed Protection Gate** (`ALLOW`, `REVIEW_REQUIRED`, `BLOCK`).

---

## 2. The Four Pillars of DataSentinel AI

| Stage | Mechanism | Responsibility |
| :--- | :--- | :--- |
| **1. Detect** | Python & SciPy | Calculates distribution statistics, p-values, missingness changes, duplicate-row rates, categorical drift, and schema differences. The LLM does not calculate measured values. |
| **2. Investigate** | LangGraph StateGraph | Orchestrates workflow state across data profiling, anomaly detection, AI investigation, and gate evaluation nodes. |
| **3. Explain** | Gemma 3 1B (via Ollama) | Analyzes measured facts to formulate unverified root-cause hypotheses, assess business impacts, and recommend verification checklists in plain language. |
| **4. Protect** | Deterministic Safety Gate | Authoritative gate evaluates finding severities. If critical risks are detected, it issues a **BLOCK** decision that **cannot be overridden by the LLM**. |

---

## 3. Architecture & Data Flow

```
[ Trusted Baseline CSV ]    [ Incoming Current CSV ]
            │                          │
            └───────────┬──────────────┘
                        ▼
       ┌─────────────────────────────────┐
       │   1. Data Validation Engine     │
       │   (SciPy, NumPy, Pandas)        │
       │   • Kolmogorov-Smirnov Test     │
       │   • Chi-Square & TVD Drift      │
       │   • Null Invariant Deltas       │
       │   • Duplicate-Row Rates         │
       └────────────────┬────────────────┘
                        │ Structured Facts
                        ▼
       ┌─────────────────────────────────┐
       │   2. LangGraph Workflow Graph   │
       │   (DataSentinelState Orchestr.) │
       └────────┬───────────────┬────────┘
                │               │
  Evidence Dict │               │ Analysis Results
                ▼               ▼
 ┌──────────────────────┐  ┌──────────────────────┐
 │  3. Reasoning Agent  │  │ 4. Protection Gate   │
 │  Gemma 3 1B (Ollama) │  │ Deterministic Rules  │
 │  • Root Hypotheses   │  │ • ALLOW              │
 │  • Business Impact   │  │ • REVIEW_REQUIRED    │
 │  • Remediation Steps │  │ • BLOCK              │
 └──────────────┬───────┘  └──────────┬───────────┘
                │                     │ (Authoritative)
                └──────────┬──────────┘
                           ▼
             ┌───────────────────────────┐
             │   5. Unified JSON Audit   │
             │   & Observability UI      │
             └───────────────────────────┘
```

### Why Deterministic Gating Over Pure LLMs?
LLMs are creative reasoners, but they can hallucinate or downplay statistical severity. In DataSentinel AI:
1. **Math is executed by Python:** KS p-values, mean shifts, and null ratios are computed using standard statistical libraries.
2. **The Protection Gate is absolute:** If an anomaly is ranked `critical` or high-severity rules trigger, the decision is **BLOCK**. An LLM explanation can never override this decision.
3. **Fail-Closed Design:** If Ollama or the reasoning agent encounters an error, the system records the failure but continues to enforce pipeline protection.

---

## 4. Real-World Demonstration Case

The repository includes a verified real-world incident dataset (`data/raw/baseline.csv` vs `data/raw/current.csv`):

| Finding | Column | Evidence | Severity | Detection Method |
| :--- | :--- | :--- | :--- | :--- |
| **Missing Values** | `customer_age` | Missingness jumped from **0.00% to 30.18%** (332 affected records). | `HIGH` | `missing_value_percentage` |
| **Duplicate Records** | Global | Duplicates increased from **0.00% to 9.09%** (100 duplicated rows). | `MEDIUM` | `duplicate_row_comparison` |
| **Distribution Drift**| `transaction_amount` | Baseline mean of **497.33** shifted to **1490.27** (KS stat: 0.963, p-value < reported precision). | `HIGH` | `summary_statistics_and_ks_test` |
| **Categorical Drift** | `payment_status` | Introduction of new **`Unknown`** category (TVD: 0.318, $\chi^2$: 382.68). | `HIGH` | `total_variation_distance_and_chi_square` |

**Outcome:**
- **Overall Status:** `CRITICAL`
- **Protection Decision:** `BLOCK`
- **Downstream Processing:** Not permitted automatically
- **Human Review:** Mandatory before production release

---

## 5. Enterprise Frontend Workspace

The frontend is designed for cybersecurity operations centers and data infrastructure teams:

1. **Command Centre (Overview):**
   - High-density observability metrics (Health Score, High-Severity counts, Reference Pipeline state).
   - Prominent Protection Gate status banner.
   - Severity distribution donut and historical run trends.
   - Recent incident streams and AI investigation preview.

2. **Pipeline Monitor:**
   - Visual data topology: `Source Dataset` $\to$ `Transformation` $\to$ `Data Validation` $\to$ `AI Investigation` $\to$ `Downstream Analytics`.
   - Node-level inspection drawer displaying raw statistical evidence.

3. **Dataset Analysis:**
   - Drag-and-drop dual-file uploader with size, extension, and empty file validation.
   - Upload status while the backend runs analysis; granular backend progress events are not currently available.

4. **Anomaly Explorer:**
   - Multi-criteria filtering by severity (`High`, `Medium`, `Low`), detector type, and keyword search.
   - Interactive evidence slide-over drawer with side-by-side baseline vs. current comparisons.

5. **AI Investigation Workspace:**
   - Dedicated incident analysis dashboard (Incident summary, Root-cause hypotheses with confidence ratings, Business impacts, and remediation checklist).
   - Clear visual distinction between measured facts and unverified AI hypotheses.

6. **Reports & Audit Logs:**
   - Complete historical ledger queried via `GET /api/reports`.
   - One-click inspection and JSON export (`GET /api/reports/{id}`).

7. **System Configuration (Settings):**
   - Dynamic API base URL configuration with live verification against `/api/health`.
   - Engine telemetry and statistical detector registry.

---

## 6. Project Structure

```text
DataSentinelAI/
├── .gitignore
├── .github/
│   └── workflows/                         # Python tests and frontend build
├── data/
│   ├── processed/
│   └── raw/
│       ├── baseline.csv                     # Trusted reference dataset
│       └── current.csv                      # Investigated incoming dataset
├── frontend/                                # Enterprise React + TypeScript UI
│   ├── public/
│   │   ├── favicon.svg
│   │   └── icons.svg
│   ├── src/
│   │   ├── assets/
│   │   ├── App.css
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── layout/                      # Sidebar and Topbar navigation
│   │   │   └── ui/                          # Badge, Card, Button, Drawer, Toast
│   │   ├── lib/
│   │   │   ├── api.ts                       # Typed REST client
│   │   │   ├── utils.ts                     # Scoring, formatting, and download utilities
│   │   │   └── react-is-shim.ts             # ESM compatibility layer
│   │   ├── pages/
│   │   │   ├── Overview.tsx                 # Command Centre
│   │   │   ├── PipelineMonitor.tsx          # Topology Node Observability
│   │   │   ├── DatasetAnalysis.tsx          # Dual CSV Ingestion
│   │   │   ├── AnomalyExplorer.tsx          # Filterable Evidence Grid
│   │   │   ├── AIInvestigation.tsx          # Gemma Reasoning Workspace
│   │   │   ├── Reports.tsx                  # Historical Audit Ledger
│   │   │   └── Settings.tsx                 # Telemetry & Config
│   │   ├── types/
│   │   │   └── api.ts                       # Strict TypeScript backend schemas
│   │   ├── index.css
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── reports/                                 # Generated JSON analysis/evaluation reports
├── scripts/
│   ├── evaluate_protection.py               # Metrics and evaluation reports
│   ├── generate_protection_fixtures.py      # Deterministic scenario generator
│   └── run_pipeline.py                      # CLI analysis and run artifacts
├── src/
│   ├── agents/
│   │   └── reasoning_agent.py               # Gemma 3 1B structured Ollama client
│   ├── detectors/                           # Statistical detection modules
│   │   ├── categorical_drift_detector.py    # TVD & Chi-square
│   │   ├── distribution_detector.py         # Two-sample Kolmogorov-Smirnov
│   │   ├── duplicate_detector.py            # Duplicate-row rate comparison
│   │   ├── missing_value_detector.py        # Null-rate differential analysis
│   │   └── schema_detector.py               # Structural column set changes
│   ├── graph/
│   │   └── workflow.py                      # LangGraph StateGraph orchestration
│   ├── utils/
│   │   └── data_loader.py                   # Pandas CSV loader
│   ├── analysis_engine.py                   # Deterministic detection coordinator
│   └── protection_gate.py                   # Fail-closed pipeline safety gate
├── tests/
│   ├── fixtures/protection/                 # Scenario CSV pairs and manifest
│   ├── test_api.py
│   ├── test_evaluation.py
│   ├── test_ollama_reasoning.py
│   ├── test_protection_gate.py
│   └── ...                                  # Detector and integration tests
├── Jenkinsfile                              # Build-specific decision enforcement
├── api.py                                   # FastAPI REST service
├── app.py                                   # Streamlit interface
├── README.md
└── requirements.txt
```

---

## 7. Quickstart Guide

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- (Optional) [Ollama](https://ollama.com/) with `gemma3:1b` for local AI reasoning:
  ```bash
  ollama pull gemma3:1b
  ```

---

### Step 1: Start the Backend API

```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1    # On Windows
# source .venv/bin/activate       # On Linux/macOS

# Install dependencies if not already present
pip install -r requirements.txt

# Run FastAPI server
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

Backend will be online at: `http://127.0.0.1:8000`  
Interactive Swagger docs: `http://127.0.0.1:8000/docs`

---

### Step 2: Start the Frontend Application

```bash
cd frontend

# Install packages
npm install

# Start Vite dev server
npm run dev
```

Open your browser at: `http://127.0.0.1:5173`

---

### Step 3: Run the Test Suites

#### Backend Test Suite
```bash
python -m pytest -v
```

#### Frontend Typecheck & Build
```bash
cd frontend
npm run build
```

---

## 8. Protection policy and reproducible scenarios

The Python analysis engine is authoritative. The gate accepts `healthy`,
`warning`, and `critical` analysis statuses; failed or incomplete analyses
block. A critical status or a high/critical finding produces `BLOCK`; medium
findings produce `REVIEW_REQUIRED`; only a consistent healthy result with no
medium-or-higher finding produces `ALLOW`. Missing, unknown, malformed, or
contradictory results cannot authorize downstream processing.

| Detector | Measured rule | Severity |
|---|---|---|
| Schema | Added column: medium; removed column or incompatible dtype: high | Medium/high |
| Missing values | Increase of at least 10 percentage points; high at 30 points or an entirely missing current column | Medium/high |
| Duplicates | Duplicate-rate increase of at least 5 percentage points; high at 20 points | Medium/high |
| Numerical distribution | At least 20% relative mean change, a KS p-value below 0.05, or a range change; high when KS is significant or mean change is at least 50% | Medium/high |
| Categorical distribution | Chi-square p-value below 0.05 and total variation distance at least 0.10; high at 0.30 TVD | Medium/high |

Regenerate the deterministic fixture pairs and run the real analysis, gate,
and report checks:

```powershell
python scripts\generate_protection_fixtures.py
python -m pytest tests\test_protection_scenarios.py tests\test_run_pipeline.py -v
```

Fixture pairs and expected finding types, severities, and decisions are defined
in `tests/fixtures/protection/evaluation_manifest.json`. Cases cover healthy
data, missing values, removed schema, duplicates, numerical drift, categorical
drift, and simultaneous anomalies.

For an interactive upload demonstration, start the backend and frontend using
the Quickstart commands, open **Dataset Analysis**, and select these fixture
pairs from `tests/fixtures/protection/`:

| Baseline | Current | Expected protection result |
|---|---|---|
| `healthy_baseline.csv` | `healthy_current.csv` | `ALLOW` |
| `suspicious_baseline.csv` | `suspicious_current.csv` | `REVIEW_REQUIRED` |
| `critical_baseline.csv` | `critical_current.csv` | `BLOCK` |

The generated report appears in the Reports page and contains the same
deterministic finding and protection result. When Ollama is available, the
report also records the actual model response and duration; otherwise the
deterministic report remains available with an AI error status.

`REVIEW_REQUIRED` remains blocked: the project does not currently implement an
authorized human-approval workflow. The Jenkins downstream operation is a
demonstration echo only; no external production system is connected.

## 9. Evaluation

The evaluation executes the real detectors and gate on the fixture manifest.
It reports finding-type detection recall, case-level false-positive rate over
clean fixtures, decision accuracy, deterministic analysis latency, local AI
request latency/status, and downstream-enforcement reliability. It writes
`reports/evaluation/metrics.json` and
`reports/evaluation/evaluation_report.md`; generated reports are ignored by Git.

```powershell
python scripts\evaluate_protection.py
```

By default, the script attempts one genuine local Ollama inference using
`gemma3:1b`. Use `--skip-ai` to evaluate deterministic behavior without
Ollama; AI latency is then unavailable, not zero. The synthetic fixture set
is small and is not evidence of production performance or readiness. The
reports include metric definitions and limitations.

## 10. API Specification

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/health` | `GET` | Returns service status, version, configured AI model, and engine metadata. |
| `/api/analyze` | `POST` | Accepts multipart form data (`baseline_file`, `current_file`), each limited to 50 MiB. Runs detection, optional reasoning, gating, and report persistence. |
| `/api/reports` | `GET` | Lists all saved analysis reports in reverse chronological order. |
| `/api/reports/{id}` | `GET` | Downloads a saved JSON report using a generated report ID. |

---

## 11. Jenkins and CI

GitHub Actions runs the Python tests and frontend production build. The Jenkins
pipeline offers `current`, `healthy`, `suspicious`, and `critical` scenarios.
It clears only the current build's generated artifact directory, reads that
build's decision file, and rechecks the exact decision at the simulated
downstream boundary. `ALLOW` permits the demonstration step; `REVIEW_REQUIRED`
and `BLOCK` skip it and mark the build unstable; missing or invalid decision
artifacts fail closed. Reports and decision artifacts are archived when
available.

No live Jenkins controller was available for verification in this environment.
The historical `UNSET` report could not be tied to a definitive Jenkins runtime
cause because its console log was not available. The previous source relied on
a shared decision-file path and a mutable environment variable across stages;
the pipeline now uses a build-specific artifact, clears only that build's
generated output before execution, and re-reads the file at enforcement rather
than trusting an environment-variable value.

## 12. Security & Compliance

- **Zero External Telemetry:** All statistical computations occur in local memory.
- **Local AI Privacy:** With the default local API and Ollama configuration, uploaded data stays on this machine. Configuring a remote API base URL sends uploads to that server.
- **Fail-Closed Safety:** If the gate fails or receives corrupted inputs, downstream processing is blocked by default.
- **Input Validation:** CSV uploads must be UTF-8, parseable, non-empty, have unique non-empty headers, and remain within the 50 MiB per-file API limit.
- **Path Traversal Protection:** Download IDs are restricted to generated identifier characters, and resolved report files must remain under the reports directory.
- **AI boundaries:** Findings remain measured evidence; model text is an unverified investigation hypothesis and cannot authorize processing.

---

## 13. License

This project is licensed under the Apache 2.0 License.
