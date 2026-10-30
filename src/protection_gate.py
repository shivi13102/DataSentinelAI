from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar


VALID_DECISIONS = {
    "ALLOW",
    "REVIEW_REQUIRED",
    "BLOCK",
}

VALID_SEVERITIES = {"low", "medium", "high", "critical"}
FAILED_STATUSES = {"error", "failed", "incomplete", "unverified"}
T = TypeVar("T")


def evaluate_pipeline_gate(
    analysis_results: Any,
) -> dict[str, Any]:
    """
    Decide whether downstream processing should continue.

    The decision is based on deterministic Python analysis.
    The LLM does not control this decision.

    Rules:
    - BLOCK: Critical/high findings, a critical status, or a failed
      analysis.
    - REVIEW_REQUIRED: A warning status or medium-severity findings.
    - ALLOW: A healthy status with only low-severity findings (or none).

    The gate never modifies the input datasets.
    """

    if not isinstance(analysis_results, dict):
        raise TypeError("analysis_results must be a dictionary.")

    overall_status = analysis_results.get("overall_status")

    if not isinstance(overall_status, str) or not overall_status.strip():
        raise ValueError(
            "analysis_results must contain a valid overall_status."
        )

    overall_status = overall_status.strip().lower()
    if overall_status not in {
        "healthy",
        "warning",
        "critical",
        *FAILED_STATUSES,
    }:
        raise ValueError(
            f"analysis_results has unknown overall_status: "
            f"{overall_status!r}."
        )

    findings = analysis_results.get("findings")

    if not isinstance(findings, list):
        raise ValueError(
            "analysis_results must contain a findings list."
        )

    reasons: list[str] = []
    finding_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "total": len(findings),
    }

    for index, finding in enumerate(findings, start=1):

        if not isinstance(finding, dict):
            raise ValueError(
                f"Finding {index} must be a dictionary."
            )

        finding_type = finding.get("type")
        if not isinstance(finding_type, str) or not finding_type.strip():
            raise ValueError(
                f"Finding {index} must have a non-empty type."
            )

        severity = finding.get("severity")
        if not isinstance(severity, str):
            raise ValueError(
                f"Finding {index} must have a valid severity."
            )

        severity = severity.strip().lower()

        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Finding {index} has unknown severity: {severity!r}."
            )

        finding_counts[severity] += 1

        reasons.append(
            f"Finding {index}: {finding_type.strip()} "
            f"(severity: {severity})."
        )

    declared_counts = analysis_results.get("severity_counts")
    if declared_counts is not None:
        if not isinstance(declared_counts, dict):
            raise ValueError("severity_counts must be a dictionary.")
        if set(declared_counts) - VALID_SEVERITIES:
            raise ValueError("severity_counts contains an unknown severity.")
        for severity in ("critical", "high", "medium", "low"):
            if severity not in declared_counts:
                continue
            declared_count = declared_counts[severity]
            if (
                not isinstance(declared_count, int)
                or isinstance(declared_count, bool)
                or declared_count < 0
            ):
                raise ValueError(
                    f"severity_counts[{severity!r}] must be a "
                    "non-negative integer."
                )
            if declared_count != finding_counts[severity]:
                return _blocked_result(
                    finding_counts,
                    reasons,
                    "Analysis severity counts contradict its findings.",
                )

    declared_total = analysis_results.get("total_findings")
    if declared_total is not None:
        if (
            not isinstance(declared_total, int)
            or isinstance(declared_total, bool)
            or declared_total < 0
        ):
            raise ValueError("total_findings must be a non-negative integer.")
        if declared_total != len(findings):
            return _blocked_result(
                finding_counts,
                reasons,
                "Analysis finding count contradicts its findings list.",
            )

    critical_findings = (
        finding_counts["critical"] + finding_counts["high"]
    )
    review_findings = finding_counts["medium"]
    if overall_status in FAILED_STATUSES:
        return _blocked_result(
            finding_counts,
            reasons,
            f"Analysis status is {overall_status}; results are not "
            "trustworthy.",
        )

    if overall_status == "critical" or critical_findings:
        if overall_status != "critical":
            return _blocked_result(
                finding_counts,
                reasons,
                "Critical or high-severity findings contradict the "
                "overall analysis status.",
            )
        decision = "BLOCK"
        human_review_required = True

        reasons.insert(
            0,
            "Critical data-quality risk detected. "
            "Downstream processing must not continue automatically.",
        )

    elif review_findings or overall_status == "warning":
        if overall_status != "warning" or not review_findings:
            return _blocked_result(
                finding_counts,
                reasons,
                "Medium-severity findings contradict the overall "
                "analysis status.",
            )
        decision = "REVIEW_REQUIRED"
        human_review_required = True

        reasons.insert(
            0,
            "Data-quality issues require human review before "
            "downstream processing.",
        )

    elif overall_status == "healthy":
        decision = "ALLOW"
        human_review_required = False

        reasons.insert(
            0,
            "No medium-or-higher severity findings were detected.",
        )

    return {
        "decision": decision,
        "downstream_processing_allowed": decision == "ALLOW",
        "human_review_required": human_review_required,
        "finding_counts": finding_counts,
        "reasons": reasons,
    }


def _blocked_result(
    finding_counts: dict[str, int],
    finding_reasons: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "decision": "BLOCK",
        "downstream_processing_allowed": False,
        "human_review_required": True,
        "finding_counts": finding_counts,
        "reasons": [reason, *finding_reasons],
    }


def enforce_downstream(
    protection_results: Any,
    operation: Callable[[], T],
) -> tuple[bool, T | None]:
    """Run an operation only when a consistent authoritative ALLOW exists."""

    if not callable(operation):
        raise TypeError("operation must be callable.")
    if not isinstance(protection_results, dict):
        raise TypeError("protection_results must be a dictionary.")

    decision = protection_results.get("decision")
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid protection decision: {decision!r}.")

    allowed = protection_results.get("downstream_processing_allowed")
    review_required = protection_results.get("human_review_required")

    if decision == "ALLOW":
        if allowed is not True or review_required is not False:
            raise ValueError(
                "ALLOW requires downstream permission and no pending "
                "human review."
            )
        return True, operation()

    if allowed is not False:
        raise ValueError(
            f"{decision} must not permit downstream processing."
        )
    return False, None