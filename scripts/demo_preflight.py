from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
CORE_FAILURES = 0
WARNINGS = 0
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def report(
    name: str,
    status: str,
    message: str,
    suggestion: str | None = None,
    *,
    core: bool = False,
) -> None:
    global CORE_FAILURES, WARNINGS
    print(f"[{status}] {name}: {message}")
    if suggestion:
        print(f"       Suggested fix: {suggestion}")
    if status == "FAIL" and core:
        CORE_FAILURES += 1
    elif status == "WARNING":
        WARNINGS += 1


def check(
    name: str,
    action: Callable[[], str],
    *,
    suggestion: str,
    core: bool = True,
) -> bool:
    try:
        detail = action()
    except Exception as exc:
        report(
            name,
            "FAIL" if core else "WARNING",
            f"{type(exc).__name__}: {exc}",
            suggestion,
            core=core,
        )
        return False
    report(name, "PASS", detail)
    return True


def _python_environment() -> str:
    if sys.version_info < (3, 11):
        raise RuntimeError(f"Python 3.11+ required; found {sys.version.split()[0]}.")
    environment = "virtual environment" if sys.prefix != sys.base_prefix else "system interpreter"
    return f"Python {sys.version.split()[0]} ({environment})"


def _virtual_environment() -> str:
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("The active interpreter is not running inside a virtual environment.")
    return f"Active virtual environment: {sys.prefix}"


def _required_packages() -> str:
    required = (
        "fastapi",
        "uvicorn",
        "pandas",
        "numpy",
        "scipy",
        "requests",
        "langgraph",
        "pytest",
        "multipart",
        "sklearn",
        "streamlit",
        "plotly",
    )
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError(f"Missing packages: {', '.join(missing)}")
    return f"{len(required)} required Python packages importable"


def _backend() -> str:
    api = importlib.import_module("api")
    from fastapi.testclient import TestClient

    route_names = {
        getattr(route, "path", "")
        for route in api.app.routes
    }
    required_routes = {"/api/health", "/api/health/ai", "/api/analyze"}
    missing = required_routes - route_names
    if missing:
        raise RuntimeError(f"Required API routes missing: {sorted(missing)}")
    response = TestClient(api.app).get("/api/health")
    if response.status_code != 200 or response.json().get("status") != "online":
        raise RuntimeError(f"Backend health route returned HTTP {response.status_code}.")
    if response.json().get("analysis_engine_status") != "available":
        raise RuntimeError(
            "The API responded, but its synthetic analysis-engine health check failed."
        )
    return f"FastAPI imports; {len(route_names)} routes registered; health responds"


