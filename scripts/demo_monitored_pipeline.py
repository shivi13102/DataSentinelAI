from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api import save_report
from src.agents.reasoning_agent import explain_findings
from src.analysis_engine import analyze_datasets
from src.graph.workflow import build_report
from src.monitoring.sdk import PipelineRun
from src.protection_gate import enforce_downstream, evaluate_pipeline_gate
from src.utils.data_loader import load_csv

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "protection"
SCENARIOS = (
    "healthy",
    "suspicious",
    "critical",
    "duplicate",
    "numerical_drift",
    "categorical_drift",
    "multiple",
)


def run_demo(scenario: str, *, skip_ai: bool) -> dict:
    run_id = str(uuid4())
    events = []
    baseline_path = FIXTURE_DIR / f"{scenario}_baseline.csv"
    current_path = FIXTURE_DIR / f"{scenario}_current.csv"

    with PipelineRun(
        run_id,
        "DataSentinel fixture pipeline",
        events.append,
    ) as monitor:
        with monitor.stage("dataset_loading", "Dataset Loading"):
            baseline = load_csv(baseline_path)
            current = load_csv(current_path)

        analysis = analyze_datasets(
            baseline,
            current,
            monitor=monitor,
        )

        with monitor.stage("protection_gate", "Deterministic Protection Gate"):
            protection = evaluate_pipeline_gate(analysis)
            monitor.publish_protection(protection)

        try:
            with monitor.stage("ai_investigation", "AI Investigation"):
                reasoning = (
                    {"status": "skipped"}
                    if skip_ai
                    else explain_findings(analysis)
                )
        except Exception:
            reasoning = {
                "status": "error",
                "error": (
                    "AI investigation failed; deterministic analysis and "
                    "protection remain authoritative."
                ),
            }

        downstream_executed = False
        if protection["decision"] == "ALLOW":
            with monitor.stage(
                "downstream_execution",
                "Simulated Downstream Processing",
            ):
                downstream_executed, _ = enforce_downstream(
                    protection,
                    lambda: {"processed_rows": len(current)},
                )
        else:
            monitor.skip_downstream(protection["decision"])

        report = build_report(
            {
                "analysis_results": analysis,
                "reasoning_results": reasoning,
                "protection_results": protection,
            }
        )["final_report"]
        report["run_id"] = run_id
        report["monitoring"] = {
            "status": (
                "completed"
                if protection["decision"] == "ALLOW"
                else (
                    "review_required"
                    if protection["decision"] == "REVIEW_REQUIRED"
                    else "blocked"
                )
            ),
            "protection_decision": protection["decision"],
            "downstream_executed": downstream_executed,
            "latest_sequence": monitor.sequence,
        }

        with monitor.stage("report_generation", "Report Generation"):
            report_id = save_report(report)

        if protection["decision"] in {"REVIEW_REQUIRED", "BLOCK"}:
            monitor.mark_blocked(protection["decision"])

    report["monitoring"]["latest_sequence"] = monitor.sequence
    report_id = save_report(report, report_id=report_id)

    return {
        "run_id": run_id,
        "report_id": report_id,
        "decision": protection["decision"],
        "downstream_executed": downstream_executed,
        "events": [json.loads(event.model_dump_json()) for event in events],
        "report_path": str(
            PROJECT_ROOT / "reports" / f"analysis_{report_id}.json"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a real fixture through the DataSentinel monitoring SDK."
    )
    parser.add_argument("--scenario", choices=SCENARIOS, default="healthy")
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip the optional local Ollama explanation request.",
    )
    args = parser.parse_args()

    result = run_demo(args.scenario, skip_ai=args.skip_ai)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
