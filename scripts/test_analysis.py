import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import json
from pathlib import Path

from src.analysis_engine import analyze_datasets
from src.utils.data_loader import load_csv


def main() -> None:
    """Load sample datasets and run the complete analysis engine."""

    project_root = Path(__file__).resolve().parents[1]

    baseline_path = project_root / "data" / "raw" / "baseline.csv"
    current_path = project_root / "data" / "raw" / "current.csv"

    print("=" * 60)
    print("DATASENTINEL AI - END-TO-END ANALYSIS TEST")
    print("=" * 60)

    # Step 1: Load both datasets.
    print("\n[1/3] Loading datasets...")

    baseline = load_csv(baseline_path)
    current = load_csv(current_path)

    print(f"Baseline loaded: {baseline.shape[0]} rows, {baseline.shape[1]} columns")
    print(f"Current loaded:  {current.shape[0]} rows, {current.shape[1]} columns")

    # Step 2: Run all five detectors.
    print("\n[2/3] Running analysis engine...")

    results = analyze_datasets(baseline, current)

    # Step 3: Display results.
    print("\n[3/3] Analysis results")
    print("-" * 60)
    print(f"Overall status:  {results['overall_status'].upper()}")
    print(f"Total findings:  {results['total_findings']}")
    print(f"Severity counts: {results['severity_counts']}")

    print("\nFindings by detector:")
    for finding_type, count in results["findings_by_type"].items():
        print(f"  {finding_type}: {count}")

    print("\nDetailed findings:")
    if results["findings"]:
        for number, finding in enumerate(results["findings"], start=1):
            print(f"\nFinding {number}:")
            print(json.dumps(finding, indent=2, default=str))
    else:
        print("No anomalies detected.")

    # Save a report for inspection.
    report_path = project_root / "reports" / "sample_analysis.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(results, report_file, indent=2, default=str)

    print("\n" + "=" * 60)
    print("END-TO-END ANALYSIS COMPLETED")
    print(f"Report saved to: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()