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
[![Tests](https://img.shields.io/badge/Pytest-54_Passed-success?style=flat&logo=pytest&logoColor=white)](https://docs.pytest.org/)

---

## 1. Executive Summary

In enterprise environments, data moves through complex ETL/ELT pipelines before feeding business dashboards, automated fraud engines, financial reports, and AI/ML algorithms.

A pipeline can execute with exit code `0` (Success) while the **data itself is severely corrupted**:
- **Silent Distribution Shift:** Transaction amounts previously denominated in INR are inadvertently ingested in USD, distorting financial calculations 80-fold.
- **Null Invariant Ruptures:** Critical features (e.g. `customer_age`) experience sudden null spikes due to an unannounced upstream schema migration.
- **Duplication Spikes:** Ingestion retry loops replay records without deduplication, inflating metric volumes.
- **Category Drift:** Unhandled enum tokens (e.g., `'Unknown'`) bypass upstream validation, contaminating downstream segmentation.

**DataSentinel AI** provides continuous data observability by comparing incoming datasets against trusted reference baselines. It pairs **deterministic mathematical detectors** (Kolmogorov-Smirnov, Chi-square, Total Variation Distance) with a **LangGraph-orchestrated reasoning agent powered by Gemma 3 1B**, enforcing an **authoritative, fail-closed Protection Gate** (`ALLOW`, `REVIEW_REQUIRED`, `BLOCK`).

---

## 2. The Four Pillars of DataSentinel AI

| Stage | Mechanism | Responsibility |
| :--- | :--- | :--- |
| **1. Detect** | Python & SciPy | Calculates exact empirical drift, p-values, missingness deltas, and row invariant hashes in-memory. Zero LLM hallucinations in numerical calculations. |
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
       │   • Exact Row Invariant Hashes  │
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
   - Multi-phase progress visualization (`Validating` $\to$ `Detecting` $\to$ `Reasoning` $\to$ `Gating`).

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
├── data/
│   ├── processed/
│   └── raw/
│       ├── baseline.csv                     # Trusted reference dataset
│       └── current.csv                      # Investigated incoming dataset
├── frontend/                                # Enterprise React + TypeScript UI
│   ├── src/
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
│   │   ├── App.tsx                          # App shell, context & navigation
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── reports/                                 # Saved immutable JSON audit reports
├── scripts/                                 # Data generation & test scripts
├── src/
│   ├── agents/
│   │   └── reasoning_agent.py               # Gemma 3 1B structured Ollama client
│   ├── detectors/                           # Statistical detection modules
│   │   ├── categorical_drift_detector.py    # TVD & Chi-square
│   │   ├── distribution_detector.py         # Two-sample Kolmogorov-Smirnov
│   │   ├── duplicate_detector.py            # Row hash invariant comparison
│   │   ├── missing_value_detector.py        # Null-rate differential analysis
│   │   └── schema_detector.py               # Structural column set changes
│   ├── graph/
│   │   └── workflow.py                      # LangGraph StateGraph orchestration
│   ├── utils/
│   │   └── data_loader.py                   # Pandas CSV loader
│   ├── analysis_engine.py                   # Deterministic detection coordinator
│   └── protection_gate.py                   # Fail-closed pipeline safety gate
├── tests/                                   # Full pytest verification suite (54 tests)
├── api.py                                   # FastAPI REST service
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

#### Backend Test Suite (54 Tests)
```bash
.\.venv\Scripts\pytest.exe
```

#### Frontend Typecheck & Build
```bash
cd frontend
npm run build
```

---

## 8. API Specification

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/health` | `GET` | Returns service status, version, configured AI model, and engine metadata. |
| `/api/analyze` | `POST` | Accepts multipart form data (`baseline_file`, `current_file`). Runs full detection, reasoning, and gating workflow. |
| `/api/reports` | `GET` | Lists all saved analysis reports in reverse chronological order. |
| `/api/reports/{id}` | `GET` | Downloads the full, immutable JSON report for a given report ID. |

---

## 9. Security & Compliance

- **Zero External Telemetry:** All statistical computations occur in local memory.
- **Local AI Privacy:** Gemma operates locally via Ollama; no proprietary datasets are transmitted over external networks.
- **Fail-Closed Safety:** If the gate fails or receives corrupted inputs, downstream processing is blocked by default.
- **Input Sanitization:** Uploaded CSVs are validated for structure and length before memory allocation.
- **Path Traversal Protection:** Report download identifiers are strictly validated against an alphanumeric allowlist.

---

## 10. License

This project is licensed under the Apache 2.0 License.
