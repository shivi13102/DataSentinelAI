import json
from io import StringIO
from pathlib import Path
import threading
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "protection"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "REPORTS_DIR", tmp_path / "reports")

    def unavailable_reasoning(analysis_results):
        return {
            "status": "error",
            "model": "gemma4:e2b",
            "error": "Ollama is unavailable in this test.",
            "duration_seconds": 0.0,
        }

    monkeypatch.setattr(
        "src.graph.workflow.explain_findings",
        unavailable_reasoning,
    )
    return TestClient(api.app)


@pytest.mark.parametrize(
    ("scenario", "expected_decision"),
    [
        ("healthy", "ALLOW"),
        ("suspicious", "REVIEW_REQUIRED"),
        ("critical", "BLOCK"),
    ],
)
def test_upload_runs_real_analysis_gate_and_persists_report(
    client,
    scenario,
    expected_decision,
):
    baseline = (FIXTURE_DIR / f"{scenario}_baseline.csv").read_bytes()
    current = (FIXTURE_DIR / f"{scenario}_current.csv").read_bytes()

    response = client.post(
        "/api/analyze",
        files={
            "baseline_file": (f"{scenario}_baseline.csv", baseline, "text/csv"),
            "current_file": (f"{scenario}_current.csv", current, "text/csv"),
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["protection"]["decision"] == expected_decision
    assert report["protection"]["downstream_processing_allowed"] is (
        expected_decision == "ALLOW"
    )
    assert report["ai_reasoning"]["status"] == "error"
    if scenario == "healthy":
        assert report["analysis"]["findings"] == []
    else:
        assert report["analysis"]["findings"]

    report_path = api.REPORTS_DIR / f"analysis_{report['report_id']}.json"
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_report == report

    downloaded = client.get(f"/api/reports/{report['report_id']}")
    assert downloaded.status_code == 200
    assert downloaded.json() == report


@pytest.mark.parametrize(
    ("scenario", "expected_decision"),
    [
        ("healthy", "ALLOW"),
        ("missing_values", "REVIEW_REQUIRED"),
        ("schema_change", "BLOCK"),
    ],
)
def test_generic_csv_upload_uses_dynamic_schema_and_real_gate(
    client,
    scenario,
    expected_decision,
):
    baseline = pd.DataFrame(
        {
            "sensor_key": range(100),
            "measurement_reading": [index % 10 for index in range(100)],
            "category_token": [
                "north" if index % 2 else "south"
                for index in range(100)
            ],
        }
    )
    current = baseline.copy(deep=True)
    if scenario == "missing_values":
        current.loc[:19, "measurement_reading"] = float("nan")
    elif scenario == "schema_change":
        current = current.drop(columns=["measurement_reading"])

    def csv_bytes(frame):
        output = StringIO()
        frame.to_csv(output, index=False)
        return output.getvalue().encode("utf-8")

    response = client.post(
        "/api/analyze",
        files={
            "baseline_file": ("generic_reference.csv", csv_bytes(baseline), "text/csv"),
            "current_file": ("generic_daily.csv", csv_bytes(current), "text/csv"),
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["protection"]["decision"] == expected_decision
    assert result["protection"]["downstream_processing_allowed"] is (
        expected_decision == "ALLOW"
    )
    assert result["dataset_metadata"]["baseline"]["columns"] == 3
    if scenario == "healthy":
        assert result["analysis"]["findings"] == []
    else:
        assert result["analysis"]["findings"]
    assert client.get(f"/api/reports/{result['report_id']}").json() == result


def test_invalid_file_type_is_rejected(client):
    response = client.post(
        "/api/analyze",
        files={
            "baseline_file": ("baseline.txt", b"a,b\n1,2\n", "text/plain"),
            "current_file": ("current.csv", b"a,b\n1,2\n", "text/csv"),
        },
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Only CSV uploads are supported."


@pytest.mark.parametrize(
    ("content", "expected_detail"),
    [
        (b"", "baseline CSV file is empty"),
        (b"header,only\n", "valid, UTF-8 CSV"),
        (b'a,b\n"1,2\n', "valid, UTF-8 CSV"),
    ],
)
def test_invalid_csv_is_rejected_without_internal_details(
    client,
    content,
    expected_detail,
):
    response = client.post(
        "/api/analyze",
        files={
            "baseline_file": ("baseline.csv", content, "text/csv"),
            "current_file": ("current.csv", b"a,b\n1,2\n", "text/csv"),
        },
    )

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]
    assert "Traceback" not in response.text


def test_upload_size_limit_is_enforced(client, monkeypatch):
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 4)
    monkeypatch.setattr(api, "MAX_UPLOAD_SIZE_MB", 0)
    response = client.post(
        "/api/analyze",
        files={
            "baseline_file": ("baseline.csv", b"a,b\n1,2\n", "text/csv"),
            "current_file": ("current.csv", b"a,b\n1,2\n", "text/csv"),
        },
    )

    assert response.status_code == 413
    assert "upload limit" in response.json()["detail"]


def test_report_id_validation_and_missing_report(client):
    invalid = client.get("/api/reports/../requirements.txt")
    missing = client.get("/api/reports/not-a-real-report")

    assert invalid.status_code == 404 or invalid.status_code == 400
    assert missing.status_code == 404


def test_ai_health_endpoint_returns_actual_status_without_exposing_configuration(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "check_ai_health",
        lambda: {
            "provider": "ollama",
            "model": "gemma4:e2b",
            "status": "MODEL_NOT_INSTALLED",
            "ollama_reachable": True,
            "model_installed": False,
            "inference_tested": False,
            "response_time_ms": 8.5,
            "error": "Install the configured model manually.",
        },
    )

    response = client.get("/api/health/ai")

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "MODEL_NOT_INSTALLED"
    assert result["inference_tested"] is False
    assert "secret" not in response.text.lower()


def test_system_health_checks_analysis_engine_with_synthetic_data(
    client,
    monkeypatch,
):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["analysis_engine_status"] == "available"
    assert response.json()["analysis_engine_error"] is None

    def fail_health_analysis(**_kwargs):
        raise RuntimeError("private failure detail")

    monkeypatch.setattr(api, "run_deterministic_analysis", fail_health_analysis)
    degraded = client.get("/api/health")

    assert degraded.status_code == 200
    assert degraded.json()["status"] == "online"
    assert degraded.json()["analysis_engine_status"] == "unavailable"
    assert degraded.json()["analysis_engine_error"] == "RuntimeError"
    assert "private failure detail" not in degraded.text


def test_analysis_exception_returns_an_explicit_blocked_report(client, monkeypatch):
    def fail_analysis(*args, **kwargs):
        raise RuntimeError("sensitive exception details are not returned")

    monkeypatch.setattr("src.graph.workflow.analyze_datasets", fail_analysis)
    baseline = (FIXTURE_DIR / "healthy_baseline.csv").read_bytes()
    current = (FIXTURE_DIR / "healthy_current.csv").read_bytes()

    response = client.post(
        "/api/analyze",
        files={
            "baseline_file": ("baseline.csv", baseline, "text/csv"),
            "current_file": ("current.csv", current, "text/csv"),
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["workflow_status"] == "error"
    assert report["analysis"]["overall_status"] == "error"
    assert report["protection"]["decision"] == "BLOCK"
    assert report["protection"]["downstream_processing_allowed"] is False
    assert "sensitive exception details" not in response.text


def test_report_download_rejects_resolved_path_outside_reports_dir(
    client,
    tmp_path,
    monkeypatch,
):
    external_file = tmp_path / "external.json"
    external_file.write_text("{}", encoding="utf-8")
    original_resolve = Path.resolve

    def resolve_report_path(path, *args, **kwargs):
        if path.name == "analysis_outside.json":
            return external_file
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_report_path)
    response = client.get("/api/reports/outside")
    assert response.status_code == 400


def _wait_for_pipeline_run(client, run_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/pipeline-runs/{run_id}")
        assert response.status_code == 200
        state = response.json()
        if state["status"] in {
            "completed",
            "review_required",
            "blocked",
            "failed",
        }:
            return state
        time.sleep(0.01)
    pytest.fail("The monitored pipeline run did not reach a terminal state.")


@pytest.mark.parametrize(
    ("scenario", "expected_status", "expected_decision", "downstream"),
    [
        ("healthy", "completed", "ALLOW", True),
        ("suspicious", "review_required", "REVIEW_REQUIRED", False),
        ("critical", "blocked", "BLOCK", False),
    ],
)
def test_monitored_pipeline_runs_real_fixtures_and_enforces_protection(
    client,
    monkeypatch,
    scenario,
    expected_status,
    expected_decision,
    downstream,
):
    monkeypatch.setattr(
        "src.monitoring.execution.explain_findings",
        lambda analysis: {
            "status": "success",
            "model": "test-model",
            "explanation": {
                "incident_summary": "test",
                "root_cause_hypotheses": [],
                "business_impacts": [],
                "recommended_actions": [],
                "human_review_required": False,
            },
        },
    )

    created = client.post(
        "/api/pipeline-runs",
        data={"scenario": scenario},
    )
    assert created.status_code == 202
    initial = created.json()
    assert initial["run_id"]

    state = _wait_for_pipeline_run(client, initial["run_id"])
    assert state["status"] == expected_status
    assert state["protection_decision"] == expected_decision
    assert state["downstream_processing_allowed"] is downstream
    assert state["downstream_executed"] is downstream
    assert state["report_id"]
    assert state["latest_sequence"] > 0

    if expected_decision != "ALLOW":
        downstream_stage = next(
            stage
            for stage in state["stages"]
            if stage["stage_id"] == "downstream_execution"
        )
        assert downstream_stage["status"] == "blocked"
        assert downstream_stage["started_at"] is None

    history = client.get(
        f"/api/pipeline-runs/{initial['run_id']}/history"
    )
    assert history.status_code == 200
    events = history.json()["events"]
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )
    assert events[0]["event_type"] == "pipeline_started"
    assert any(event["event_type"] == "protection_decided" for event in events)
    assert events[-1]["event_type"] in {
        "pipeline_completed",
        "pipeline_blocked",
    }

    report_response = client.get(
        f"/api/pipeline-runs/{initial['run_id']}/report"
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["run_id"] == initial["run_id"]
    assert report["protection"]["decision"] == expected_decision
    assert report["monitoring"]["status"] == expected_status
    assert report["monitoring"]["downstream_executed"] is downstream
    assert report["monitoring"]["latest_sequence"] == state["latest_sequence"]

    stream = client.get(
        f"/api/pipeline-runs/{initial['run_id']}/events?after_sequence=0"
    )
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "event: pipeline" in stream.text
    assert f'"run_id":"{initial["run_id"]}"' in stream.text


def test_monitored_run_accepts_custom_csv_uploads(client, monkeypatch):
    monkeypatch.setattr(
        "src.monitoring.execution.explain_findings",
        lambda _analysis: {"status": "skipped"},
    )
    baseline = (FIXTURE_DIR / "healthy_baseline.csv").read_bytes()
    current = (FIXTURE_DIR / "healthy_current.csv").read_bytes()
    response = client.post(
        "/api/pipeline-runs",
        data={"scenario": "custom"},
        files={
            "baseline_file": ("C:\\private\\baseline.csv", baseline, "text/csv"),
            "current_file": ("current.csv", current, "text/csv"),
        },
    )

    assert response.status_code == 202
    state = _wait_for_pipeline_run(client, response.json()["run_id"])
    assert state["status"] == "completed"
    assert state["protection_decision"] == "ALLOW"
    report = client.get(
        f"/api/pipeline-runs/{state['run_id']}/report"
    ).json()
    assert report["dataset_metadata"]["baseline"]["filename"] == "baseline.csv"


def test_monitored_run_rejects_unknown_scenarios_and_run_ids(client):
    unknown_scenario = client.post(
        "/api/pipeline-runs",
        data={"scenario": "../../outside"},
    )
    invalid_run_id = client.get("/api/pipeline-runs/not-a-uuid")
    missing_run = client.get(
        "/api/pipeline-runs/00000000-0000-0000-0000-000000000000"
    )

    assert unknown_scenario.status_code == 422
    assert invalid_run_id.status_code == 400
    assert missing_run.status_code == 404


def test_monitored_pipeline_errors_are_safe_and_fail_closed(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        "src.monitoring.execution.explain_findings",
        lambda _analysis: {"status": "skipped"},
    )

    def fail_analysis(*_args, **_kwargs):
        raise RuntimeError("private internal details")

    monkeypatch.setattr(
        "src.monitoring.execution.analyze_datasets",
        fail_analysis,
    )
    created = client.post(
        "/api/pipeline-runs",
        data={"scenario": "healthy"},
    )
    state = _wait_for_pipeline_run(client, created.json()["run_id"])

    assert state["status"] == "failed"
    assert state["downstream_processing_allowed"] is False
    assert state["downstream_executed"] is False
    assert state["error_category"] == "RuntimeError"
    assert "private internal details" not in str(state)


def test_monitored_pipeline_rejects_invalid_protection_decisions(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        "src.monitoring.execution.explain_findings",
        lambda _analysis: {"status": "skipped"},
    )
    monkeypatch.setattr(
        "src.monitoring.execution.evaluate_pipeline_gate",
        lambda _analysis: {
            "decision": "ALLOW",
            "downstream_processing_allowed": False,
            "human_review_required": True,
            "finding_counts": {},
            "reasons": [],
        },
    )

    created = client.post(
        "/api/pipeline-runs",
        data={"scenario": "healthy"},
    )
    state = _wait_for_pipeline_run(client, created.json()["run_id"])
    downstream = next(
        stage
        for stage in state["stages"]
        if stage["stage_id"] == "downstream_execution"
    )

    assert state["status"] == "failed"
    assert state["protection_decision"] is None
    assert state["downstream_processing_allowed"] is False
    assert state["downstream_executed"] is False
    assert downstream["started_at"] is None


def test_concurrent_monitored_api_runs_keep_reports_and_events_isolated(
    client,
    monkeypatch,
):
    both_at_ai = threading.Barrier(2)

    def wait_for_peer(_analysis):
        both_at_ai.wait(timeout=5)
        return {"status": "skipped"}

    monkeypatch.setattr(
        "src.monitoring.execution.explain_findings",
        wait_for_peer,
    )
    created_runs = []
    for scenario in ("healthy", "critical"):
        response = client.post(
            "/api/pipeline-runs",
            data={"scenario": scenario},
        )
        assert response.status_code == 202
        created_runs.append(response.json()["run_id"])

    states = {
        run_id: _wait_for_pipeline_run(client, run_id)
        for run_id in created_runs
    }
    assert states[created_runs[0]]["protection_decision"] == "ALLOW"
    assert states[created_runs[1]]["protection_decision"] == "BLOCK"
    assert states[created_runs[0]]["findings"] == []
    assert states[created_runs[1]]["findings"]

    for run_id, state in states.items():
        report = client.get(
            f"/api/pipeline-runs/{run_id}/report"
        ).json()
        history = client.get(
            f"/api/pipeline-runs/{run_id}/history"
        ).json()["events"]
        assert report["run_id"] == run_id
        assert report["protection"]["decision"] == state["protection_decision"]
        assert {event["run_id"] for event in history} == {run_id}
