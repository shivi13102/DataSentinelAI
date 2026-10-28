import pandas as pd
import pytest

from src.detectors.duplicate_detector import (
    detect_duplicate_anomalies,
)


def test_detect_duplicate_rate_increase():
    baseline = pd.DataFrame(
        {
            "transaction_id": ["T101", "T102", "T103", "T104"],
            "amount": [100, 200, 300, 400],
        }
    )

    current = pd.DataFrame(
        {
            "transaction_id": ["T101", "T102", "T102", "T104"],
            "amount": [100, 200, 200, 400],
        }
    )

    findings = detect_duplicate_anomalies(
        baseline,
        current,
        increase_threshold=5.0,
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding["category"] == "duplicate_rate_increase"
    assert finding["baseline_value"]["duplicate_count"] == 0
    assert finding["current_value"]["duplicate_count"] == 1
    assert finding["current_value"]["duplicate_percentage"] == 25.0
    assert finding["change_percentage_points"] == 25.0
    assert finding["severity"] == "high"


def test_no_anomaly_when_duplicate_rate_is_unchanged():
    baseline = pd.DataFrame(
        {
            "transaction_id": ["T101", "T102", "T102", "T104"],
            "amount": [100, 200, 200, 400],
        }
    )

    current = pd.DataFrame(
        {
            "transaction_id": ["T201", "T202", "T202", "T204"],
            "amount": [100, 200, 200, 400],
        }
    )

    findings = detect_duplicate_anomalies(baseline, current)

    assert findings == []


def test_no_anomaly_when_duplicate_rate_is_below_threshold():
    baseline = pd.DataFrame(
        {
            "transaction_id": ["T101", "T102", "T103", "T104"],
            "amount": [100, 200, 300, 400],
        }
    )

    current = pd.DataFrame(
        {
            "transaction_id": ["T101", "T102", "T103", "T103"],
            "amount": [100, 200, 300, 300],
        }
    )

    findings = detect_duplicate_anomalies(
        baseline,
        current,
        increase_threshold=30.0,
    )

    assert findings == []


def test_empty_datasets_produce_no_findings():
    baseline = pd.DataFrame(columns=["transaction_id", "amount"])

    current = pd.DataFrame(
        {
            "transaction_id": ["T101"],
            "amount": [100],
        }
    )

    findings = detect_duplicate_anomalies(baseline, current)

    assert findings == []


def test_no_common_columns_produce_no_findings():
    baseline = pd.DataFrame({"customer_id": ["C101", "C102"]})

    current = pd.DataFrame({"transaction_id": ["T101", "T102"]})

    findings = detect_duplicate_anomalies(baseline, current)

    assert findings == []


def test_negative_threshold_is_rejected():
    baseline = pd.DataFrame({"amount": [100, 200]})
    current = pd.DataFrame({"amount": [100, 100]})

    with pytest.raises(ValueError):
        detect_duplicate_anomalies(
            baseline,
            current,
            increase_threshold=-1,
        )