from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_numeric_dtype,
)


def _are_compatible_dtypes(
    baseline_dtype: Any,
    current_dtype: Any,
) -> bool:
    """
    Check whether two data types are compatible.

    Integer and floating-point types are treated as compatible
    because missing values can cause Pandas to convert integers
    to floats.

    Boolean types are handled separately because booleans should
    not be treated as ordinary numerical measurements.
    """

    if baseline_dtype == current_dtype:
        return True

    baseline_is_bool = is_bool_dtype(baseline_dtype)
    current_is_bool = is_bool_dtype(current_dtype)

    if baseline_is_bool or current_is_bool:
        return False

    if (
        is_numeric_dtype(baseline_dtype)
        and is_numeric_dtype(current_dtype)
    ):
        return True

    return False


def detect_schema_changes(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Compare the schemas of two DataFrames.

    Detects:
    - Added columns
    - Removed columns
    - Incompatible data type changes

    Compatible numerical type changes, such as int64 to float64,
    do not generate schema findings.

    The function does not modify either DataFrame.
    """

    findings: list[dict[str, Any]] = []

    baseline_columns = set(baseline.columns)
    current_columns = set(current.columns)

    # Detect columns added to the current dataset.
    for column in sorted(current_columns - baseline_columns):
        findings.append(
            {
                "type": "schema_change",
                "category": "added_column",
                "column": column,
                "description": (
                    f"Column '{column}' exists in the current dataset "
                    "but not in the baseline."
                ),
                "baseline_value": None,
                "current_value": str(current[column].dtype),
                "severity": "medium",
                "detection_method": "column_name_comparison",
            }
        )

    # Detect columns removed from the current dataset.
    for column in sorted(baseline_columns - current_columns):
        findings.append(
            {
                "type": "schema_change",
                "category": "removed_column",
                "column": column,
                "description": (
                    f"Column '{column}' exists in the baseline "
                    "but is missing from the current dataset."
                ),
                "baseline_value": str(baseline[column].dtype),
                "current_value": None,
                "severity": "high",
                "detection_method": "column_name_comparison",
            }
        )

    # Compare data types for columns present in both datasets.
    common_columns = sorted(
        baseline_columns & current_columns,
        key=str,
    )

    for column in common_columns:
        baseline_dtype = baseline[column].dtype
        current_dtype = current[column].dtype

        if _are_compatible_dtypes(
            baseline_dtype,
            current_dtype,
        ):
            continue

        baseline_dtype_name = str(baseline_dtype)
        current_dtype_name = str(current_dtype)

        findings.append(
            {
                "type": "schema_change",
                "category": "dtype_change",
                "column": column,
                "description": (
                    f"Column '{column}' changed data type "
                    f"from {baseline_dtype_name} "
                    f"to {current_dtype_name}."
                ),
                "baseline_value": baseline_dtype_name,
                "current_value": current_dtype_name,
                "severity": "high",
                "detection_method": "pandas_dtype_comparison",
            }
        )

    return findings