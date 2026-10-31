import json
from types import SimpleNamespace

import pandas as pd

from src.agents import investigation_agent as agent
from src.analysis_engine import analyze_datasets
from src.graph.workflow import build_workflow
from src.protection_gate import evaluate_pipeline_gate


def _frames():
    baseline = pd.DataFrame({"reading": [float(i % 10) for i in range(100)]})
    current = baseline.copy()
    current.loc[:19, "reading"] = float("nan")
    return baseline, current


def _model_plan(monkeypatch, calls):
    def post(_url, *, json, timeout):
        assert timeout == 30
        assert json["options"]["num_predict"] == 180
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"done": True, "response": __import__("json").dumps({"calls": calls})},
        )
    monkeypatch.setattr(agent.requests, "post", post)


def test_tool_selection_rejects_excess_unknown_and_duplicate_calls(monkeypatch):
    baseline, current = _frames()
    analysis = analyze_datasets(baseline, current)
    monkeypatch.setenv("DATASENTINEL_AGENTIC_INVESTIGATION", "true")
    valid = {"tool": "inspect_null_spike", "column": "reading"}
    for calls in (
        [valid] * 3,
        [{"tool": "inspect_null_spike", "column": "other"}],
        [{"tool": "arbitrary_code", "column": "reading"}],
        [valid, valid],
    ):
        _model_plan(monkeypatch, calls)
        updated, audit = agent.investigate(baseline, current, analysis)
        assert audit["status"] == "error"
        assert audit["tool_calls"] == []
        assert evaluate_pipeline_gate(updated)["decision"] == "BLOCK"


def test_deterministic_tool_output_and_audit(monkeypatch):
    baseline, current = _frames()
    analysis = analyze_datasets(baseline, current)
    monkeypatch.setenv("DATASENTINEL_AGENTIC_INVESTIGATION", "true")
    _model_plan(monkeypatch, [{"tool": "inspect_null_spike", "column": "reading"}])
    first, audit = agent.investigate(baseline, current, analysis)
    second, second_audit = agent.investigate(baseline, current, analysis)
    assert audit == second_audit
    assert first["findings"] == second["findings"]
    assert audit["status"] == "complete"
    assert audit["tool_calls"][0]["inputs"] == {"column": "reading"}
    assert audit["tool_calls"][0]["output"]
    assert audit["tool_calls"][0]["error"] is None
    assert evaluate_pipeline_gate(first)["finding_counts"]["total"] == first["total_findings"]


def test_real_followup_detector_adds_a_new_finding_to_gate(monkeypatch):
    baseline = pd.DataFrame({"reading": [0.0] * 50 + [1.0] * 50})
    current = baseline.copy()
    current.loc[:16, "reading"] = float("nan")
    current.loc[50:52, "reading"] = float("nan")
    initial = analyze_datasets(baseline, current)
    assert {finding["type"] for finding in initial["findings"]} == {"missing_value_anomaly"}
    monkeypatch.setenv("DATASENTINEL_AGENTIC_INVESTIGATION", "true")
    _model_plan(monkeypatch, [{"tool": "inspect_distribution", "column": "reading"}])
    updated, audit = agent.investigate(baseline, current, initial)
    assert audit["status"] == "complete"
    assert any(finding["type"] == "distribution_drift" for finding in updated["findings"])
    assert updated["total_findings"] == initial["total_findings"] + 1
    assert evaluate_pipeline_gate(updated)["finding_counts"]["total"] == updated["total_findings"]


def test_tool_failure_is_visible_and_blocks(monkeypatch):
    baseline, current = _frames()
    analysis = analyze_datasets(baseline, current)
    monkeypatch.setenv("DATASENTINEL_AGENTIC_INVESTIGATION", "true")
    _model_plan(monkeypatch, [{"tool": "inspect_null_spike", "column": "reading"}])
    def fail(*_args, **_kwargs):
        raise RuntimeError("private data")
    monkeypatch.setattr(agent, "detect_missing_value_anomalies", fail)
    updated, audit = agent.investigate(baseline, current, analysis)
    assert audit["status"] == "error"
    assert audit["tool_calls"][0]["error"] == "Tool failed (RuntimeError)."
    assert "private data" not in json.dumps(audit)
    assert evaluate_pipeline_gate(updated)["decision"] == "BLOCK"


