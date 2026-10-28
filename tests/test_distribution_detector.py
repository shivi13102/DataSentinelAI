import numpy as np
import pandas as pd
import pytest

from src.detectors.distribution_detector import (
    detect_distribution_drift,
)


def test_detect_large_distribution_shift():
    baseline = pd.DataFrame(
        {
            "amount": [
                100, 120, 110, 130,
                115, 125, 105, 120,
            ]
        }
    )

    current = pd.DataFrame(
        {
            "amount": [
                8000, 9600, 8800, 10400,
                9200, 10000, 8400, 9600,
            ]
        }
    )

    findings = detect_distribution_drift(
        baseline,
        current,
        min_samples=8,
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding["column"] == "amount"
    assert finding["category"] == "numerical_distribution_change"
    assert finding["baseline_value"]["mean"] < 200
    assert finding["current_value"]["mean"] > 8000
    assert "mean_change" in finding["evidence"]
    assert finding["severity"] == "high"


def test_identical_distributions_produce_no_findings():
    values = np.arange(1, 21, dtype=float)

    baseline = pd.DataFrame({"amount": values})
    current = pd.DataFrame({"amount": values.copy()})

    findings = detect_distribution_drift(
        baseline,
        current,
        min_samples=8,
    )

    assert findings == []


def test_insufficient_samples_are_skipped():
    baseline = pd.DataFrame({"amount": [10, 20, 30]})
    current = pd.DataFrame({"amount": [100, 200, 300]})

    findings = detect_distribution_drift(
        baseline,
        current,
        min_samples=8,
    )

    assert findings == []


def test_non_numeric_columns_are_skipped():
    baseline = pd.DataFrame(
        {"category": ["A", "B", "C", "D"]}
    )

    current = pd.DataFrame(
        {"category": ["X", "Y", "Z", "W"]}
    )

    findings = detect_distribution_drift(
        baseline,
        current,
        min_samples=2,
    )

    assert findings == []


def test_invalid_alpha_is_rejected():
    baseline = pd.DataFrame({"amount": range(10)})
    current = pd.DataFrame({"amount": range(10)})

    with pytest.raises(ValueError):
        detect_distribution_drift(
            baseline,
            current,
            alpha=1.5,
        )


def test_negative_mean_threshold_is_rejected():
    baseline = pd.DataFrame({"amount": range(10)})
    current = pd.DataFrame({"amount": range(10)})

    with pytest.raises(ValueError):
        detect_distribution_drift(
            baseline,
            current,
            mean_change_threshold=-0.1,
        )