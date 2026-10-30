from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

# Ensure the project root is available for imports when this script
# is executed directly from the scripts directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis_engine import analyze_datasets
from src.protection_gate import evaluate_pipeline_gate
from src.utils.data_loader import load_csv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"


def json_safe(value: Any) -> Any:
    """Convert common NumPy and pandas values into JSON-compatible values."""

    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        number = float(value)
        return number if np.isfinite(number) else None

    if isinstance(value, np.bool_):
        return bool(value)

    if isinstance(value, float):
        return value if np.isfinite(value) else None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if value is pd.NA or value is pd.NaT:
        return None

    if isinstance(value, Path):
        return str(value)

    return value


def run_pipeline(
    baseline_path: Path,
    current_path: Path,
    *,
    artifact_dir: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Analyze two datasets and apply DataSentinel's existing protection gate."""

    run_id = run_id or uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", run_id):
        raise ValueError("run_id may contain only letters, numbers, '.', '_' and '-'.")

    run_artifact_dir = artifact_dir or REPORTS_DIR / "runs" / run_id
    run_artifact_dir.mkdir(parents=True, exist_ok=True)
    decision_path = run_artifact_dir / "jenkins_decision.txt"
    decision_path.unlink(missing_ok=True)

    if not baseline_path.is_file():
        raise FileNotFoundError(f"Baseline CSV not found: {baseline_path}")

    if not current_path.is_file():
        raise FileNotFoundError(f"Current CSV not found: {current_path}")

    print("=" * 60)
    print("DATASENTINEL AI - PIPELINE EXECUTION")
    print("=" * 60)

    print("\n[1/4] Loading datasets...")

    baseline = load_csv(baseline_path)
    current = load_csv(current_path)

    print(f"Baseline dataset: {baseline.shape[0]} rows, {baseline.shape[1]} columns")
    print(f"Current dataset:  {current.shape[0]} rows, {current.shape[1]} columns")

    print("\n[2/4] Running deterministic data quality analysis...")

    analysis_results = analyze_datasets(
        baseline=baseline,
        current=current,
    )

    if not isinstance(analysis_results, dict):
        raise RuntimeError("The analysis engine did not return a valid result.")

    print(f"Analysis status: {analysis_results.get('overall_status', 'unknown')}")

    findings = analysis_results.get("findings", [])

    if not isinstance(findings, list):
        raise RuntimeError("The analysis engine returned an invalid findings list.")

    print(f"Findings detected: {len(findings)}")

    print("\n[3/4] Evaluating the protection gate...")

    protection_results = evaluate_pipeline_gate(analysis_results)
    decision = protection_results.get("decision")

    if decision not in {"ALLOW", "REVIEW_REQUIRED", "BLOCK"}:
        raise RuntimeError(f"Unexpected protection decision: {decision!r}")

    print(f"Protection decision: {decision}")
    print(
        "Downstream processing allowed:",
        protection_results.get("downstream_processing_allowed", False),
    )

    print("\n[4/4] Generating JSON report...")

    generated_at = datetime.now(timezone.utc)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    report_path = run_artifact_dir / (
        f"jenkins_analysis_{timestamp}_{run_id}_{uuid4().hex[:8]}.json"
    )

    report = {
        "report_type": "jenkins_pipeline",
        "run_id": run_id,
        "generated_at": generated_at.isoformat(),
        "workflow_status": "success",
        "overall_status": analysis_results.get("overall_status", "unknown"),
        "dataset_metadata": {
            "baseline": {
                "filename": baseline_path.name,
                "rows": int(len(baseline)),
                "columns": int(len(baseline.columns)),
            },
            "current": {
                "filename": current_path.name,
                "rows": int(len(current)),
                "columns": int(len(current.columns)),
            },
        },
        "analysis": analysis_results,
        "ai_reasoning": {
            "status": "skipped",
            "reason": (
                "Jenkins uses deterministic Python findings and the protection "
                "gate. Local Ollama/Gemma reasoning is not required for this run."
            ),
        },
        "protection": protection_results,
        "human_review_required": protection_results.get(
            "human_review_required", True
        ),
    }

    safe_report = json_safe(report)

    report_json = json.dumps(
        safe_report,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )
    _write_atomically(report_path, report_json)
    _write_atomically(decision_path, f"{decision}\n")

    print(f"Report saved: {report_path}")
    print(f"Decision saved: {decision_path}")
    print(f"\nDATASENTINEL_DECISION={decision}")

    return safe_report


def _write_atomically(path: Path, content: str) -> None:
    """Write an artifact without exposing a partially written decision."""

    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DataSentinel AI analysis and protection gate."
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "baseline.csv",
        help="Path to the trusted baseline CSV.",
    )

    parser.add_argument(
        "--current",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "current.csv",
        help="Path to the current CSV to inspect.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help="Directory for this run's report and decision artifacts.",
    )
    parser.add_argument(
        "--run-id",
        help="Unique, safe identifier for this execution.",
    )

    args = parser.parse_args()

    baseline_path = args.baseline
    current_path = args.current
    artifact_dir = args.artifact_dir

    if not baseline_path.is_absolute():
        baseline_path = PROJECT_ROOT / baseline_path

    if not current_path.is_absolute():
        current_path = PROJECT_ROOT / current_path
    if artifact_dir is not None and not artifact_dir.is_absolute():
        artifact_dir = PROJECT_ROOT / artifact_dir

    try:
        run_pipeline(
            baseline_path,
            current_path,
            artifact_dir=artifact_dir,
            run_id=args.run_id,
        )
        return 0

    except Exception as exc:
        print(f"\nPIPELINE ANALYSIS ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())