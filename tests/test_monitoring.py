from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.monitoring.events import PipelineEvent, SafeFinding
from src.monitoring.run_manager import RunManager
from src.monitoring.sdk import PipelineRun
from src.protection_gate import evaluate_pipeline_gate, enforce_downstream


def test_pipeline_events_are_serializable_and_sequence_is_monotonic():
    events = []
    run_id = str(uuid4())

    with PipelineRun(run_id, "test-pipeline", events.append) as run:
        with run.stage("analysis", "Analysis"):
            pass

    assert [event.sequence for event in events] == [1, 2, 3, 4]
    assert {event.run_id for event in events} == {run_id}
    assert events[2].duration_ms is not None
    assert events[-1].event_type == "pipeline_completed"
    assert events[0].model_dump(mode="json")["timestamp"].endswith("Z")


def test_sdk_publishes_only_explicit_measurable_progress():
    events = []
    manager = RunManager(worker_count=1)
    run_id = manager.create_run("test-pipeline")
    with PipelineRun(
        run_id,
        "test-pipeline",
        lambda event: (events.append(event), manager.publish(event)),
    ) as run:
        with run.stage("partition_load", "Partition Loading"):
            run.progress(
                "partition_load",
                "Partition Loading",
                40,
                "Processed 4 of 10 partitions.",
            )
            with pytest.raises(ValueError, match="backwards"):
                run.progress(
                    "partition_load",
                    "Partition Loading",
                    30,
                    "Invalid regression.",
                )

    progress_events = [
        event for event in events if event.event_type == "stage_progress"
    ]
    assert len(progress_events) == 1
    assert progress_events[0].progress == 40
    assert progress_events[0].message == "Processed 4 of 10 partitions."
    assert manager.get_snapshot(run_id)["stages"][-1]["progress"] == 40


@pytest.mark.parametrize(
    "values",
    [
        {"run_id": "not-a-uuid"},
        {"sequence": 0},
        {"event_type": "client_decision"},
        {"status": "invented"},
        {"event_type": "stage_completed", "stage_id": "analysis"},
    ],
)
def test_event_schema_rejects_invalid_values(values):
    base = {
        "event_id": "event-1",
        "run_id": str(uuid4()),
        "sequence": 1,
        "timestamp": datetime.now(timezone.utc),
        "event_type": "pipeline_started",
    }

    with pytest.raises(ValueError):
        PipelineEvent(**(base | values))


def test_event_schema_requires_utc_and_bounded_payload():
    base = {
        "event_id": "event-1",
        "run_id": str(uuid4()),
        "sequence": 1,
        "timestamp": datetime.fromisoformat("2026-10-30T12:00:00-05:00"),
        "event_type": "pipeline_started",
    }

    with pytest.raises(ValueError, match="UTC"):
        PipelineEvent(**base)

    with pytest.raises(ValueError, match="8 KiB"):
        long_metrics = {
            f"metric_{index}_{'k' * 50}": "v" * 64
            for index in range(20)
        }
        PipelineEvent(
            event_id="event-2",
            run_id=str(uuid4()),
            sequence=1,
            timestamp=datetime.now(timezone.utc),
            event_type="pipeline_started",
            message="x" * 300,
            reasons=["r" * 300] * 20,
            finding=SafeFinding(
                finding_id="finding",
                detector_type="schema_change",
                severity="medium",
                description="d" * 400,
                detection_method="test",
                baseline_metrics=long_metrics,
                current_metrics=long_metrics,
            ),
        )


def test_stage_exception_is_propagated_and_reported():
    events = []
    run_id = str(uuid4())

    with pytest.raises(RuntimeError, match="original failure"):
        with PipelineRun(run_id, "test-pipeline", events.append) as run:
            with run.stage("analysis", "Analysis"):
                raise RuntimeError("original failure")

    assert events[-2].event_type == "stage_failed"
    assert events[-2].error_category == "RuntimeError"
    assert events[-1].event_type == "pipeline_failed"
    assert events[-1].message == "Pipeline failed (RuntimeError)."


