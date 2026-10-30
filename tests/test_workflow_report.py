from src.graph.workflow import (
    build_report,
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
