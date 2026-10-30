from __future__ import annotations

from typing import Any


VALID_DECISIONS = {
    "ALLOW",
    "REVIEW_REQUIRED",
    "BLOCK",
}

SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def evaluate_pipeline_gate(
    analysis_results: dict[str, Any],
) -> dict[str, Any]:
    """
    Decide whether downstream processing should continue.

    The decision is based on deterministic Python analysis.
    The LLM does not control this decision.

    Rules:
    - BLOCK: The overall analysis status is critical.
    - REVIEW_REQUIRED: High-severity or medium-severity findings exist.
    - ALLOW: No blocking or review-worthy findings exist.

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
    findings = analysis_results.get("findings")

    if not isinstance(findings, list):
        raise ValueError(
            "analysis_results must contain a findings list."
        )

    reasons: list[str] = []
    high_severity_count = 0
    medium_severity_count = 0
    critical_severity_count = 0
    low_severity_count = 0

    for index, finding in enumerate(findings, start=1):

        if not isinstance(finding, dict):
            raise ValueError(
                f"Finding {index} must be a dictionary."
            )

        severity = finding.get("severity")

        if not isinstance(severity, str):
            raise ValueError(
                f"Finding {index} must have a valid severity."
            )

        severity = severity.strip().lower()

        if severity not in SEVERITY_RANK:
            raise ValueError(
                f"Finding {index} has unknown severity: {severity!r}."
            )

        if severity == "critical":
            critical_severity_count += 1
        elif severity == "high":
            high_severity_count += 1
        elif severity == "medium":
            medium_severity_count += 1
        else:
            low_severity_count += 1

        finding_type = finding.get("type", "unknown_finding")

        reasons.append(
            f"Finding {index}: {finding_type} "
            f"(severity: {severity})."
        )

    if overall_status == "critical" or critical_severity_count > 0:
        decision = "BLOCK"
        human_review_required = True

        reasons.insert(
            0,
            "Critical data-quality risk detected. "
            "Downstream processing must not continue automatically.",
        )

    elif high_severity_count > 0 or medium_severity_count > 0:
        decision = "REVIEW_REQUIRED"
        human_review_required = True

        reasons.insert(
            0,
            "Data-quality issues require human review before "
            "downstream processing.",
        )

    elif overall_status in {"error", "failed", "unknown"}:
        decision = "BLOCK"
        human_review_required = True

        reasons.insert(
            0,
            "Analysis status is not trustworthy. "
            "Downstream processing is blocked.",
        )

    else:
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
        "finding_counts": {
            "critical": critical_severity_count,
            "high": high_severity_count,
            "medium": medium_severity_count,
            "low": low_severity_count,
            "total": len(findings),
        },
        "reasons": reasons,
    }