def _frontend() -> str:
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        raise RuntimeError("Node.js and npm must be available on PATH.")
    version = subprocess.run(
        [node, "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    parsed_version = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not parsed_version:
        raise RuntimeError(f"Unrecognized Node.js version: {version}")
    major, minor = int(parsed_version.group(1)), int(parsed_version.group(2))
    supported = (
        (major == 20 and minor >= 19)
        or (major == 22 and minor >= 12)
        or major > 22
    )
    if not supported:
        raise RuntimeError(
            f"Vite 8 requires Node 20.19+ or 22.12+; found {version}."
        )
    if not (FRONTEND_DIR / "node_modules").is_dir():
        raise RuntimeError("frontend/node_modules is missing.")
    api_client = (FRONTEND_DIR / "src" / "lib" / "api.ts").read_text(
        encoding="utf-8"
    )
    if "http://127.0.0.1:8000" not in api_client:
        raise RuntimeError("The default frontend API URL is not localhost.")
    build = subprocess.run(
        [npm, "run", "build"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if build.returncode:
        tail = "\n".join((build.stdout + build.stderr).splitlines()[-25:])
        raise RuntimeError(f"Frontend build failed (exit {build.returncode}):\n{tail}")
    return f"Node {version}; dependencies present; localhost API default; production build passed"


def _fixtures_and_protection() -> str:
    import pandas as pd

    from src.analysis_engine import analyze_datasets
    from src.protection_gate import enforce_downstream, evaluate_pipeline_gate
    from src.utils.data_loader import load_csv

    baseline = pd.DataFrame(
        {
            "record_key": range(100),
            "measure_value": [index % 10 for index in range(100)],
            "segment_code": ["A" if index % 2 else "B" for index in range(100)],
        }
    )
    healthy = baseline.copy(deep=True)
    suspicious = baseline.copy(deep=True)
    suspicious.loc[:19, "measure_value"] = float("nan")
    critical = baseline.drop(columns=["measure_value"])

    cases = (
        ("healthy", healthy, "ALLOW"),
        ("missing values", suspicious, "REVIEW_REQUIRED"),
        ("schema mismatch", critical, "BLOCK"),
    )
    results = []
    with tempfile.TemporaryDirectory(prefix="datasentinel-fixtures-") as directory:
        fixture_dir = Path(directory)
        baseline_path = fixture_dir / "baseline.csv"
        baseline.to_csv(baseline_path, index=False)
        loaded_baseline = load_csv(baseline_path)
        for label, current, expected in cases:
            current_path = fixture_dir / f"{label.replace(' ', '_')}.csv"
            current.to_csv(current_path, index=False)
            loaded_current = load_csv(current_path)
            analysis = analyze_datasets(
                baseline=loaded_baseline,
                current=loaded_current,
            )
            decision = evaluate_pipeline_gate(analysis)
            if decision["decision"] != expected:
                raise RuntimeError(
                    f"Synthetic {label} case returned {decision['decision']}; expected {expected}."
                )
            called = []
            executed, _ = enforce_downstream(
                decision,
                lambda: called.append(True),
            )
            should_execute = expected == "ALLOW"
            if executed is not should_execute or bool(called) is not should_execute:
                raise RuntimeError(
                    f"Downstream policy failed for synthetic {label} case."
                )
            results.append(f"{label}={expected}")
    return "Temporary generic CSVs loaded through the project loader: " + ", ".join(results)


def _workflow_and_report() -> str:
    import pandas as pd

    import api
    from src.graph.workflow import data_sentinel_workflow

    frame = pd.DataFrame(
        {
            "record_key": range(20),
            "measure_value": [index % 5 for index in range(20)],
            "segment_code": ["A" if index % 2 else "B" for index in range(20)],
        }
    )
    with tempfile.TemporaryDirectory(prefix="datasentinel-preflight-") as directory:
        reports_dir = Path(directory) / "reports"
        with (
            patch.object(api, "REPORTS_DIR", reports_dir),
            patch(
                "src.graph.workflow.explain_findings",
                return_value={
                    "status": "error",
                    "error": "AI intentionally skipped by preflight.",
                },
            ),
        ):
            result = data_sentinel_workflow.invoke(
                {"baseline": frame, "current": frame.copy(deep=True)}
            )
            final_report = result.get("final_report")
            if not isinstance(final_report, dict):
                raise RuntimeError("LangGraph did not build a final report.")
            if final_report["protection"]["decision"] != "ALLOW":
                raise RuntimeError("LangGraph synthetic healthy case was not ALLOW.")
            if final_report["ai_reasoning"]["status"] != "error":
                raise RuntimeError("LangGraph preflight fallback was not preserved.")
            report_id = api.save_report(final_report)
            saved_path = reports_dir / f"analysis_{report_id}.json"
            saved = json.loads(saved_path.read_text(encoding="utf-8"))
            if saved["protection"]["decision"] != "ALLOW":
                raise RuntimeError("Saved report did not preserve the gate decision.")
    return "LangGraph execution and isolated temporary report persistence passed; AI fallback did not alter ALLOW"


def _storage() -> str:
    from src.experiments.store import ExperimentStore

    with tempfile.TemporaryDirectory(prefix="datasentinel-storage-") as directory:
        reports_dir = Path(directory) / "reports"
        store = ExperimentStore(reports_dir)
        if not (reports_dir / "experiments.sqlite3").is_file():
            raise RuntimeError("Experiment SQLite store was not initialized.")
        if not store.list(limit=1) == []:
            raise RuntimeError("New temporary experiment store should be empty.")
    return "Temporary report directory writable; SQLite experiment store initializes"


def _ci_configuration() -> str:
    workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    jenkinsfile = PROJECT_ROOT / "Jenkinsfile"
    if not workflow.is_file() or not jenkinsfile.is_file():
        raise RuntimeError("GitHub Actions workflow or Jenkinsfile is missing.")
    github_text = workflow.read_text(encoding="utf-8")
    jenkins_text = jenkinsfile.read_text(encoding="utf-8")
    if "python-tests:" not in github_text or "frontend-build:" not in github_text:
        raise RuntimeError("GitHub Actions test/build jobs are not configured.")
    if "Enforce Protection Policy" not in jenkins_text:
        raise RuntimeError("Jenkins protection enforcement stage is missing.")
    return "GitHub Actions and Jenkins configuration files present; no remote job executed"


def _ai_health() -> str:
    from src.agents.reasoning_agent import check_ai_health

    result = check_ai_health()
    details = (
        f"provider={result['provider']}, model={result['model'] or 'unset'}, "
        f"status={result['status']}"
    )
    if result["response_time_ms"] is not None:
        details += f", inference_ms={result['response_time_ms']}"
    if result["status"] != "AVAILABLE":
        raise RuntimeError(
            f"{details}; {result.get('error') or 'Install/configure local Ollama manually.'}"
        )
    return details


def _ai_reasoning() -> str:
    import pandas as pd

    from src.agents.reasoning_agent import explain_findings
    from src.analysis_engine import analyze_datasets

    baseline = pd.DataFrame(
        {
            "record_key": range(100),
            "measurement_reading": [index % 10 for index in range(100)],
            "category_token": [
                "north" if index % 2 else "south"
                for index in range(100)
            ],
        }
    )
    current = baseline.copy(deep=True)
    current.loc[:19, "measurement_reading"] = float("nan")
    analysis = analyze_datasets(baseline=baseline, current=current)
    if not analysis.get("findings"):
        raise RuntimeError("The synthetic AI preflight did not produce detector findings.")
    reasoning = explain_findings(analysis)
    if reasoning.get("status") != "success":
        raise RuntimeError(
            "Local AI reasoning did not complete successfully: "
            f"{reasoning.get('error', reasoning.get('status', 'unknown error'))}"
        )
    hypothesis_count = len(
        reasoning.get("explanation", {}).get("root_cause_hypotheses", [])
    )
    if hypothesis_count != len(analysis["findings"]):
        raise RuntimeError("AI reasoning did not return one hypothesis per finding.")
    return (
        f"Gemma returned a schema-valid explanation for "
        f"{hypothesis_count} synthetic detector finding(s)"
    )


def _ollama_cli() -> str:
    executable = shutil.which("ollama")
    if not executable:
        raise RuntimeError("Ollama CLI was not found on PATH.")
    return f"Ollama CLI found at {executable}"


def _jenkins_connectivity() -> str:
    url = os.environ.get("DATASENTINEL_JENKINS_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATASENTINEL_JENKINS_URL is not configured; Jenkins was not contacted."
        )
    import requests

    started = time.perf_counter()
    response = requests.get(url, timeout=3)
    response.raise_for_status()
    elapsed = round((time.perf_counter() - started) * 1000)
    return f"Configured Jenkins URL responded in {elapsed} ms; no credentials were sent"


def main() -> int:
    print("DATASENTINEL AI - DEMO READINESS CHECK\n")
    check(
        "Python environment",
        _python_environment,
        suggestion="Use .\\.venv\\Scripts\\python.exe on Windows.",
    )
    check(
        "Virtual environment",
        _virtual_environment,
        suggestion="Activate the project venv or run .\\.venv\\Scripts\\python.exe.",
        core=False,
    )
    check(
        "Required Python packages",
        _required_packages,
        suggestion="Activate the project venv and install requirements.txt.",
    )
    check(
        "Backend imports and health route",
        _backend,
        suggestion="Fix the reported import/configuration error, then retry.",
    )
    check(
        "Frontend dependencies and production build",
        _frontend,
        suggestion="Run npm ci from frontend, then npm run build.",
    )
    check(
        "Generic deterministic analysis and gate",
        _fixtures_and_protection,
        suggestion="Inspect detector/gate errors; only temporary synthetic fixtures are used.",
    )
    check(
        "LangGraph and report persistence",
        _workflow_and_report,
        suggestion="Inspect the LangGraph workflow and reports directory permissions.",
    )
    check(
        "Local storage",
        _storage,
        suggestion="Check temporary directory permissions and SQLite support.",
    )
    check(
        "Ollama installation",
        _ollama_cli,
        suggestion="Install Ollama before the event; deterministic analysis works without it.",
        core=False,
    )
    check(
        "Local Ollama and actual inference",
        _ai_health,
        suggestion="Start Ollama locally, run ollama pull gemma4:e2b manually if needed, then rerun.",
        core=False,
    )
    check(
        "AI reasoning with synthetic evidence",
        _ai_reasoning,
        suggestion="Check Ollama/model availability, then inspect the reported structured-response error.",
        core=False,
    )
    check(
        "CI/CD configuration",
        _ci_configuration,
        suggestion="Restore the GitHub Actions workflow and Jenkinsfile.",
    )
    check(
        "Jenkins connectivity",
        _jenkins_connectivity,
        suggestion="Set DATASENTINEL_JENKINS_URL only when Jenkins is expected to be reachable.",
        core=False,
    )

    if CORE_FAILURES:
        print(f"\nOVERALL: NOT READY ({CORE_FAILURES} core check(s) failed)")
        return 1
    if WARNINGS:
        print(f"\nOVERALL: READY WITH WARNINGS ({WARNINGS} optional check(s) need attention)")
        return 0
    print("\nOVERALL: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
