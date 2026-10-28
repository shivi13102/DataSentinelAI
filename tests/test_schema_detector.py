import pandas as pd

from src.detectors.schema_detector import detect_schema_changes


def test_detect_added_column():
    baseline = pd.DataFrame(
        {
            "customer_id": ["C101", "C102"],
            "amount": [1500, 2200],
        }
    )

    current = pd.DataFrame(
        {
            "customer_id": ["C101", "C102"],
            "amount": [1500, 2200],
            "region": ["South", "North"],
        }
    )

    findings = detect_schema_changes(baseline, current)

    assert len(findings) == 1
    assert findings[0]["category"] == "added_column"
    assert findings[0]["column"] == "region"


def test_detect_removed_column():
    baseline = pd.DataFrame(
        {
            "customer_id": ["C101", "C102"],
            "amount": [1500, 2200],
        }
    )

    current = pd.DataFrame(
        {
            "customer_id": ["C101", "C102"],
        }
    )

    findings = detect_schema_changes(baseline, current)

    assert len(findings) == 1
    assert findings[0]["category"] == "removed_column"
    assert findings[0]["column"] == "amount"


def test_detect_dtype_change():
    baseline = pd.DataFrame(
        {
            "amount": [1500, 2200],
        }
    )

    current = pd.DataFrame(
        {
            "amount": ["1500", "2200"],
        }
    )

    findings = detect_schema_changes(baseline, current)

    assert len(findings) == 1
    assert findings[0]["category"] == "dtype_change"
    assert findings[0]["column"] == "amount"
    assert findings[0]["baseline_value"] == "int64"
    assert findings[0]["current_value"] == "str"


def test_identical_schemas_produce_no_findings():
    baseline = pd.DataFrame(
        {
            "customer_id": ["C101", "C102"],
            "amount": [1500, 2200],
        }
    )

    current = pd.DataFrame(
        {
            "customer_id": ["C103", "C104"],
            "amount": [1700, 2400],
        }
    )

    findings = detect_schema_changes(baseline, current)

    assert findings == []