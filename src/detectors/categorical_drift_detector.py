
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency


def detect_categorical_drift(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    alpha: float = 0.05,
    min_samples: int = 20,
    drift_threshold: float = 0.10,
) -> list[dict[str, Any]]:
    """
    Detect significant changes in categorical column distributions.

    Parameters
    ----------
    baseline:
        Trusted historical dataset.
    current:
        New dataset being monitored.
    alpha:
        Significance level for the chi-square test.
    min_samples:
        Minimum non-missing observations required in each dataset.
    drift_threshold:
        Minimum total variation distance required to report a finding.

    Returns
    -------
    list[dict[str, Any]]
        Categorical drift findings.
    """

    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1.")

    if min_samples < 2:
        raise ValueError("min_samples must be at least 2.")

    if not 0 <= drift_threshold <= 1:
        raise ValueError("drift_threshold must be between 0 and 1.")

    findings: list[dict[str, Any]] = []

    common_columns = sorted(set(baseline.columns) & set(current.columns))

    for column in common_columns:
        baseline_values = baseline[column].dropna().astype(str)
        current_values = current[column].dropna().astype(str)

        if (
            len(baseline_values) < min_samples
            or len(current_values) < min_samples
        ):
            continue

        baseline_counts = baseline_values.value_counts()
        current_counts = current_values.value_counts()

        # Save the original categories before reindexing.
        baseline_categories = set(baseline_counts.index)
        current_categories = set(current_counts.index)

        categories = sorted(
            baseline_categories | current_categories
        )

        if len(categories) < 2:
            continue

        baseline_counts = baseline_counts.reindex(
            categories, fill_value=0
        )
        current_counts = current_counts.reindex(
            categories, fill_value=0
        )

        baseline_proportions = (
            baseline_counts / len(baseline_values)
        )
        current_proportions = (
            current_counts / len(current_values)
        )

        # Calculate Total Variation Distance
        total_variation_distance = float(
            0.5
            * np.abs(
                baseline_proportions.to_numpy()
                - current_proportions.to_numpy()
            ).sum()
        )

        # Create contingency table
        contingency_table = np.vstack(
            [
                baseline_counts.to_numpy(),
                current_counts.to_numpy(),
            ]
        )

        # Remove categories absent from both datasets
        contingency_table = contingency_table[
            :, contingency_table.sum(axis=0) > 0
        ]

        if contingency_table.shape[1] < 2:
            continue

        # Calculate expected frequencies
        _, _, _, expected_counts = chi2_contingency(
            contingency_table,
            correction=False,
        )

        # Skip unreliable chi-square results
        if (expected_counts < 5).any():
            continue

        # Perform Chi-Square test
        chi2_statistic, p_value, _, _ = chi2_contingency(
            contingency_table,
            correction=False,
        )

        statistically_significant = p_value < alpha

        magnitude_significant = (
            total_variation_distance >= drift_threshold
        )

        if not (
            statistically_significant and magnitude_significant
        ):
            continue

        # Identify new and removed categories
        new_categories = sorted(
            current_categories - baseline_categories
        )

        removed_categories = sorted(
            baseline_categories - current_categories
        )

        # Determine drift severity
        severity = (
            "high"
            if total_variation_distance >= 0.30
            else "medium"
        )

        # Store drift findings
        findings.append(
            {
                "type": "categorical_drift",
                "category": "categorical_distribution_change",
                "column": column,
                "description": (
                    f"Categorical distribution changed in column "
                    f"'{column}'."
                ),
                "baseline_value": {
                    "counts": {
                        str(k): int(v)
                        for k, v in baseline_counts.items()
                    },
                    "sample_count": int(len(baseline_values)),
                },
                "current_value": {
                    "counts": {
                        str(k): int(v)
                        for k, v in current_counts.items()
                    },
                    "sample_count": int(len(current_values)),
                },
                "total_variation_distance": round(
                    total_variation_distance, 6
                ),
                "chi2_statistic": round(float(chi2_statistic), 6),
                "p_value": round(float(p_value), 6),
                "alpha": alpha,
                "new_categories": new_categories,
                "removed_categories": removed_categories,
                "severity": severity,
                "detection_method": (
                    "total_variation_distance_and_chi_square"
                ),
            }
        )

    return findings
