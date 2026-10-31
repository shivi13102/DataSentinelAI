
from __future__ import annotations

import logging
from typing import Any
from typing_extensions import TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from src.analysis_engine import analyze_datasets
from src.agents.reasoning_agent import explain_findings
from src.agents.investigation_agent import investigate
from src.protection_gate import evaluate_pipeline_gate


logger = logging.getLogger(__name__)


class DataSentinelState(TypedDict, total=False):
    """State passed between nodes in the DataSentinel AI workflow."""

    baseline: pd.DataFrame
    current: pd.DataFrame
    analysis_results: dict[str, Any]
    reasoning_results: dict[str, Any]
    investigation_results: dict[str, Any]
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
        logger.error(
            "Deterministic analysis failed (%s).",
            type(exc).__name__,
        )
        return {
            "error": (
                "Deterministic analysis failed; results are unavailable "
                f"({type(exc).__name__})."
            ),
        }


def generate_reasoning(state: DataSentinelState) -> dict[str, Any]:
    """Generate an AI explanation without losing Python findings."""

    analysis_results = state.get("analysis_results")

    if analysis_results is None:
        return {
            "reasoning_results": {
                "status": "skipped",
                "error": (
                    "AI investigation was skipped because deterministic "
                    "analysis did not complete."
                ),
            }
        }

    try:
        reasoning_results = explain_findings({
            **analysis_results,
            "investigation": state.get("investigation_results"),
        })

        return {
            "reasoning_results": reasoning_results,
        }

    except Exception as exc:
        logger.error("AI reasoning failed (%s).", type(exc).__name__)
        return {
            "reasoning_results": {
                "status": "error",
                "error": (
                    "Local AI investigation is currently unavailable. "
                    "Deterministic data-quality analysis and pipeline "
                    "protection are operating normally. AI reasoning failed "
                    f"({type(exc).__name__})."
                ),
            }
        }


def run_investigation(state: DataSentinelState) -> dict[str, Any]:
    analysis = state.get("analysis_results")
    if not isinstance(analysis, dict):
        return {"investigation_results": {"status": "skipped", "tool_calls": []}}
    try:
        updated, audit = investigate(state["baseline"], state["current"], analysis)
    except Exception as exc:
        logger.error("Agentic investigation failed (%s).", type(exc).__name__)
        updated = {**analysis, "overall_status": "incomplete"}
        audit = {"status": "error", "tool_calls": [], "error": f"Investigation failed ({type(exc).__name__})."}
    return {"analysis_results": updated, "investigation_results": audit}


def protect_pipeline(state: DataSentinelState) -> dict[str, Any]:
    """Evaluate the pipeline gate using deterministic analysis results."""

    analysis_results = state.get("analysis_results")

    if analysis_results is None:
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
        logger.error("Protection gate failed (%s).", type(exc).__name__)
        return {
            "error": (
                "Protection gate failed; downstream processing is blocked "
                f"({type(exc).__name__})."
            ),
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
                    "Protection gate failed; downstream processing is blocked.",
                    "Downstream processing is blocked for safety.",
                ],
            }
        }


def build_report(state: DataSentinelState) -> dict[str, Any]:
    """Combine analysis, AI reasoning and protection results."""

    raw_analysis_results = state.get("analysis_results")
    analysis_results = raw_analysis_results
    if not isinstance(raw_analysis_results, dict):
        analysis_results = {
            "overall_status": "error",
            "findings": [],
        }

    reasoning_results = state.get(
        "reasoning_results",
        {
            "status": "skipped",
            "error": "No AI reasoning results were produced.",
        },
    )
    investigation_results = state.get("investigation_results", {"status": "disabled", "tool_calls": []})

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

    # The protection gate is authoritative.
    # An AI response can never override a BLOCK or REVIEW_REQUIRED decision.
    analysis_complete = (
        not state.get("error")
        and isinstance(raw_analysis_results, dict)
        and raw_analysis_results.get("overall_status")
        in {"healthy", "warning", "critical"}
        and isinstance(raw_analysis_results.get("findings"), list)
    )
    final_report = {
        "workflow_status": "success" if analysis_complete else "error",
        "overall_status": analysis_results.get(
            "overall_status",
            "error",
        ),
        "analysis": analysis_results,
        "ai_reasoning": reasoning_results,
        "investigation": investigation_results,
        "protection": protection_results,
        "human_review_required": protection_results.get(
            "human_review_required", True
        ),
        "error": state.get("error", ""),
    }

    return {
        "final_report": final_report,
    }


def build_workflow():
    """Build and compile the DataSentinel AI LangGraph workflow."""

    graph = StateGraph(DataSentinelState)

    graph.add_node("analyze_data", analyze_data)
    graph.add_node("run_investigation", run_investigation)
    graph.add_node("generate_reasoning", generate_reasoning)
    graph.add_node("protect_pipeline", protect_pipeline)
    graph.add_node("build_report", build_report)

    graph.add_edge(START, "analyze_data")
    graph.add_edge("analyze_data", "run_investigation")
    graph.add_edge("run_investigation", "protect_pipeline")
    graph.add_edge("protect_pipeline", "generate_reasoning")
    graph.add_edge("generate_reasoning", "build_report")
    graph.add_edge("build_report", END)

    return graph.compile()


# Compiled graph used by the application and tests.
data_sentinel_workflow = build_workflow()
