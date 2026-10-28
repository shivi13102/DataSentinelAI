import pandas as pd
import pytest

from src.detectors.missing_value_detector import (
    detect_missing_value_anomalies,
)


def test_detect_missing_rate_increase():
    baseline = pd.DataFrame(
        {
            "amount": [100, 200, 300, 400],
        }
    )

    current = pd.DataFrame(
        {
            "amount": [100, None, None, 400],
        }
    )

    findings = detect_missing_value_anomalies(
        baseline,
        current,
        increase_threshold=10.0,
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding["category"] == "missing_rate_increase"
    assert finding["column"] == "amount"
    assert finding["baseline_value"]["missing_percentage"] == 0.0
    assert finding["current_value"]["missing_percentage"] == 50.0
    assert finding["change_percentage_points"] == 50.0
    assert finding["severity"] == "high"


def test_detect_entirely_missing_column():
    baseline = pd.DataFrame(
        {
            "amount": [100, 200, 300],
        }
    )

    current = pd.DataFrame(
        {
            "amount": [None, None, None],
        }
    )

    findings = detect_missing_value_anomalies(baseline, current)

    assert len(findings) == 1
    assert findings[0]["category"] == "entirely_missing_column"
    assert findings[0]["current_value"]["missing_percentage"] == 100.0


def test_no_anomaly_when_missing_rate_is_below_threshold():
    baseline = pd.DataFrame(
        {
            "amount": [100, 200, 300, 400],
        }
    )

    current = pd.DataFrame(
        {
            "amount": [100, 200, None, 400],
        }
    )

    findings = detect_missing_value_anomalies(
        baseline,
        current,
        increase_threshold=30.0,
    )

    assert findings == []


def test_unchanged_missing_rate_produces_no_findings():
    baseline = pd.DataFrame(
        {
            "amount": [100, None, 300, 400],
        }
    )

    current = pd.DataFrame(
        {
            "amount": [200, None, 400, 500],
        }
    )

    findings = detect_missing_value_anomalies(baseline, current)

    assert findings == []


def test_negative_threshold_is_rejected():
    baseline = pd.DataFrame({"amount": [100, 200]})
    current = pd.DataFrame({"amount": [100, None]})

    with pytest.raises(ValueError):
        detect_missing_value_anomalies(
            baseline,
            current,
            increase_threshold=-1,
        )