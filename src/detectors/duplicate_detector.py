from __future__ import annotations
from typing import Any
import pandas as pd


def detect_duplicate_anomalies(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    increase_threshold: float = 5.0,
) -> list[dict[str, Any]]:
    """
    Detect increases in duplicate rows between two datasets.

    Duplicate rows are identified using all columns shared by
    the baseline and current datasets.

    Parameters
    ----------
    baseline:
        Trusted baseline dataset.

    current:
        Current dataset being investigated.

    increase_threshold:
        Minimum increase in duplicate percentage points
        required to report an anomaly.

    Returns
    -------
    list[dict[str, Any]]
        Structured duplicate findings.

    Notes
    -----
    The function does not modify either DataFrame.
    """

    if increase_threshold < 0:
        raise ValueError("increase_threshold cannot be negative.")

    if baseline.empty or current.empty:
        return []

    # Compare records using columns shared by both datasets.
    common_columns = sorted(
        set(baseline.columns) & set(current.columns)
    )

    if not common_columns:
        return []

    baseline_comparable = baseline[common_columns]
    current_comparable = current[common_columns]

    baseline_duplicate_count = int(
        baseline_comparable.duplicated().sum()
    )

    current_duplicate_count = int(
        current_comparable.duplicated().sum()
    )

    baseline_duplicate_pct = (
        baseline_duplicate_count / len(baseline) * 100
    )

    current_duplicate_pct = (
        current_duplicate_count / len(current) * 100
    )

    increase_pct_points = (
        current_duplicate_pct - baseline_duplicate_pct
    )

    findings: list[dict[str, Any]] = []

    if increase_pct_points >= increase_threshold:
        findings.append(
            {
                "type": "duplicate_anomaly",
                "category": "duplicate_rate_increase",
                "column": None,
                "description": (
                    "Duplicate row percentage increased from "
                    f"{baseline_duplicate_pct:.2f}% to "
                    f"{current_duplicate_pct:.2f}%."
                ),
                "baseline_value": {
                    "duplicate_count": baseline_duplicate_count,
                    "duplicate_percentage": round(
                        baseline_duplicate_pct, 2
                    ),
                },
                "current_value": {
                    "duplicate_count": current_duplicate_count,
                    "duplicate_percentage": round(
                        current_duplicate_pct, 2
                    ),
                },
                "change_percentage_points": round(
                    increase_pct_points, 2
                ),
                "severity": (
                    "high"
                    if increase_pct_points >= 20
                    else "medium"
                ),
                "detection_method": "duplicate_row_comparison",
                "compared_columns": common_columns,
            }
        )

    return findings