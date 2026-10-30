
from __future__ import annotations

import pandas as pd

from src.graph.workflow import data_sentinel_workflow


def main() -> None:
    """Run the complete workflow against the sample datasets."""

    print("=" * 60)
    print("DATASENTINEL AI - LANGGRAPH WORKFLOW TEST")
    print("=" * 60)

    print("\n[1/3] Loading sample datasets...")

    baseline = pd.read_csv("data/raw/baseline.csv")
    current = pd.read_csv("data/raw/current.csv")

    print(f"Baseline shape: {baseline.shape}")
    print(f"Current shape:  {current.shape}")

    print("\n[2/3] Running LangGraph workflow...")

    result = data_sentinel_workflow.invoke(
        {
            "baseline": baseline,
            "current": current,
        }
    )

    report = result["final_report"]
    analysis = report["analysis"]
    reasoning = report["ai_reasoning"]

    print("\n[3/3] Workflow results")
    print("-" * 60)

    print(f"Workflow status: {report['workflow_status']}")
    print(f"Overall status:  {report['overall_status']}")
    print(f"Total findings:  {analysis.get('total_findings', 0)}")
    print(f"AI status:       {reasoning.get('status', 'unknown')}")
    print(f"Human review:    {report['human_review_required']}")

    if analysis.get("findings"):
        print("\nDetected findings:")

        for finding in analysis["findings"]:
            print(
                f"- [{finding.get('severity', 'unknown').upper()}] "
                f"{finding.get('type', 'unknown')}"
            )

    if reasoning.get("status") == "success":
        explanation = reasoning["explanation"]

        print("\nAI incident summary:")
        print(explanation["incident_summary"])

        print("\nAI recommendations:")

        for action in explanation["recommended_actions"]:
            print(f"- {action}")

    elif reasoning.get("error"):
        print("\nAI reasoning message:")
        print(reasoning["error"])

    if report.get("error"):
        print("\nWorkflow error:")
        print(report["error"])

    print("\n" + "=" * 60)
    print("WORKFLOW TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()