from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


def _is_identifier_column(column: Any) -> bool:
    """
    Identify columns that likely contain identifiers rather than
    numerical measurements.

    Uses conservative name-based matching to avoid treating ordinary
    numerical measurements as identifiers.

    Examples:
        transaction_id -> True
        customerID     -> True
        account_key    -> True
        order_uuid     -> True
        transaction_amount -> False
        customer_age       -> False
    """

    name = str(column).strip()

    # Convert camelCase/PascalCase names to snake_case.
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)

    # Normalize common separators and capitalization.
    name = re.sub(r"[\s-]+", "_", name).lower().strip("_")

    exact_identifier_names = {
        "id",
        "identifier",
        "uuid",
        "guid",
        "key",
        "index",
        "row_id",
        "record_id",
        "transaction_id",
        "customer_id",
        "account_id",
        "user_id",
        "order_id",
        "product_id",
        "session_id",
    }

    if name in exact_identifier_names:
        return True

    identifier_suffixes = (
        "_id",
        "_identifier",
        "_uuid",
        "_guid",
        "_key",
    )

    return name.endswith(identifier_suffixes)


def detect_distribution_drift(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    alpha: float = 0.05,
    min_samples: int = 8,
    mean_change_threshold: float = 0.20,
) -> list[dict[str, Any]]:
    """
    Detect numerical distribution changes between two datasets.

    Detection includes:
    - Mean changes
    - Standard deviation changes in the reported statistics
    - Minimum and maximum changes
    - Two-sample Kolmogorov-Smirnov test

    Columns identified as likely identifiers are excluded from
    numerical distribution analysis.

    Parameters
    ----------
    baseline:
        Trusted baseline dataset.

    current:
        Current dataset being investigated.

    alpha:
        Significance threshold for the KS test.

    min_samples:
        Minimum valid observations required in each dataset.

    mean_change_threshold:
        Minimum relative mean change required to flag a mean anomaly.
        For example, 0.20 means 20%.

    Returns
    -------
    list[dict[str, Any]]
        Structured distribution findings.

    Notes
    -----
    The detector does not modify either DataFrame.

    The KS test detects differences in distributions, not their cause.
    Identifier detection is based on column names and is not infallible.
    """

    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1.")

    if min_samples < 2:
        raise ValueError("min_samples must be at least 2.")

    if mean_change_threshold < 0:
        raise ValueError("mean_change_threshold cannot be negative.")

    findings: list[dict[str, Any]] = []

    common_columns = sorted(
        set(baseline.columns) & set(current.columns),
        key=str,
    )

    for column in common_columns:
        # Identifiers are not meaningful numerical measurements.
        if _is_identifier_column(column):
            continue

        # Convert values to numeric where possible.
        # Invalid strings become NaN; infinities are removed.
        baseline_values = pd.to_numeric(
            baseline[column],
            errors="coerce",
        ).to_numpy(dtype=float)

        current_values = pd.to_numeric(
            current[column],
            errors="coerce",
        ).to_numpy(dtype=float)

        baseline_values = baseline_values[
            np.isfinite(baseline_values)
        ]

        current_values = current_values[
            np.isfinite(current_values)
        ]

        # Skip columns that do not have enough valid observations.
        if (
            len(baseline_values) < min_samples
            or len(current_values) < min_samples
        ):
            continue

        # Require at least one varying distribution.
        if (
            np.ptp(baseline_values) == 0
            and np.ptp(current_values) == 0
        ):
            continue

        baseline_mean = float(np.mean(baseline_values))
        current_mean = float(np.mean(current_values))

        baseline_std = float(np.std(baseline_values, ddof=1))
        current_std = float(np.std(current_values, ddof=1))

        baseline_min = float(np.min(baseline_values))
        current_min = float(np.min(current_values))

        baseline_max = float(np.max(baseline_values))
        current_max = float(np.max(current_values))

        # Relative mean change is unreliable near a zero baseline.
        if abs(baseline_mean) > 1e-12:
            relative_mean_change = (
                (current_mean - baseline_mean)
                / abs(baseline_mean)
            )
        else:
            relative_mean_change = None

        # Compare the two empirical distributions.
        ks_result = ks_2samp(
            baseline_values,
            current_values,
            alternative="two-sided",
            method="auto",
        )

        ks_statistic = float(ks_result.statistic)
        ks_p_value = float(ks_result.pvalue)

        mean_anomaly = (
            relative_mean_change is not None
            and abs(relative_mean_change) >= mean_change_threshold
        )

        distribution_anomaly = ks_p_value < alpha

        range_anomaly = (
            baseline_min != current_min
            or baseline_max != current_max
        )

        # Emit a finding only when a configured check detects a change.
        if not (
            mean_anomaly
            or distribution_anomaly
            or range_anomaly
        ):
            continue

        evidence: list[str] = []

        if mean_anomaly:
            evidence.append("mean_change")

        if distribution_anomaly:
            evidence.append("ks_distribution_drift")

        if range_anomaly:
            evidence.append("range_change")

        # Statistical evidence does not prove business harm.
        if distribution_anomaly or (
            relative_mean_change is not None
            and abs(relative_mean_change) >= 0.50
        ):
            severity = "high"
        else:
            severity = "medium"

        findings.append(
            {
                "type": "distribution_drift",
                "category": "numerical_distribution_change",
                "column": column,
                "description": (
                    f"Numerical distribution changes detected "
                    f"in column '{column}'."
                ),
                "baseline_value": {
                    "mean": round(baseline_mean, 6),
                    "std": round(baseline_std, 6),
                    "min": baseline_min,
                    "max": baseline_max,
                    "sample_count": int(len(baseline_values)),
                },
                "current_value": {
                    "mean": round(current_mean, 6),
                    "std": round(current_std, 6),
                    "min": current_min,
                    "max": current_max,
                    "sample_count": int(len(current_values)),
                },
                "relative_mean_change": (
                    round(relative_mean_change, 6)
                    if relative_mean_change is not None
                    else None
                ),
                "ks_statistic": round(ks_statistic, 6),
                "ks_p_value": round(ks_p_value, 6),
                "alpha": alpha,
                "evidence": evidence,
                "severity": severity,
                "detection_method": "summary_statistics_and_ks_test",
            }
        )

    return findings