import json
from pathlib import Path

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
            "model": "gemma3:1b",
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
