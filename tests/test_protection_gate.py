import pytest

from src.protection_gate import (
    enforce_downstream,
    evaluate_pipeline_gate,
)


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


def test_medium_severity_requires_review():
    analysis = {
        "overall_status": "warning",
        "findings": [
            {"type": "duplicate_anomaly", "severity": "medium"},
        ],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["downstream_processing_allowed"] is False
    assert result["human_review_required"] is True


def test_low_severity_allows_pipeline():
    analysis = {
        "overall_status": "healthy",
        "findings": [
            {"type": "minor_anomaly", "severity": "low"},
        ],
    }

    result = evaluate_pipeline_gate(analysis)

    assert result["decision"] == "ALLOW"
    assert result["downstream_processing_allowed"] is True
    assert result["human_review_required"] is False


def test_empty_findings_allow_pipeline():
    result = evaluate_pipeline_gate(
        {"overall_status": "healthy", "findings": []}
    )

    assert result["decision"] == "ALLOW"
    assert result["finding_counts"]["total"] == 0


@pytest.mark.parametrize("status", ["error", "failed", "incomplete", "unverified"])
def test_failed_analysis_status_blocks_pipeline(status):
    result = evaluate_pipeline_gate(
        {"overall_status": status, "findings": []}
    )

    assert result["decision"] == "BLOCK"
    assert result["downstream_processing_allowed"] is False
    assert result["human_review_required"] is True


@pytest.mark.parametrize(
    "analysis",
    [
        {"findings": []},
        {"overall_status": "", "findings": []},
        {"overall_status": "unknown", "findings": []},
        {"overall_status": "healthy"},
        {"overall_status": "healthy", "findings": ["not a finding"]},
        {"overall_status": "healthy", "findings": [{"type": "drift"}]},
        {
            "overall_status": "healthy",
            "findings": [{"severity": "low"}],
        },
        {
            "overall_status": "healthy",
            "findings": [{"type": "", "severity": "low"}],
        },
        {
            "overall_status": "healthy",
            "findings": [{"type": "drift", "severity": "urgent"}],
        },
    ],
)
def test_malformed_or_unknown_analysis_never_allows(analysis):
    with pytest.raises((TypeError, ValueError)):
        evaluate_pipeline_gate(analysis)


def test_non_dictionary_analysis_is_rejected():
    with pytest.raises(TypeError):
        evaluate_pipeline_gate("not an analysis dictionary")


def test_critical_finding_cannot_be_downgraded_by_healthy_status():
    result = evaluate_pipeline_gate(
        {
            "overall_status": "healthy",
            "findings": [{"type": "distribution_drift", "severity": "high"}],
        }
    )

    assert result["decision"] == "BLOCK"
    assert result["downstream_processing_allowed"] is False
    assert "contradict" in result["reasons"][0]


def test_medium_finding_cannot_be_downgraded_by_healthy_status():
    result = evaluate_pipeline_gate(
        {
            "overall_status": "healthy",
            "findings": [{"type": "drift", "severity": "medium"}],
        }
    )

    assert result["decision"] == "BLOCK"
    assert result["downstream_processing_allowed"] is False


def test_analysis_counters_must_agree_with_findings():
    result = evaluate_pipeline_gate(
        {
            "overall_status": "warning",
            "total_findings": 0,
            "severity_counts": {"medium": 0},
            "findings": [{"type": "drift", "severity": "medium"}],
        }
    )

    assert result["decision"] == "BLOCK"


@pytest.mark.parametrize(
    "counts",
    [
        [],
        {"unknown": 0},
        {"low": True},
        {"low": -1},
    ],
)
def test_malformed_severity_counts_are_rejected(counts):
    with pytest.raises(ValueError):
        evaluate_pipeline_gate(
            {
                "overall_status": "healthy",
                "severity_counts": counts,
                "findings": [],
            }
        )


def test_downstream_executor_invokes_operation_only_for_allow():
    calls = []
    allowed = evaluate_pipeline_gate(
        {"overall_status": "healthy", "findings": []}
    )

    executed, value = enforce_downstream(
        allowed,
        lambda: calls.append("executed") or "result",
    )

    assert executed is True
    assert value == "result"
    assert calls == ["executed"]


@pytest.mark.parametrize(
    "analysis",
    [
        {
            "overall_status": "warning",
            "findings": [{"type": "drift", "severity": "medium"}],
        },
        {
            "overall_status": "critical",
            "findings": [{"type": "schema_change", "severity": "high"}],
        },
        {"overall_status": "failed", "findings": []},
    ],
)
def test_downstream_executor_never_invokes_operation_without_allow(analysis):
    calls = []
    protection = evaluate_pipeline_gate(analysis)

    executed, value = enforce_downstream(
        protection,
        lambda: calls.append("executed"),
    )

    assert executed is False
    assert value is None
    assert calls == []


def test_ai_explanation_cannot_override_protection_result():
    calls = []
    protection = evaluate_pipeline_gate(
        {
            "overall_status": "critical",
            "findings": [{"type": "schema_change", "severity": "high"}],
        }
    )
    ai_explanation = {"recommendation": "Proceed despite the block"}

    executed, _ = enforce_downstream(
        protection,
        lambda: calls.append(ai_explanation),
    )

    assert executed is False
    assert calls == []


def test_invalid_or_missing_protection_decision_fails_closed():
    calls = []
    for protection in ({}, {"decision": "UNSET"}):
        with pytest.raises(ValueError):
            enforce_downstream(
                protection,
                lambda: calls.append("executed"),
            )
    assert calls == []


def test_allow_with_inconsistent_fields_fails_closed():
    calls = []
    protection = {
        "decision": "ALLOW",
        "downstream_processing_allowed": False,
        "human_review_required": False,
    }

    with pytest.raises(ValueError):
        enforce_downstream(
            protection,
            lambda: calls.append("executed"),
        )
    assert calls == []


def test_downstream_operation_errors_are_not_suppressed():
    def operation():
        raise RuntimeError("downstream error")

    protection = evaluate_pipeline_gate(
        {"overall_status": "healthy", "findings": []}
    )

    with pytest.raises(RuntimeError, match="downstream error"):
        enforce_downstream(protection, operation)
