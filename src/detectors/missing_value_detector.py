from __future__ import annotations

from typing import Any

import pandas as pd


def detect_missing_value_anomalies(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    increase_threshold: float = 10.0,
) -> list[dict[str, Any]]:
    """
    Detect unexpected increases in missing-value percentages.

    Parameters
    ----------
    baseline:
        Trusted baseline dataset.

    current:
        Current dataset being investigated.

    increase_threshold:
        Minimum increase in missing-value percentage points
        required to report an anomaly.

    Returns
    -------
    list[dict[str, Any]]
        Structured missing-value findings.

    Notes
    -----
    The function does not modify either DataFrame.
    Missing-value percentages are calculated independently
    for each dataset.
    """

    if increase_threshold < 0:
        raise ValueError("increase_threshold cannot be negative.")

    findings: list[dict[str, Any]] = []

    # Only compare columns that exist in both datasets.
    common_columns = sorted(set(baseline.columns) & set(current.columns))

    for column in common_columns:
        baseline_missing_count = int(baseline[column].isna().sum())
        current_missing_count = int(current[column].isna().sum())

        baseline_rows = len(baseline)
        current_rows = len(current)

        baseline_missing_pct = (
            baseline_missing_count / baseline_rows * 100
            if baseline_rows > 0
            else 0.0
        )

        current_missing_pct = (
            current_missing_count / current_rows * 100
            if current_rows > 0
            else 0.0
        )

        increase_pct_points = current_missing_pct - baseline_missing_pct

        # An entirely empty current column is a high-priority finding.
        if current_rows > 0 and current_missing_count == current_rows:
            findings.append(
                {
                    "type": "missing_value_anomaly",
                    "category": "entirely_missing_column",
                    "column": column,
                    "description": (
                        f"Column '{column}' is entirely missing "
                        "in the current dataset."
                    ),
                    "baseline_value": {
                        "missing_count": baseline_missing_count,
                        "missing_percentage": round(
                            baseline_missing_pct, 2
                        ),
                    },
                    "current_value": {
                        "missing_count": current_missing_count,
                        "missing_percentage": round(
                            current_missing_pct, 2
                        ),
                    },
                    "change_percentage_points": round(
                        increase_pct_points, 2
                    ),
                    "severity": "high",
                    "detection_method": "missing_value_percentage",
                }
            )

        elif increase_pct_points >= increase_threshold:
            findings.append(
                {
                    "type": "missing_value_anomaly",
                    "category": "missing_rate_increase",
                    "column": column,
                    "description": (
                        f"Missing values in '{column}' increased "
                        f"from {baseline_missing_pct:.2f}% to "
                        f"{current_missing_pct:.2f}%."
                    ),
                    "baseline_value": {
                        "missing_count": baseline_missing_count,
                        "missing_percentage": round(
                            baseline_missing_pct, 2
                        ),
                    },
                    "current_value": {
                        "missing_count": current_missing_count,
                        "missing_percentage": round(
                            current_missing_pct, 2
                        ),
                    },
                    "change_percentage_points": round(
                        increase_pct_points, 2
                    ),
                    "severity": (
                        "high"
                        if increase_pct_points >= 30
                        else "medium"
                    ),
                    "detection_method": "missing_value_percentage",
                }
            )

    return findings