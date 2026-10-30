import json
from pathlib import Path

from scripts.evaluate_protection import evaluate


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "protection"


def test_evaluation_metrics_are_calculated_from_fixture_results(tmp_path):
    result = evaluate(
        fixture_dir=FIXTURE_DIR,
        output_dir=tmp_path,
        run_ai=False,
    )

    metrics = result["metrics"]
    assert result["case_count"] == 7
    assert result["failed_case_count"] == 0
    assert metrics["detection_recall"] == 1
    assert metrics["injected_anomaly_count"] == 7
    assert metrics["false_positive_rate"] == 0
    assert metrics["negative_case_count"] == 1
    assert metrics["protection_decision_accuracy"] == 1
    assert metrics["analysis_latency_seconds"]["sample_count"] == 7
    assert metrics["ai_explanation_latency_seconds"] is None
    assert metrics["ai_failure_count"] == 0
    assert metrics["protection_enforcement_reliability"] == 1
    assert metrics["protection_enforcement_case_count"] == 9

    saved = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert saved == result
    markdown = (tmp_path / "evaluation_report.md").read_text(encoding="utf-8")
    assert "Scenario results" in markdown
    assert "synthetic examples" in markdown
