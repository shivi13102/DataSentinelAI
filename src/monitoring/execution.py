from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.reasoning_agent import explain_findings
from src.analysis_engine import analyze_datasets
from src.graph.workflow import build_report
from src.monitoring.sdk import PipelineRun
from src.protection_gate import enforce_downstream, evaluate_pipeline_gate
from src.utils.data_loader import load_csv


logger = logging.getLogger(__name__)

DatasetSource = bytes | Path
ReportWriter = Callable[..., str]


def execute_monitored_pipeline(
    run: PipelineRun,
    *,
    baseline_source: DatasetSource,
    current_source: DatasetSource,
    baseline_filename: str,
    current_filename: str,
    baseline_size_bytes: int,
    current_size_bytes: int,
    write_report: ReportWriter,
    snapshot_run: Callable[[str], dict[str, Any]],
    set_report_id: Callable[[str, str], None],
) -> str:
    """Run the existing analysis and gate with actual lifecycle events."""

    report_id: str | None = None
    with run:
        with run.stage("dataset_loading", "Dataset Loading"):
            baseline = load_csv(baseline_source)
            current = load_csv(current_source)

        analysis = analyze_datasets(
            baseline=baseline,
            current=current,
            monitor=run,
        )

        with run.stage("protection_gate", "Deterministic Protection Gate"):
            protection = evaluate_pipeline_gate(analysis)
            run.publish_protection(protection)

        try:
            with run.stage("ai_investigation", "AI Investigation"):
                reasoning = explain_findings(analysis)
        except Exception as exc:
            logger.exception(
                "AI investigation failed for run %s (%s).",
                run.run_id,
                type(exc).__name__,
            )
            reasoning = {
                "status": "error",
                "error": (
                    "Local AI investigation is currently unavailable. "
                    "Deterministic data-quality analysis and pipeline "
                    "protection are operating normally."
                ),
            }

        downstream_executed = False
        if protection["decision"] == "ALLOW":
            with run.stage(
                "downstream_execution",
                "Simulated Downstream Processing",
            ):
                executed, _ = enforce_downstream(
                    protection,
                    lambda: {
                        "accepted_current_rows": int(len(current)),
                        "status": "simulated",
                    },
                )
                if not executed:
                    raise ValueError(
                        "The protection gate did not authorize downstream work."
                    )
                downstream_executed = True
        else:
            run.skip_downstream(protection["decision"])

        report = build_report(
            {
                "analysis_results": analysis,
                "reasoning_results": reasoning,
                "protection_results": protection,
            }
        )["final_report"]
        report["run_id"] = run.run_id
        report["dataset_metadata"] = {
            "baseline": {
                "filename": Path(baseline_filename).name,
                "rows": int(len(baseline)),
                "columns": int(len(baseline.columns)),
                "size_bytes": baseline_size_bytes,
            },
            "current": {
                "filename": Path(current_filename).name,
                "rows": int(len(current)),
                "columns": int(len(current.columns)),
                "size_bytes": current_size_bytes,
            },
        }
        report["generated_at"] = datetime.now(timezone.utc).isoformat()

        with run.stage("report_generation", "Report Generation"):
            report_id = write_report(report)

        run_state = snapshot_run(run.run_id)
        run_state["status"] = (
            "completed"
            if protection["decision"] == "ALLOW"
            else (
                "review_required"
                if protection["decision"] == "REVIEW_REQUIRED"
                else "blocked"
            )
        )
        run_state["report_id"] = report_id
        run_state["downstream_executed"] = downstream_executed
        run_state["latest_sequence"] += 1
        report["monitoring"] = run_state
        write_report(report, report_id=report_id)
        set_report_id(run.run_id, report_id)

        if protection["decision"] in {"REVIEW_REQUIRED", "BLOCK"}:
            run.mark_blocked(protection["decision"])

    return report_id
