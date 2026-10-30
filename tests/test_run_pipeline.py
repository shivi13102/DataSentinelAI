import json
from pathlib import Path

import pytest

from scripts.run_pipeline import run_pipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "protection"


@pytest.mark.parametrize(
    ("scenario", "expected_decision"),
    [
        ("healthy", "ALLOW"),
        ("suspicious", "REVIEW_REQUIRED"),
        ("critical", "BLOCK"),
    ],
)
def test_pipeline_writes_decision_and_report_for_the_current_run(
    tmp_path,
    scenario,
    expected_decision,
):
    artifact_dir = tmp_path / "jenkins" / scenario
    report = run_pipeline(
        FIXTURE_DIR / f"{scenario}_baseline.csv",
        FIXTURE_DIR / f"{scenario}_current.csv",
        artifact_dir=artifact_dir,
        run_id=f"test-{scenario}",
    )

    decision_file = artifact_dir / "jenkins_decision.txt"
    report_files = list(artifact_dir.glob("jenkins_analysis_*.json"))

    assert decision_file.read_text(encoding="utf-8").strip() == expected_decision
    assert len(report_files) == 1
    assert json.loads(report_files[0].read_text(encoding="utf-8")) == report
    assert report["run_id"] == f"test-{scenario}"
    assert report["protection"]["decision"] == expected_decision


def test_pipeline_artifacts_are_isolated_by_run_id(tmp_path):
    first_dir = tmp_path / "run-1"
    second_dir = tmp_path / "run-2"

    run_pipeline(
        FIXTURE_DIR / "healthy_baseline.csv",
        FIXTURE_DIR / "healthy_current.csv",
        artifact_dir=first_dir,
        run_id="run-1",
    )
    run_pipeline(
        FIXTURE_DIR / "critical_baseline.csv",
        FIXTURE_DIR / "critical_current.csv",
        artifact_dir=second_dir,
        run_id="run-2",
    )

    assert (first_dir / "jenkins_decision.txt").read_text(
        encoding="utf-8"
    ).strip() == "ALLOW"
    assert (second_dir / "jenkins_decision.txt").read_text(
        encoding="utf-8"
    ).strip() == "BLOCK"


def test_pipeline_rejects_unsafe_run_id(tmp_path):
    with pytest.raises(ValueError, match="run_id"):
        run_pipeline(
            FIXTURE_DIR / "healthy_baseline.csv",
            FIXTURE_DIR / "healthy_current.csv",
            artifact_dir=tmp_path,
            run_id="../outside",
        )


def test_failed_run_removes_any_previous_decision_artifact(tmp_path):
    artifact_dir = tmp_path / "run"
    artifact_dir.mkdir()
    decision_file = artifact_dir / "jenkins_decision.txt"
    decision_file.write_text("ALLOW\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        run_pipeline(
            tmp_path / "missing.csv",
            FIXTURE_DIR / "healthy_current.csv",
            artifact_dir=artifact_dir,
            run_id="retry",
        )

    assert not decision_file.exists()
