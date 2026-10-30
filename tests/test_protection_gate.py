import pytest

from src.protection_gate import evaluate_pipeline_gate


def test_critical_incident_blocks_pipeline():
    analysis = {
        "overall_status": "critical",
        "findings": [
            {"type": "missing_value_anomaly", "severity": "high"},
            {"type": "duplicate_anomaly", "severity": "medium"},
            {"type": "distribution_drift", "severity": "high"},
        ],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "BLOCK"
    assert result["downstream_processing_allowed"] is False
    assert result["human_review_required"] is True


def test_high_severity_requires_review():
    analysis = {
        "overall_status": "high",
        "findings": [
            {"type": "distribution_drift", "severity": "high"},
        ],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["downstream_processing_allowed"] is False
    assert result["human_review_required"] is True


def test_medium_severity_requires_review():
    analysis = {
        "overall_status": "medium",
        "findings": [
            {"type": "duplicate_anomaly", "severity": "medium"},
        ],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["downstream_processing_allowed"] is False


def test_low_severity_allows_pipeline():
    analysis = {
        "overall_status": "low",
        "findings": [
            {"type": "minor_anomaly", "severity": "low"},
        ],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "ALLOW"
    assert result["downstream_processing_allowed"] is True
    assert result["human_review_required"] is False


def test_empty_findings_allow_pipeline():
    analysis = {
        "overall_status": "healthy",
        "findings": [],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "ALLOW"
    assert result["finding_counts"]["total"] == 0


def test_failed_analysis_blocks_pipeline():
    analysis = {
        "overall_status": "error",
        "findings": [],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "BLOCK"
    assert result["downstream_processing_allowed"] is False
    assert result["human_review_required"] is True


def test_invalid_analysis_raises_error():
    with pytest.raises(TypeError):
        evaluate_pipeline_gate("not an analysis dictionary")


def test_unknown_severity_raises_error():
    analysis = {
        "overall_status": "high",
        "findings": [
            {"type": "unexpected_issue", "severity": "extreme"},
        ],
    }

    with pytest.raises(ValueError):
        evaluate_pipeline_gate(analysis)