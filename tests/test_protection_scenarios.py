import json
from pathlib import Path

import pytest

from src.analysis_engine import analyze_datasets
from src.protection_gate import evaluate_pipeline_gate
from src.utils.data_loader import load_csv


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "protection"
MANIFEST = json.loads(
    (FIXTURE_DIR / "evaluation_manifest.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("scenario", MANIFEST["scenarios"], ids=lambda item: item["id"])
def test_real_csv_scenario_produces_manifest_findings_and_decision(scenario):
    baseline = load_csv(FIXTURE_DIR / scenario["baseline"])
    current = load_csv(FIXTURE_DIR / scenario["current"])

    analysis = analyze_datasets(baseline, current)
    protection = evaluate_pipeline_gate(analysis)

    actual_types = sorted(finding["type"] for finding in analysis["findings"])
    actual_severities = sorted(
        finding["severity"] for finding in analysis["findings"]
    )
    expected_types = sorted(scenario["expected_finding_types"])
    expected_severities = sorted(scenario["expected_severities"])

    assert actual_types == expected_types
    assert actual_severities == expected_severities
    assert protection["decision"] == scenario["expected_decision"]
    assert protection["downstream_processing_allowed"] is (
        scenario["expected_decision"] == "ALLOW"
    )
    assert analysis["baseline_rows"] == len(baseline)
    assert analysis["current_rows"] == len(current)
    assert analysis["baseline_columns"] == len(baseline.columns)
    assert analysis["current_columns"] == len(current.columns)


@pytest.mark.parametrize("scenario", MANIFEST["scenarios"], ids=lambda item: item["id"])
def test_real_csv_scenario_is_deterministic(scenario):
    baseline = load_csv(FIXTURE_DIR / scenario["baseline"])
    current = load_csv(FIXTURE_DIR / scenario["current"])

    first = analyze_datasets(baseline, current)
    second = analyze_datasets(baseline, current)

    assert first["findings"] == second["findings"]
    assert first["overall_status"] == second["overall_status"]
    assert evaluate_pipeline_gate(first) == evaluate_pipeline_gate(second)
