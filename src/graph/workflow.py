
from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from src.analysis_engine import analyze_datasets
from src.agents.reasoning_agent import explain_findings
from src.protection_gate import evaluate_pipeline_gate


class DataSentinelState(TypedDict, total=False):
    """State passed between nodes in the DataSentinel AI workflow."""

    baseline: pd.DataFrame
    current: pd.DataFrame
    analysis_results: dict[str, Any]
    reasoning_results: dict[str, Any]
    protection_results: dict[str, Any]
    final_report: dict[str, Any]
    error: str


def analyze_data(state: DataSentinelState) -> dict[str, Any]:
    """Run deterministic Python-based data quality analysis."""

    try:
        baseline = state["baseline"]
        current = state["current"]

        analysis_results = analyze_datasets(
            baseline=baseline,
            current=current,
        )

        return {
            "analysis_results": analysis_results,
            "error": "",
        }

    except Exception as exc:
        return {
            "error": f"Data analysis failed: {exc}",
        }


def generate_reasoning(state: DataSentinelState) -> dict[str, Any]:
    """Generate an AI explanation without losing Python findings."""

    analysis_results = state.get("analysis_results")

    if not analysis_results:
        return {
            "reasoning_results": {
                "status": "skipped",
                "error": "AI reasoning skipped because data analysis failed.",
            }
        }

    try:
        reasoning_results = explain_findings(analysis_results)

        return {
            "reasoning_results": reasoning_results,
        }

    except Exception as exc:
        return {
            "reasoning_results": {
                "status": "error",
                "error": f"AI reasoning failed: {exc}",
            }
        }


def protect_pipeline(state: DataSentinelState) -> dict[str, Any]:
    """Evaluate the pipeline gate using deterministic analysis results."""

    analysis_results = state.get("analysis_results")

    if not analysis_results:
        return {
            "protection_results": {
                "decision": "BLOCK",
                "downstream_processing_allowed": False,
                "human_review_required": True,
                "finding_counts": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "total": 0,
                },
                "reasons": [
                    "Data analysis failed or produced no results. "
                    "Downstream processing is blocked.",
                ],
            }
        }

    try:
        protection_results = evaluate_pipeline_gate(analysis_results)

        return {
            "protection_results": protection_results,
        }

    except Exception as exc:
        # Fail closed: if the gate itself fails, do not allow processing.
        return {
            "protection_results": {
                "decision": "BLOCK",
                "downstream_processing_allowed": False,
                "human_review_required": True,
                "finding_counts": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "total": 0,
                },
                "reasons": [
                    f"Protection gate failed: {exc}",
                    "Downstream processing is blocked for safety.",
                ],
            }
        }


def build_report(state: DataSentinelState) -> dict[str, Any]:
    """Combine analysis, AI reasoning and protection results."""

    analysis_results = state.get("analysis_results", {})

    reasoning_results = state.get(
        "reasoning_results",
        {
            "status": "skipped",
            "error": "No AI reasoning results were produced.",
        },
    )

    protection_results = state.get(
        "protection_results",
        {
            "decision": "BLOCK",
            "downstream_processing_allowed": False,
            "human_review_required": True,
            "reasons": [
                "No protection-gate result is available. "
                "Downstream processing is blocked.",
            ],
        },
    )

    explanation = reasoning_results.get("explanation", {})

    human_review_required = (
        protection_results.get("human_review_required", True)
        or explanation.get("human_review_required", False)
    )

    # The protection gate is authoritative.
    # An AI response can never override a BLOCK or REVIEW_REQUIRED decision.
    final_report = {
        "workflow_status": (
            "success" if analysis_results else "error"
        ),
        "overall_status": analysis_results.get(
            "overall_status",
            "error",
        ),
        "analysis": analysis_results,
        "ai_reasoning": reasoning_results,
        "protection": protection_results,
        "human_review_required": human_review_required,
        "error": state.get("error", ""),
    }

    return {
        "final_report": final_report,
    }


def build_workflow():
    """Build and compile the DataSentinel AI LangGraph workflow."""

    graph = StateGraph(DataSentinelState)

    graph.add_node("analyze_data", analyze_data)
    graph.add_node("generate_reasoning", generate_reasoning)
    graph.add_node("protect_pipeline", protect_pipeline)
    graph.add_node("build_report", build_report)

    graph.add_edge(START, "analyze_data")
    graph.add_edge("analyze_data", "generate_reasoning")
    graph.add_edge("generate_reasoning", "protect_pipeline")
    graph.add_edge("protect_pipeline", "build_report")
    graph.add_edge("build_report", END)

    return graph.compile()


# Compiled graph used by the application and tests.
data_sentinel_workflow = build_workflow()
