
import pandas as pd
import pytest

from src.analysis_engine import analyze_datasets


def test_identical_datasets_are_healthy():
    baseline = pd.DataFrame(
        {
            "age": [20, 25, 30, 35, 40, 45, 50, 55],
            "status": ["A", "B"] * 4,
        }
    )

    current = baseline.copy(deep=True)

    result = analyze_datasets(baseline, current)

    assert result["overall_status"] == "healthy"
    assert result["total_findings"] == 0
    assert result["severity_counts"] == {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }


def test_schema_removal_is_reported():
    baseline = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4],
            "amount": [100, 200, 300, 400],
        }
    )

    current = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4],
        }
    )

    result = analyze_datasets(baseline, current)

    assert result["total_findings"] >= 1
    assert result["overall_status"] == "critical"

    removed_columns = [
        finding
        for finding in result["findings"]
        if finding["category"] == "removed_column"
    ]

    assert len(removed_columns) == 1
    assert removed_columns[0]["column"] == "amount"


def test_result_contains_dataset_statistics():
    baseline = pd.DataFrame(
        {
            "age": [20, 30, 40, 50],
            "status": ["A", "B", "A", "B"],
        }
    )

    current = pd.DataFrame(
        {
            "age": [21, 31, 41, 51, 61],
            "status": ["A", "B", "A", "B", "A"],
        }
    )

    result = analyze_datasets(baseline, current)

    assert result["baseline_rows"] == 4
    assert result["current_rows"] == 5
    assert result["baseline_columns"] == 2
    assert result["current_columns"] == 2
    assert "analysis_timestamp" in result
    assert "findings" in result


def test_invalid_baseline_type_is_rejected():
    current = pd.DataFrame({"value": [1, 2, 3]})

    with pytest.raises(TypeError):
        analyze_datasets(
            {"value": [1, 2, 3]},
            current,
        )


def test_invalid_current_type_is_rejected():
    baseline = pd.DataFrame({"value": [1, 2, 3]})

    with pytest.raises(TypeError):
        analyze_datasets(
            baseline,
            {"value": [1, 2, 3]},
        )


def test_empty_datasets_are_rejected_instead_of_marked_healthy():
    with pytest.raises(ValueError, match="at least one row"):
        analyze_datasets(pd.DataFrame({"value": []}), pd.DataFrame({"value": []}))


def test_input_datasets_are_not_modified():
    baseline = pd.DataFrame(
        {
            "age": [20, 30, 40, 50],
            "status": ["A", "B", "A", "B"],
        }
    )

    current = pd.DataFrame(
        {
            "age": [21, 31, 41, 51],
            "status": ["A", "B", "A", "B"],
        }
    )

    baseline_before = baseline.copy(deep=True)
    current_before = current.copy(deep=True)

    analyze_datasets(baseline, current)

    pd.testing.assert_frame_equal(baseline, baseline_before)
    pd.testing.assert_frame_equal(current, current_before)
