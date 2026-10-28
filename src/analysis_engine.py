
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


def analyze_datasets(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
) -> dict[str, Any]:
    """
    Run all data-quality detectors against two datasets.

    The baseline represents trusted historical data.
    The current dataset represents the data being investigated.

    This function only analyzes data. It never modifies either
    input DataFrame.
    """

    if not isinstance(baseline, pd.DataFrame):
        raise TypeError("baseline must be a pandas DataFrame.")

    if not isinstance(current, pd.DataFrame):
        raise TypeError("current must be a pandas DataFrame.")

    findings: list[dict[str, Any]] = []

    # Run each detector independently.
    detector_results = [
        detect_schema_changes(baseline, current),
        detect_missing_value_anomalies(baseline, current),
        detect_duplicate_anomalies(baseline, current),
        detect_distribution_drift(baseline, current),
        detect_categorical_drift(baseline, current),
    ]

    # Combine all findings into one list.
    for result in detector_results:
        findings.extend(result)

    # Count findings by severity.
    severity_counts = {
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    for finding in findings:
        severity = finding.get("severity", "low")

        if severity in severity_counts:
            severity_counts[severity] += 1

    # Determine an overall status.
    if severity_counts["high"] > 0:
        overall_status = "critical"
    elif severity_counts["medium"] > 0:
        overall_status = "warning"
    else:
        overall_status = "healthy"

    # Count findings by detector type.
    findings_by_type: dict[str, int] = {}

    for finding in findings:
        finding_type = finding.get("type", "unknown")

        findings_by_type[finding_type] = (
            findings_by_type.get(finding_type, 0) + 1
        )

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
