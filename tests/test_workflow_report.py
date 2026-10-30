import pandas as pd

from src.graph.workflow import (
    build_report,
    build_workflow,
    generate_reasoning,
    protect_pipeline,
)
from src.protection_gate import evaluate_pipeline_gate


def test_ai_review_flag_does_not_change_allow_protection_decision():
    analysis = {"overall_status": "healthy", "findings": []}
    protection = evaluate_pipeline_gate(analysis)
    report = build_report(
        {
            "analysis_results": analysis,
            "reasoning_results": {
                "status": "success",
                "explanation": {"human_review_required": True},
            },
            "protection_results": protection,
        }
    )["final_report"]

    assert report["protection"]["decision"] == "ALLOW"
    assert report["protection"]["downstream_processing_allowed"] is True
    assert report["human_review_required"] is False


def test_ai_recommendation_cannot_change_block_decision_or_evidence():
    analysis = {
        "overall_status": "critical",
        "findings": [{"type": "schema_change", "severity": "high"}],
    }
    protection = evaluate_pipeline_gate(analysis)
    report = build_report(
        {
            "analysis_results": analysis,
            "reasoning_results": {
                "status": "success",
                "explanation": {
                    "recommended_actions": ["Proceed with processing."]
                },
            },
            "protection_results": protection,
        }
    )["final_report"]

    assert report["analysis"] == analysis
    assert report["protection"]["decision"] == "BLOCK"
    assert report["protection"]["downstream_processing_allowed"] is False


def test_ai_exception_details_are_not_returned(monkeypatch):
    def fail_reasoning(_analysis):
        raise RuntimeError("sensitive exception details")

    monkeypatch.setattr("src.graph.workflow.explain_findings", fail_reasoning)
    result = generate_reasoning(
        {"analysis_results": {"overall_status": "healthy", "findings": []}}
    )

    assert result["reasoning_results"]["status"] == "error"
    assert "sensitive exception details" not in result["reasoning_results"]["error"]


def test_gate_exception_details_are_not_returned_and_block(monkeypatch):
    def fail_gate(_analysis):
        raise RuntimeError("sensitive exception details")

    monkeypatch.setattr("src.graph.workflow.evaluate_pipeline_gate", fail_gate)
    result = protect_pipeline(
        {"analysis_results": {"overall_status": "healthy", "findings": []}}
    )

    assert result["protection_results"]["decision"] == "BLOCK"
    assert result["protection_results"]["downstream_processing_allowed"] is False
    assert "sensitive exception details" not in str(result)


def test_langgraph_evaluates_gate_before_optional_ai(monkeypatch):
    execution_order = []
    original_gate = evaluate_pipeline_gate

    def observe_gate(analysis):
        execution_order.append("gate")
        return original_gate(analysis)

    def unavailable_ai(_analysis):
        execution_order.append("ai")
        return {"status": "error", "error": "Local model unavailable."}

    monkeypatch.setattr("src.graph.workflow.evaluate_pipeline_gate", observe_gate)
    monkeypatch.setattr("src.graph.workflow.explain_findings", unavailable_ai)
    frame = pd.DataFrame(
        {
            "record_key": range(100),
            "measure_value": [index % 10 for index in range(100)],
            "segment_code": ["A" if index % 2 else "B" for index in range(100)],
        }
    )

    result = build_workflow().invoke({"baseline": frame, "current": frame.copy()})

    assert execution_order == ["gate", "ai"]
    assert result["final_report"]["protection"]["decision"] == "ALLOW"
    assert result["final_report"]["ai_reasoning"]["status"] == "error"
    assert result["final_report"]["workflow_status"] == "success"


def test_ai_failure_cannot_change_deterministic_gate_outcomes(monkeypatch):
    monkeypatch.setattr(
        "src.graph.workflow.explain_findings",
        lambda _analysis: {
            "status": "error",
            "error": "Local AI investigation is currently unavailable.",
        },
    )
    baseline = pd.DataFrame(
        {
            "record_key": range(100),
            "measure_value": [index % 10 for index in range(100)],
            "segment_code": ["A" if index % 2 else "B" for index in range(100)],
        }
    )

    scenarios = [
        ("healthy", baseline.copy(), "ALLOW"),
        (
            "review",
            baseline.assign(
                measure_value=pd.Series(
                    [None] * 20 + [index % 10 for index in range(80)],
                    dtype="float64",
                )
            ),
            "REVIEW_REQUIRED",
        ),
        (
            "critical",
            baseline.drop(columns=["measure_value"]),
            "BLOCK",
        ),
    ]

    workflow = build_workflow()
    for _name, current, expected_decision in scenarios:
        report = workflow.invoke(
            {"baseline": baseline, "current": current}
        )["final_report"]

        assert report["protection"]["decision"] == expected_decision
        assert report["ai_reasoning"]["status"] == "error"
        assert report["workflow_status"] == "success"
