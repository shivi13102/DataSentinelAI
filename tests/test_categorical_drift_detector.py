
import numpy as np
import pandas as pd
import pytest

from src.detectors.categorical_drift_detector import (
    detect_categorical_drift,
)


def test_detect_significant_categorical_drift():
    baseline = pd.DataFrame(
        {
            "status": (
                ["Approved"] * 60
                + ["Pending"] * 30
                + ["Rejected"] * 30
            )
        }
    )

    current = pd.DataFrame(
        {
            "status": (
                ["Approved"] * 10
                + ["Pending"] * 30
                + ["Rejected"] * 30
                + ["Unknown"] * 50
            )
        }
    )

    findings = detect_categorical_drift(
        baseline,
        current,
        min_samples=20,
        drift_threshold=0.10,
    )

    assert len(findings) == 1
    assert findings[0]["column"] == "status"
    assert findings[0]["type"] == "categorical_drift"
    assert (
        findings[0]["category"]
        == "categorical_distribution_change"
    )
    assert findings[0]["severity"] == "high"
    assert "Unknown" in findings[0]["new_categories"]


def test_identical_distributions_produce_no_findings():
    values = ["A"] * 40 + ["B"] * 40 + ["C"] * 40

    baseline = pd.DataFrame({"category": values})
    current = pd.DataFrame({"category": values})

    findings = detect_categorical_drift(baseline, current)

    assert findings == []


def test_small_distribution_change_below_threshold():
    baseline = pd.DataFrame(
        {"category": ["A"] * 50 + ["B"] * 50}
    )

    current = pd.DataFrame(
        {"category": ["A"] * 45 + ["B"] * 55}
    )

    findings = detect_categorical_drift(
        baseline,
        current,
        drift_threshold=0.20,
    )

    assert findings == []


def test_insufficient_samples_are_skipped():
    baseline = pd.DataFrame(
        {"category": ["A", "B", "A", "B"]}
    )

    current = pd.DataFrame(
        {"category": ["A", "A", "A", "B"]}
    )

    findings = detect_categorical_drift(
        baseline,
        current,
        min_samples=20,
    )

    assert findings == []


def test_missing_values_are_excluded_from_category_counts():
    baseline = pd.DataFrame(
        {
            "category": (
                ["A"] * 40
                + ["B"] * 40
                + [None] * 20
            )
        }
    )

    current = pd.DataFrame(
        {
            "category": (
                ["A"] * 40
                + ["B"] * 40
                + [None] * 20
            )
        }
    )

    findings = detect_categorical_drift(baseline, current)

    assert findings == []


def test_invalid_alpha_is_rejected():
    baseline = pd.DataFrame({"category": ["A", "B"] * 20})
    current = pd.DataFrame({"category": ["A", "B"] * 20})

    with pytest.raises(ValueError):
        detect_categorical_drift(
            baseline,
            current,
            alpha=1.5,
        )


def test_negative_drift_threshold_is_rejected():
    baseline = pd.DataFrame({"category": ["A", "B"] * 20})
    current = pd.DataFrame({"category": ["A", "B"] * 20})

    with pytest.raises(ValueError):
        detect_categorical_drift(
            baseline,
            current,
            drift_threshold=-0.1,
        )


def test_numeric_columns_with_too_few_categories_are_skipped():
    baseline = pd.DataFrame(
        {"category": np.ones(30)}
    )

    current = pd.DataFrame(
        {"category": np.ones(30)}
    )

    findings = detect_categorical_drift(baseline, current)

    assert findings == []


def test_numeric_measurements_are_not_reported_as_categorical_drift():
    baseline = pd.DataFrame({"measurement": [value % 10 for value in range(100)]})
    current = pd.DataFrame(
        {"measurement": [value * 4 for value in range(100)]}
    )

    findings = detect_categorical_drift(baseline, current)

    assert findings == []