def test_invalid_tool_output_is_visible_and_blocks(monkeypatch):
    baseline, current = _frames()
    analysis = analyze_datasets(baseline, current)
    monkeypatch.setenv("DATASENTINEL_AGENTIC_INVESTIGATION", "true")
    _model_plan(monkeypatch, [{"tool": "inspect_null_spike", "column": "reading"}])
    monkeypatch.setattr(
        agent, "detect_missing_value_anomalies",
        lambda *_args, **_kwargs: [{"type": "missing_value_anomaly", "column": "reading", "severity": "high", "value": float("nan")}],
    )
    updated, audit = agent.investigate(baseline, current, analysis)
    assert audit["status"] == "error"
    assert audit["tool_calls"][0]["output"] is None
    assert audit["tool_calls"][0]["error"] == "Tool failed (ValueError)."
    assert evaluate_pipeline_gate(updated)["decision"] == "BLOCK"


def test_followup_findings_reach_gate_and_ai_cannot_override(monkeypatch):
    baseline, current = _frames()
    initial = analyze_datasets(baseline, current)
    monkeypatch.setenv("DATASENTINEL_AGENTIC_INVESTIGATION", "true")
    _model_plan(monkeypatch, [{"tool": "inspect_null_spike", "column": "reading"}])
    def extra_finding(_before, _after, **_kwargs):
        return [{
            "type": "missing_value_anomaly", "category": "followup_null_pattern",
            "column": "reading", "severity": "high", "description": "Measured follow-up risk.",
        }]
    monkeypatch.setattr(agent, "detect_missing_value_anomalies", extra_finding)
    monkeypatch.setattr(
        "src.graph.workflow.explain_findings",
        lambda _analysis: {"status": "success", "explanation": {"human_review_required": False, "recommended_actions": ["Allow"]}},
    )
    report = build_workflow().invoke({"baseline": baseline, "current": current})["final_report"]
    assert report["analysis"]["total_findings"] == initial["total_findings"] + 1
    assert report["protection"]["finding_counts"]["total"] == initial["total_findings"] + 1
    assert report["protection"]["decision"] == "BLOCK"
    assert report["human_review_required"] is True


def test_disabled_investigation_preserves_existing_gate(monkeypatch):
    baseline, current = _frames()
    monkeypatch.delenv("DATASENTINEL_AGENTIC_INVESTIGATION", raising=False)
    monkeypatch.setattr("src.graph.workflow.explain_findings", lambda _analysis: {"status": "skipped"})
    report = build_workflow().invoke({"baseline": baseline, "current": current})["final_report"]
    assert report["investigation"] == {"status": "disabled", "tool_calls": []}
    assert report["protection"]["decision"] == evaluate_pipeline_gate(analyze_datasets(baseline, current))["decision"]


def test_unavailable_selection_blocks_enabled_workflow(monkeypatch):
    baseline, current = _frames()
    monkeypatch.setenv("DATASENTINEL_AGENTIC_INVESTIGATION", "true")
    def unavailable(_analysis):
        raise ConnectionError("private connection detail")
    monkeypatch.setattr(agent, "select_tools", unavailable)
    monkeypatch.setattr("src.graph.workflow.explain_findings", lambda _analysis: {"status": "success"})
    report = build_workflow().invoke({"baseline": baseline, "current": current})["final_report"]
    assert report["investigation"]["status"] == "error"
    assert report["investigation"]["tool_calls"] == []
    assert "private connection detail" not in json.dumps(report)
    assert report["analysis"]["overall_status"] == "incomplete"
    assert report["protection"]["decision"] == "BLOCK"
