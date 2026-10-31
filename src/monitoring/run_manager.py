from __future__ import annotations

import logging
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from src.monitoring.events import PipelineEvent
from src.monitoring.sdk import PipelineRun


logger = logging.getLogger(__name__)

PIPELINE_STAGES = (
    ("dataset_loading", "Dataset Loading"),
    ("input_validation", "Input Validation"),
    ("schema_analysis", "Schema Change Detection"),
    ("missing_value_analysis", "Missing Value Detection"),
    ("duplicate_analysis", "Duplicate Detection"),
    ("numerical_drift_analysis", "Numerical Drift Detection"),
    ("categorical_drift_analysis", "Categorical Drift Detection"),
    ("findings_aggregation", "Findings Aggregation"),
    ("agentic_investigation", "Agentic Investigation"),
    ("protection_gate", "Deterministic Protection Gate"),
    ("ai_investigation", "AI Investigation"),
    ("downstream_execution", "Simulated Downstream Processing"),
    ("report_generation", "Report Generation"),
)
TERMINAL_STATUSES = {"completed", "review_required", "blocked", "failed"}


class RunNotFoundError(LookupError):
    pass


class RunCapacityError(RuntimeError):
    pass


class RunManager:
    """Single-process, bounded run and event registry."""

    def __init__(
        self,
        *,
        worker_count: int = 2,
        max_active_runs: int = 4,
        max_retained_runs: int = 50,
        max_events_per_run: int = 100,
        max_subscribers_per_run: int = 20,
        max_findings_per_run: int = 100,
    ) -> None:
        self._lock = threading.RLock()
        self._runs: dict[str, dict] = {}
        self._conditions: dict[str, threading.Condition] = {}
        self._futures: dict[str, Future] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="datasentinel-run",
        )
        self._max_active_runs = max_active_runs
        self._max_retained_runs = max_retained_runs
        self._max_events_per_run = max_events_per_run
        self._max_subscribers_per_run = max_subscribers_per_run
        self._max_findings_per_run = max_findings_per_run

    def create_run(self, pipeline_name: str) -> str:
        with self._lock:
            self._prune_completed_runs()
            active = sum(
                run["status"] in {"queued", "running"}
                for run in self._runs.values()
            )
            if active >= self._max_active_runs:
                raise RunCapacityError("The monitored-run capacity is full.")
            if len(self._runs) >= self._max_retained_runs:
                raise RunCapacityError(
                    "The retained-run capacity is full; retry later."
                )

            run_id = str(uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            self._runs[run_id] = {
                "run_id": run_id,
                "pipeline_name": pipeline_name,
                "status": "queued",
                "created_at": created_at,
                "updated_at": created_at,
                "current_stage": None,
                "stages": [
                    {
                        "stage_id": stage_id,
                        "name": name,
                        "status": "pending",
                        "started_at": None,
                        "completed_at": None,
                        "duration_ms": None,
                        "progress": None,
                        "findings_count": 0,
                        "findings": [],
                        "error_category": None,
                        "message": None,
                    }
                    for stage_id, name in PIPELINE_STAGES
                ],
                "findings": [],
                "findings_count": 0,
                "investigation": {"status": "pending", "tool_calls": []},
                "protection_decision": None,
                "downstream_processing_allowed": False,
                "downstream_executed": False,
                "protection_reasons": [],
                "report_id": None,
                "latest_sequence": 0,
                "history_truncated": False,
                "error_category": None,
                "events": deque(),
                "subscriber_count": 0,
                "event_count": 0,
            }
            self._conditions[run_id] = threading.Condition(self._lock)
            return run_id

    def submit(
        self,
        run_id: str,
        target: Callable[[PipelineRun], None],
    ) -> None:
        with self._lock:
            record = self._get_record(run_id)
            if record["status"] != "queued":
                raise RunCapacityError("This run has already been submitted.")
            future = self._executor.submit(self._execute, run_id, target)
            self._futures[run_id] = future

    def discard_queued_run(self, run_id: str) -> bool:
        """Remove an unsubmitted run when its durable setup cannot complete."""

        with self._lock:
            record = self._runs.get(run_id)
            if (
                record is None
                or record["status"] != "queued"
                or run_id in self._futures
            ):
                return False
            self._runs.pop(run_id)
            self._conditions.pop(run_id, None)
            return True

    def _execute(
        self,
        run_id: str,
        target: Callable[[PipelineRun], None],
    ) -> None:
        run = PipelineRun(
            run_id=run_id,
            pipeline_name=self.get_snapshot(run_id)["pipeline_name"],
            publisher=self.publish,
        )
        try:
            target(run)
        except Exception as exc:
            logger.exception(
                "Monitored run %s failed (%s).",
                run_id,
                type(exc).__name__,
            )
            if not run.is_terminal:
                try:
                    run.fail(type(exc).__name__)
                except Exception:
                    logger.exception(
                        "Could not publish terminal failure for run %s.",
                        run_id,
                    )

    def publish(self, event: PipelineEvent) -> None:
        with self._lock:
            record = self._get_record(event.run_id)
            if event.sequence != record["latest_sequence"] + 1:
                raise ValueError("Run event sequence is not monotonic.")
            record["latest_sequence"] = event.sequence
            record["event_count"] += 1
            record["updated_at"] = event.timestamp.isoformat()
            record["events"].append(event)
            if len(record["events"]) > self._max_events_per_run:
                record["events"].popleft()
                record["history_truncated"] = True

            self._apply_event(record, event)
            self._conditions[event.run_id].notify_all()

    def _apply_event(self, record: dict, event: PipelineEvent) -> None:
        event_type = event.event_type
        if event_type == "pipeline_started":
            record["status"] = "running"

        if event.stage_id is not None:
            stage = next(
                (
                    item
                    for item in record["stages"]
                    if item["stage_id"] == event.stage_id
                ),
                None,
            )
            if stage is None:
                stage = {
                    "stage_id": event.stage_id,
                    "name": event.stage_name or event.stage_id,
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": None,
                    "progress": None,
                    "findings_count": 0,
                    "findings": [],
                    "error_category": None,
                    "message": None,
                }
                record["stages"].append(stage)

            if event_type == "stage_started":
                stage.update(
                    status="running",
                    started_at=event.timestamp.isoformat(),
                    message=event.message,
                )
                record["current_stage"] = event.stage_id
            elif event_type == "stage_completed":
                stage.update(
                    status="completed",
                    completed_at=event.timestamp.isoformat(),
                    duration_ms=event.duration_ms,
                    progress=(
                        event.progress
                        if event.progress is not None
                        else stage["progress"]
                    ),
                    message=event.message,
                )
                if record["current_stage"] == event.stage_id:
                    record["current_stage"] = None
                if event.stage_id == "downstream_execution":
                    record["downstream_executed"] = True
            elif event_type == "stage_progress":
                stage.update(
                    status="running",
                    progress=event.progress,
                    message=event.message,
                )
            elif event_type == "stage_failed":
                stage.update(
                    status="failed",
                    completed_at=event.timestamp.isoformat(),
                    duration_ms=event.duration_ms,
                    error_category=event.error_category,
                    message=event.message,
                )
                if record["current_stage"] == event.stage_id:
                    record["current_stage"] = None
            elif event_type == "stage_skipped":
                stage.update(
                    status=event.status or "skipped",
                    completed_at=event.timestamp.isoformat(),
                    message=event.message,
                )
            elif event_type == "finding_detected" and event.finding is not None:
                finding = event.finding.model_dump(mode="json")
                stage["findings_count"] += event.finding_count or 1
                if len(stage["findings"]) < self._max_findings_per_run:
                    stage["findings"].append(finding)
                record["findings_count"] += event.finding_count or 1
                if len(record["findings"]) < self._max_findings_per_run:
                    record["findings"].append(finding)

        if event_type == "protection_decided":
            record["protection_decision"] = event.protection_decision
            record["downstream_processing_allowed"] = (
                event.downstream_processing_allowed is True
            )
            record["protection_reasons"] = event.reasons or []

        if event_type == "investigation_updated":
            record["investigation"] = event.investigation

        if event_type == "pipeline_completed":
            record["status"] = "completed"
            record["current_stage"] = None
        elif event_type == "pipeline_blocked":
            record["status"] = (
                "review_required"
                if event.protection_decision == "REVIEW_REQUIRED"
                else "blocked"
            )
            record["current_stage"] = None
            record["protection_decision"] = event.protection_decision
            record["downstream_processing_allowed"] = False
        elif event_type == "pipeline_failed":
            record["status"] = "failed"
            record["current_stage"] = None
            record["error_category"] = event.error_category
            for stage in record["stages"]:
                if stage["status"] == "pending":
                    stage["status"] = "skipped"
                    stage["message"] = "Not run because the pipeline failed."
                elif stage["status"] == "running":
                    stage.update(
                        status="failed",
                        completed_at=event.timestamp.isoformat(),
                        error_category=event.error_category,
                        message="Stage ended when the pipeline failed.",
                    )

    def get_snapshot(self, run_id: str) -> dict:
        with self._lock:
            return self._snapshot(self._get_record(run_id))

    def _snapshot(self, record: dict) -> dict:
        return {
            key: deepcopy(value)
            for key, value in record.items()
            if key not in {"events", "subscriber_count", "event_count"}
        }

    def list_events(
        self,
        run_id: str,
        after_sequence: int = 0,
    ) -> tuple[list[PipelineEvent], bool]:
        with self._lock:
            record = self._get_record(run_id)
            events: deque[PipelineEvent] = record["events"]
            is_truncated = bool(
                events
                and after_sequence < events[0].sequence - 1
            )
            return (
                [
                    event
                    for event in events
                    if event.sequence > after_sequence
                ],
                is_truncated,
            )

    def wait_for_events(
        self,
        run_id: str,
        after_sequence: int,
        timeout: float,
    ) -> tuple[list[PipelineEvent], bool, dict]:
        with self._lock:
            record = self._get_record(run_id)
            condition = self._conditions[run_id]
            events: deque[PipelineEvent] = record["events"]
            available = any(
                event.sequence > after_sequence for event in events
            )
            if not available and record["status"] not in TERMINAL_STATUSES:
                condition.wait(timeout=timeout)
            record = self._get_record(run_id)
            events = record["events"]
            is_truncated = bool(
                events and after_sequence < events[0].sequence - 1
            )
            return (
                [
                    event
                    for event in events
                    if event.sequence > after_sequence
                ],
                is_truncated,
                self._snapshot(record),
            )

    def begin_subscription(self, run_id: str) -> None:
        with self._lock:
            record = self._get_record(run_id)
            if record["subscriber_count"] >= self._max_subscribers_per_run:
                raise RunCapacityError("Too many event-stream subscribers.")
            record["subscriber_count"] += 1

    def end_subscription(self, run_id: str) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is not None:
                record["subscriber_count"] = max(
                    0, record["subscriber_count"] - 1
                )

    def set_report_id(self, run_id: str, report_id: str) -> None:
        with self._lock:
            record = self._get_record(run_id)
            record["report_id"] = report_id
            record["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._conditions[run_id].notify_all()

    def _get_record(self, run_id: str) -> dict:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise RunNotFoundError(run_id) from exc

    def _prune_completed_runs(self) -> None:
        removable = sorted(
            (
                record
                for record in self._runs.values()
                if record["status"] in TERMINAL_STATUSES
                and record["subscriber_count"] == 0
            ),
            key=lambda record: record["created_at"],
        )
        while len(self._runs) >= self._max_retained_runs and removable:
            record = removable.pop(0)
            run_id = record["run_id"]
            self._runs.pop(run_id, None)
            self._conditions.pop(run_id, None)
            self._futures.pop(run_id, None)
