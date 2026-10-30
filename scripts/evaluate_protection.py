from __future__ import annotations

import argparse
from collections import Counter
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.reasoning_agent import DEFAULT_MODEL, explain_findings
from src.analysis_engine import analyze_datasets
from src.protection_gate import enforce_downstream, evaluate_pipeline_gate
from src.utils.data_loader import load_csv


FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "protection"
MANIFEST_PATH = FIXTURE_DIR / "evaluation_manifest.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "evaluation"


def _git_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"sample_count": 0, "mean": None, "median": None}
    return {
        "sample_count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
    }


def evaluate(
    *,
    fixture_dir: Path = FIXTURE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    run_ai: bool = True,
) -> dict[str, Any]:
    manifest_path = fixture_dir / "evaluation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    analysis_latencies: list[float] = []
    detection_true_positives = 0
    detection_false_negatives = 0
    clean_false_positives = 0
    clean_true_negatives = 0
    decision_correct = 0
    decision_confusion: dict[str, dict[str, int]] = {}
    enforcement_passed = 0
    enforcement_total = 0
    ai_result: dict[str, Any] | None = None
    ai_latency: float | None = None

    for scenario in manifest["scenarios"]:
        case_id = scenario["id"]
        baseline_path = fixture_dir / scenario["baseline"]
        current_path = fixture_dir / scenario["current"]
        case: dict[str, Any] = {
            "scenario_id": case_id,
            "injected_anomalies": scenario["injected_anomalies"],
            "expected_finding_types": scenario["expected_finding_types"],
            "expected_severities": scenario["expected_severities"],
            "expected_decision": scenario["expected_decision"],
            "baseline_file": baseline_path.name,
            "current_file": current_path.name,
        }

        try:
            baseline = load_csv(baseline_path)
            current = load_csv(current_path)
            started = time.perf_counter()
            analysis = analyze_datasets(baseline, current)
            elapsed = time.perf_counter() - started
            analysis_latencies.append(elapsed)
            protection = evaluate_pipeline_gate(analysis)
        except Exception as exc:
            failures.append(
                {
                    "scenario_id": case_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            case["status"] = "failed"
            cases.append(case)
            continue

        findings = analysis["findings"]
        finding_types = [finding["type"] for finding in findings]
        finding_severities = [finding["severity"] for finding in findings]
        expected_types = scenario["expected_finding_types"]
        expected_severities = scenario["expected_severities"]
        expected_findings = Counter(zip(expected_types, expected_severities))
        observed_findings = Counter(zip(finding_types, finding_severities))
        detected_count = sum(
            min(expected_count, observed_findings[finding_key])
            for finding_key, expected_count in expected_findings.items()
        )
        detection_true_positives += detected_count
        detection_false_negatives += (
            sum(expected_findings.values()) - detected_count
        )

        if not scenario["injected_anomalies"]:
            if findings:
                clean_false_positives += 1
            else:
                clean_true_negatives += 1

        expected_decision = scenario["expected_decision"]
        actual_decision = protection["decision"]
        decision_confusion.setdefault(
            expected_decision,
            {"ALLOW": 0, "REVIEW_REQUIRED": 0, "BLOCK": 0},
        )[actual_decision] += 1
        decision_matches = actual_decision == expected_decision
        decision_correct += decision_matches

        downstream_calls: list[str] = []
        try:
            executed, _ = enforce_downstream(
                protection,
                lambda: downstream_calls.append("executed"),
            )
            expected_execution = expected_decision == "ALLOW"
            enforcement_ok = (
                executed is expected_execution
                and len(downstream_calls) == int(expected_execution)
            )
        except Exception as exc:
            enforcement_ok = False
            failures.append(
                {
                    "scenario_id": case_id,
                    "error": f"Downstream enforcement: {type(exc).__name__}: {exc}",
                }
            )
        enforcement_total += 1
        enforcement_passed += int(enforcement_ok)

        findings_match = observed_findings == expected_findings
        if not findings_match:
            failures.append(
                {
                    "scenario_id": case_id,
                    "error": (
                        "Expected finding type/severity pairs "
                        f"{sorted(expected_findings.elements())}, observed "
                        f"{sorted(observed_findings.elements())}."
                    ),
                }
            )
        if not decision_matches:
            failures.append(
                {
                    "scenario_id": case_id,
                    "error": (
                        f"Expected {expected_decision}; "
                        f"observed {actual_decision}."
                    ),
                }
            )
        if not enforcement_ok:
            failures.append(
                {
                    "scenario_id": case_id,
                    "error": "Downstream operation did not match the gate decision.",
                }
            )

        case.update(
            {
                "status": (
                    "passed"
                    if findings_match and decision_matches and enforcement_ok
                    else "failed"
                ),
                "baseline_rows": len(baseline),
                "baseline_columns": len(baseline.columns),
                "current_rows": len(current),
                "current_columns": len(current.columns),
                "analysis_status": analysis["overall_status"],
                "findings": findings,
                "observed_finding_types": finding_types,
                "observed_severities": finding_severities,
                "actual_decision": actual_decision,
                "downstream_processing_allowed": protection[
                    "downstream_processing_allowed"
                ],
                "analysis_latency_seconds": elapsed,
            }
        )
        cases.append(case)

        if run_ai and ai_result is None and findings:
            ai_result = explain_findings(analysis)
            ai_latency = ai_result.get("duration_seconds")

    enforcement_invalid_cases = [
        {},
        {
            "decision": "UNSET",
            "downstream_processing_allowed": False,
            "human_review_required": True,
        },
    ]
    for invalid_protection in enforcement_invalid_cases:
        calls: list[str] = []
        try:
            enforce_downstream(
                invalid_protection,
                lambda: calls.append("executed"),
            )
        except (TypeError, ValueError):
            passed = not calls
        else:
            passed = False
        enforcement_total += 1
        enforcement_passed += int(passed)
        if not passed:
            failures.append(
                {
                    "scenario_id": "invalid_protection_state",
                    "error": "Invalid decision state was not rejected fail-closed.",
                }
            )

    injected_anomaly_count = sum(
        len(scenario["injected_anomalies"])
        for scenario in manifest["scenarios"]
    )
    valid_case_count = sum(
        "actual_decision" in case for case in cases
    )
    negative_case_count = clean_false_positives + clean_true_negatives
    ai_attempted = ai_result is not None
    ai_status = ai_result.get("status") if ai_result else (
        "not_run" if not run_ai else "not_available"
    )
    successful_ai_latency = (
        ai_latency
        if ai_result is not None and ai_result.get("status") == "success"
        else None
    )

    result = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "project_revision": _git_revision(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "manifest": manifest_path.relative_to(PROJECT_ROOT).as_posix()
        if manifest_path.is_relative_to(PROJECT_ROOT)
        else manifest_path.name,
        "test_conditions": {
            "analysis_latency_includes_dataset_loading": False,
            "analysis_latency_repetitions_per_case": 1,
            "ai_model": DEFAULT_MODEL if run_ai else None,
            "ai_status": ai_status,
            "ai_attempted": ai_attempted,
        },
        "case_count": len(cases),
        "passed_case_count": sum(case.get("status") == "passed" for case in cases),
        "failed_case_count": sum(case.get("status") == "failed" for case in cases),
        "cases": cases,
        "metrics": {
            "detection_recall": (
                detection_true_positives / injected_anomaly_count
                if injected_anomaly_count
                else None
            ),
            "detection_true_positives": detection_true_positives,
            "detection_false_negatives": detection_false_negatives,
            "injected_anomaly_count": injected_anomaly_count,
            "false_positive_rate": (
                clean_false_positives / negative_case_count
                if negative_case_count
                else None
            ),
            "clean_false_positive_cases": clean_false_positives,
            "clean_true_negative_cases": clean_true_negatives,
            "negative_case_count": negative_case_count,
            "protection_decision_accuracy": (
                decision_correct / valid_case_count if valid_case_count else None
            ),
            "correct_protection_decisions": decision_correct,
            "protection_decision_case_count": valid_case_count,
            "protection_decision_confusion_matrix": decision_confusion,
            "analysis_latency_seconds": _summary(analysis_latencies),
            "ai_explanation_latency_seconds": successful_ai_latency,
            "ai_request_duration_seconds": ai_latency,
            "ai_failure_count": int(ai_attempted and ai_status != "success"),
            "ai_success_count": int(ai_attempted and ai_status == "success"),
            "ai_attempt_count": int(ai_attempted),
            "protection_enforcement_reliability": (
                enforcement_passed / enforcement_total
                if enforcement_total
                else None
            ),
            "protection_enforcement_passed": enforcement_passed,
            "protection_enforcement_case_count": enforcement_total,
        },
        "ai_investigation": ai_result,
        "failures": failures,
        "known_limitations": [
            "Fixtures are deterministic synthetic examples, not representative production data.",
            "False-positive rate is case-level and uses only explicitly clean fixture cases.",
            "Anomaly recall matches injected anomalies to detector finding types; it does not prove semantic cause.",
            "Analysis latency includes one run per scenario, excludes CSV loading, and is not a production benchmark.",
            "AI explanation availability and latency depend on the locally installed Ollama model and machine.",
            "Structured output validation cannot guarantee the semantic truth of AI-generated hypotheses.",
        ],
        "reproduction": [
            "python scripts/generate_protection_fixtures.py",
            "python scripts/evaluate_protection.py",
            "python scripts/evaluate_protection.py --skip-ai",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "metrics.json"
    markdown_path = output_dir / "evaluation_report.md"
    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(result), encoding="utf-8")
    return result


def _render_markdown(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# DataSentinel AI Protection Evaluation",
        "",
        f"- Evaluated: {result['evaluation_timestamp']}",
        f"- Revision: {result['project_revision'] or 'unavailable'}",
        f"- Python: {result['environment']['python']}",
        f"- Platform: {result['environment']['platform']}",
        f"- Cases: {result['passed_case_count']} passed / "
        f"{result['case_count']} total",
        "",
        "## Scenario results",
        "",
        "| Scenario | Findings | Analysis status | Expected decision | Actual decision | Downstream allowed |",
        "|---|---|---|---|---|---|",
    ]
    for case in result["cases"]:
        lines.append(
            "| {scenario_id} | {findings} | {analysis_status} | "
            "{expected_decision} | {actual_decision} | {downstream} |".format(
                scenario_id=case["scenario_id"],
                findings=", ".join(case.get("observed_finding_types", [])) or "none",
                analysis_status=case.get("analysis_status", "failed"),
                expected_decision=case["expected_decision"],
                actual_decision=case.get("actual_decision", "unavailable"),
                downstream=case.get("downstream_processing_allowed", False),
            )
        )

    lines.extend(
        [
            "",
            "## Metrics",
            "",
            f"- Detection recall: {metrics['detection_recall']}",
            f"- False-positive rate: {metrics['false_positive_rate']}",
            "- Protection-decision accuracy: "
            f"{metrics['protection_decision_accuracy']}",
            "- Analysis latency (seconds): "
            f"{json.dumps(metrics['analysis_latency_seconds'])}",
            "- Successful AI explanation latency (seconds): "
            f"{metrics['ai_explanation_latency_seconds']}",
            "- AI request duration (seconds): "
            f"{metrics['ai_request_duration_seconds']}",
            f"- AI status: {result['test_conditions']['ai_status']}",
            "- AI attempts/successes/failures: "
            f"{metrics['ai_attempt_count']}/"
            f"{metrics['ai_success_count']}/"
            f"{metrics['ai_failure_count']}",
            "- Protection enforcement reliability: "
            f"{metrics['protection_enforcement_reliability']} "
            f"({metrics['protection_enforcement_passed']}/"
            f"{metrics['protection_enforcement_case_count']})",
            "",
            "## Failures",
            "",
        ]
    )
    if result["failures"]:
        lines.extend(
            f"- {failure['scenario_id']}: {failure['error']}"
            for failure in result["failures"]
        )
    else:
        lines.append("- None observed.")

    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in result["known_limitations"])
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            "Run from the repository root:",
            "",
            "```powershell",
            "python scripts/generate_protection_fixtures.py",
            "python scripts/evaluate_protection.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate DataSentinel's real analysis and protection gate."
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip local Ollama inference and report AI metrics as unavailable.",
    )
    args = parser.parse_args()

    result = evaluate(run_ai=not args.skip_ai)
    print(
        f"Evaluation completed: {result['passed_case_count']}/"
        f"{result['case_count']} cases passed."
    )
    print(f"JSON report: {DEFAULT_OUTPUT_DIR / 'metrics.json'}")
    print(f"Markdown report: {DEFAULT_OUTPUT_DIR / 'evaluation_report.md'}")
    return 0 if not result["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
