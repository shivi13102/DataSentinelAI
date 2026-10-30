
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.detectors.schema_detector import detect_schema_changes
from src.detectors.missing_value_detector import (
    detect_missing_value_anomalies,
)
from src.detectors.duplicate_detector import (
    detect_duplicate_anomalies,
)
from src.detectors.distribution_detector import (
    detect_distribution_drift,
)
from src.detectors.categorical_drift_detector import (
    detect_categorical_drift,
)
from src.monitoring.sdk import PipelineRun


_DETECTORS = (
    (
        "schema_analysis",
        "Schema Change Detection",
        detect_schema_changes,
    ),
    (
        "missing_value_analysis",
        "Missing Value Detection",
        detect_missing_value_anomalies,
    ),
    (
        "duplicate_analysis",
        "Duplicate Detection",
        detect_duplicate_anomalies,
    ),
    (
        "numerical_drift_analysis",
        "Numerical Drift Detection",
        detect_distribution_drift,
    ),
    (
        "categorical_drift_analysis",
        "Categorical Drift Detection",
        detect_categorical_drift,
    ),
)


def analyze_datasets(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    *,
    monitor: PipelineRun | None = None,
) -> dict[str, Any]:
    """
    Run all data-quality detectors against two datasets.

    The baseline represents trusted historical data.
    The current dataset represents the data being investigated.

    This function only analyzes data. It never modifies either
    input DataFrame.
    """

    def validate_inputs() -> None:
        if not isinstance(baseline, pd.DataFrame):
            raise TypeError("baseline must be a pandas DataFrame.")

        if not isinstance(current, pd.DataFrame):
            raise TypeError("current must be a pandas DataFrame.")

        if baseline.empty or current.empty:
            raise ValueError(
                "Baseline and current datasets must each contain at least one row."
            )

        if len(baseline.columns) == 0 or len(current.columns) == 0:
            raise ValueError(
                "Baseline and current datasets must each contain at least one column."
            )

        if (
            baseline.columns.duplicated().any()
            or current.columns.duplicated().any()
        ):
            raise ValueError("Dataset column names must be unique.")

    if monitor is None:
        validate_inputs()
    else:
        with monitor.stage("input_validation", "Input Validation"):
            validate_inputs()

    findings: list[dict[str, Any]] = []

    for stage_id, stage_name, detector in _DETECTORS:
        if monitor is None:
            result = detector(baseline, current)
        else:
            with monitor.stage(stage_id, stage_name):
                result = detector(baseline, current)
                monitor.publish_findings(stage_id, stage_name, result)

        findings.extend(result)

    def aggregate_findings() -> tuple[dict[str, int], dict[str, int]]:
        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        for finding in findings:
            severity = finding.get("severity")
            if severity in severity_counts:
                severity_counts[severity] += 1

        findings_by_type: dict[str, int] = {}
        for finding in findings:
            finding_type = finding.get("type", "unknown")
            findings_by_type[finding_type] = (
                findings_by_type.get(finding_type, 0) + 1
            )
        return severity_counts, findings_by_type

    if monitor is None:
        severity_counts, findings_by_type = aggregate_findings()
    else:
        with monitor.stage("findings_aggregation", "Findings Aggregation"):
            severity_counts, findings_by_type = aggregate_findings()

    # Determine an overall status.
    if severity_counts["critical"] > 0 or severity_counts["high"] > 0:
        overall_status = "critical"
    elif severity_counts["medium"] > 0:
        overall_status = "warning"
    else:
        overall_status = "healthy"

    return {
        "analysis_timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "baseline_rows": int(len(baseline)),
        "current_rows": int(len(current)),
        "baseline_columns": int(len(baseline.columns)),
        "current_columns": int(len(current.columns)),
        "total_findings": len(findings),
        "overall_status": overall_status,
        "severity_counts": severity_counts,
        "findings_by_type": findings_by_type,
        "findings": findings,
    }
