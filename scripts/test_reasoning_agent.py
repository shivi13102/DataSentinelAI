
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add the project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.reasoning_agent import explain_findings
from src.analysis_engine import analyze_datasets
from src.utils.data_loader import load_csv


def main() -> None:
    """Test the AI reasoning agent using the sample datasets."""

    baseline_path = PROJECT_ROOT / "data" / "raw" / "baseline.csv"
    current_path = PROJECT_ROOT / "data" / "raw" / "current.csv"

    print("=" * 60)
    print("DATASENTINEL AI - REASONING AGENT TEST")
    print("=" * 60)

    print("\n[1/3] Loading datasets...")

    baseline = load_csv(baseline_path)
    current = load_csv(current_path)

    print(f"Baseline: {baseline.shape}")
    print(f"Current:  {current.shape}")

    print("\n[2/3] Running Python analysis...")

    analysis_results = analyze_datasets(baseline, current)

    print(f"Overall status: {analysis_results['overall_status']}")
    print(f"Total findings: {analysis_results['total_findings']}")

    print("\n[3/3] Requesting AI explanation from Ollama...")
    print("This may take a little while on a CPU-only machine.")

    ai_results = explain_findings(analysis_results)

    if ai_results["status"] != "success":
        print("\nAI reasoning failed.")
        print(ai_results.get("error", "An unknown error occurred."))
        return

    explanation = ai_results["explanation"]

    print("\n" + "=" * 60)
    print("AI REASONING RESULTS")
    print("=" * 60)

    print("\nIncident summary:")
    print(explanation["incident_summary"])

    print("\nRoot-cause hypotheses:")
    print(
        json.dumps(
            explanation["root_cause_hypotheses"],
            indent=2
        )
    )

    print("\nPotential business impacts:")
    for impact in explanation["business_impacts"]:
        print(f"- {impact}")

    print("\nRecommended actions:")
    for action in explanation["recommended_actions"]:
        print(f"- {action}")

    print(
        "\nHuman review required:",
        explanation["human_review_required"]
    )

    report_path = PROJECT_ROOT / "reports" / "ai_reasoning.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(
            ai_results,
            report_file,
            indent=2,
            ensure_ascii=False
        )

    print(f"\nAI report saved to: {report_path}")
    print("\nREASONING AGENT TEST COMPLETED")


if __name__ == "__main__":
    main()
