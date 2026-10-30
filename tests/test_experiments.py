from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
from src.analysis_engine import analyze_datasets
from src.experiments.lab import (
    SCENARIOS,
    correct_experiment,
    dataset_fingerprint,
    inject_scenario,
    verify_recovery,
)
from src.experiments.store import ExperimentStore
from src.utils.data_loader import load_csv


SAMPLE_DATASET = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "raw"
    / "baseline.csv"
)


@pytest.mark.parametrize("scenario_id", list(SCENARIOS))
def test_scenario_runs_real_detectors_and_correction_restores_source(
    scenario_id: str,
) -> None:
    source = load_csv(SAMPLE_DATASET)
    injected, operations, targets = inject_scenario(source, scenario_id)

    measured = analyze_datasets(source, injected)
    measured_targets = {
        (finding["type"], finding.get("column"))
        for finding in measured["findings"]
    }
    assert all(
        (target["finding_type"], target.get("column")) in measured_targets
        for target in targets
    )

    corrected, actions = correct_experiment(
        source,
        injected,
        operations,
    )
    recovered = analyze_datasets(source, corrected)

    assert actions
    assert dataset_fingerprint(corrected) == dataset_fingerprint(source)
    assert recovered["findings"] == []


def test_scenario_rejects_missing_required_column() -> None:
    import pandas as pd

    source = pd.DataFrame({"only_id": range(10)})
    with pytest.raises(ValueError, match="numeric column"):
        inject_scenario(source, "numeric_drift")


@pytest.mark.parametrize(
    ("before", "after", "analysis_failed", "expected_status", "unrelated"),
    [
        ([], [], False, "injection_not_detected", 0),
        (
            [{"detector_type": "missing_value_anomaly", "column": "age"}],
            [{"detector_type": "missing_value_anomaly", "column": "age"}],
            False,
            "unresolved",
            0,
        ),
        (
            [{"detector_type": "missing_value_anomaly", "column": "age"}],
            [{"detector_type": "duplicate_anomaly", "column": None}],
            False,
            "resolved",
            1,
        ),
        ([], [], True, "analysis_failed", 0),
    ],
)
def test_recovery_verification_checks_target_evidence(
    before: list[dict],
    after: list[dict],
    analysis_failed: bool,
    expected_status: str,
    unrelated: int,
) -> None:
    result = verify_recovery(
        [{"finding_type": "missing_value_anomaly", "column": "age"}],
        before,
        after,
        analysis_failed=analysis_failed,
    )
    assert result["status"] == expected_status
    assert result["unrelated_findings_remaining"] == unrelated


def test_experiment_store_keeps_metadata_separate_from_dataset_values(
    tmp_path: Path,
) -> None:
    source = b"customer,value\nprivate-marker,1\n"
    injected = b"customer,value\nprivate-marker,\n"
    store = ExperimentStore(tmp_path)
    record = {
        "experiment_id": "e62fae5c-b8d8-4fb9-80b8-8d7137206179",
        "scenario_id": "missing_values",
        "status": "running",
        "initial_run_id": "7ebf2c92-682c-43f3-a675-27e8dd13cc49",
        "dataset_version_before": "source-fingerprint",
        "dataset_version_after_injection": "injected-fingerprint",
    }

    store.create(record, source, injected)
    stored = store.get(record["experiment_id"])

    assert stored == record
    assert b"private-marker" in store.read_source_csv(record["experiment_id"])
    database = (tmp_path / "experiments.sqlite3").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    assert "private-marker" not in database


@pytest.fixture
def experiment_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(api, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(
        "src.monitoring.execution.explain_findings",
        lambda analysis: {
            "status": "error",
            "error": "Ollama is unavailable in this test.",
        },
    )
    return TestClient(api.app)


def _wait_for_experiment(
    client: TestClient,
    experiment_id: str,
    expected_status: str,
) -> dict:
    deadline = time.monotonic() + 5
    latest = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/experiments/{experiment_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] == expected_status:
            return latest
        time.sleep(0.02)
    pytest.fail(
        f"Experiment did not reach {expected_status}; latest status was "
        f"{latest.get('status')!r}."
    )


def test_experiment_api_executes_and_verifies_recovery(
    experiment_client: TestClient,
) -> None:
    response = experiment_client.post(
        "/api/experiments",
        data={"scenario_id": "missing_values"},
    )
    assert response.status_code == 202
    started = response.json()
    experiment_id = started["experiment_id"]

    before = _wait_for_experiment(
        experiment_client,
        experiment_id,
        "experiment_completed",
    )
    assert before["run"]["protection_decision"] in {
        "REVIEW_REQUIRED",
        "BLOCK",
    }
    assert before["findings_before"]
    assert before["ai_reasoning"]["status"] == "error"

    recovery_response = experiment_client.post(
        f"/api/experiments/{experiment_id}/correct"
    )
    assert recovery_response.status_code == 202
    assert recovery_response.json()["status"] in {
        "recovery_running",
        "recovery_completed",
    }

    after = _wait_for_experiment(
        experiment_client,
        experiment_id,
        "recovery_completed",
    )
    assert after["recovery_verification"]["status"] == "resolved"
    assert after["findings_after"] == []
    assert after["dataset_version_before"] == (
        after["dataset_version_after_correction"]
    )

    repeated = experiment_client.post(
        f"/api/experiments/{experiment_id}/correct"
    )
    assert repeated.status_code == 202
    assert repeated.json()["recovery_run_id"] == after["recovery_run_id"]


def test_unknown_experiment_scenario_is_rejected(
    experiment_client: TestClient,
) -> None:
    response = experiment_client.post(
        "/api/experiments",
        data={"scenario_id": "invented"},
    )
    assert response.status_code == 422