def test_nested_stage_contexts_are_rejected():
    events = []
    with PipelineRun(str(uuid4()), "test-pipeline", events.append) as run:
        with run.stage("outer", "Outer"):
            with pytest.raises(RuntimeError, match="Nested"):
                with run.stage("inner", "Inner"):
                    pass


def test_event_transport_failure_cannot_authorize_downstream():
    calls = []

    def broken_publisher(event):
        if event.event_type == "protection_decided":
            raise OSError("monitoring transport unavailable")

    run = PipelineRun(str(uuid4()), "test-pipeline", broken_publisher)
    with pytest.raises(OSError):
        with run:
            protection = evaluate_pipeline_gate(
                {"overall_status": "healthy", "findings": []}
            )
            with run.stage("protection_gate", "Protection Gate"):
                run.publish_protection(protection)
            enforce_downstream(
                protection,
                lambda: calls.append("executed"),
            )

    assert calls == []


def test_run_manager_keeps_concurrent_runs_isolated():
    manager = RunManager(worker_count=2, max_retained_runs=10)
    run_ids = [manager.create_run("test-pipeline") for _ in range(2)]

    def execute(run_id):
        def target(run):
            with run:
                with run.stage("analysis", "Analysis"):
                    run.publish_findings(
                        "analysis",
                        "Analysis",
                        [
                            {
                                "type": f"finding_{run_id[:6]}",
                                "severity": "medium",
                                "column": "feature",
                                "description": "Measured test finding.",
                                "detection_method": "test",
                                "baseline_value": {"sample_count": 20},
                                "current_value": {"sample_count": 20},
                            }
                        ],
                    )

        manager.submit(run_id, target)

    for run_id in run_ids:
        execute(run_id)

    deadline = time.monotonic() + 5
    states = [manager.get_snapshot(run_id) for run_id in run_ids]
    while any(state["status"] not in {"completed", "failed"} for state in states):
        if time.monotonic() >= deadline:
            pytest.fail("Concurrent monitored runs did not finish in time.")
        time.sleep(0.01)
        states = [manager.get_snapshot(run_id) for run_id in run_ids]

    assert states[0]["run_id"] != states[1]["run_id"]
    assert states[0]["findings"][0]["detector_type"] != (
        states[1]["findings"][0]["detector_type"]
    )
    assert all(state["latest_sequence"] == 5 for state in states)


def test_run_manager_bounds_retained_event_history():
    manager = RunManager(
        worker_count=1,
        max_retained_runs=2,
        max_events_per_run=2,
    )
    run_id = manager.create_run("test-pipeline")
    events = []
    run = PipelineRun(run_id, "test-pipeline", lambda event: (
        events.append(event),
        manager.publish(event),
    ))
    with run:
        with run.stage("analysis", "Analysis"):
            pass

    retained, truncated = manager.list_events(run_id, after_sequence=0)
    assert len(retained) == 2
    assert truncated is True
    assert manager.get_snapshot(run_id)["history_truncated"] is True


def test_finding_events_exclude_category_values_and_row_contents():
    events = []
    with PipelineRun(str(uuid4()), "test-pipeline", events.append) as run:
        with run.stage("categorical_drift", "Categorical Drift"):
            run.publish_findings(
                "categorical_drift",
                "Categorical Drift",
                [
                    {
                        "type": "categorical_drift",
                        "severity": "medium",
                        "column": "segment",
                        "description": "Distribution changed in segment.",
                        "detection_method": "chi_square",
                        "baseline_value": {
                            "counts": {"private-label": 99},
                            "sample_count": 100,
                        },
                        "current_value": {
                            "counts": {"patient-alice": 99},
                            "sample_count": 100,
                        },
                    }
                ],
            )

    finding_event = next(
        event for event in events if event.event_type == "finding_detected"
    )
    serialized = finding_event.model_dump_json()
    assert "private-label" not in serialized
    assert "patient-alice" not in serialized
    assert finding_event.finding.current_metrics == {"sample_count": 100}
