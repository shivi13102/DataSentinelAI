from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.monitoring.events import PipelineEvent, SafeFinding


EventPublisher = Callable[[PipelineEvent], None]
logger = logging.getLogger(__name__)

_METRIC_KEYS = {
    "missing_count",
    "missing_percentage",
    "duplicate_count",
    "duplicate_percentage",
    "mean",
    "std",
    "min",
    "max",
    "sample_count",
    "relative_mean_change",
    "ks_statistic",
    "ks_p_value",
    "alpha",
    "total_variation_distance",
    "chi2_statistic",
    "p_value",
    "change_percentage_points",
}


def _safe_metrics(value: Any) -> dict[str, str | int | float | bool | None]:
    if isinstance(value, dict):
        return {
            key: item
            for key, item in value.items()
            if key in _METRIC_KEYS
            and isinstance(item, (str, int, float, bool, type(None)))
        }
    if isinstance(value, str) and len(value) <= 64:
        return {"value": value}
    return {}


class PipelineRun:
    """Create ordered execution events without coupling callers to SSE."""

    def __init__(
        self,
        run_id: str,
        pipeline_name: str,
        publisher: EventPublisher,
    ) -> None:
        if not pipeline_name or len(pipeline_name) > 100:
            raise ValueError("pipeline_name must contain 1 to 100 characters.")
        self.run_id = run_id
        self.pipeline_name = pipeline_name
        self._publisher = publisher
        self._sequence = 0
        self._terminal = False
        self._active_stage_id: str | None = None
        self._seen_stages: set[str] = set()
        self._progress_by_stage: dict[str, float] = {}

    def __enter__(self) -> PipelineRun:
        self._emit(
            "pipeline_started",
            status="running",
            message=f"{self.pipeline_name} started.",
        )
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if exc is not None:
            logger.exception(
                "Monitored pipeline failed (%s).",
                exc_type.__name__ if exc_type else "Exception",
                exc_info=(exc_type, exc, traceback),
            )
            if not self._terminal:
                try:
                    self.fail(exc_type.__name__ if exc_type else "Exception")
                except Exception:
                    logger.exception(
                        "Could not publish terminal failure for run %s.",
                        self.run_id,
                    )
            return False

        if not self._terminal:
            self._emit(
                "pipeline_completed",
                status="completed",
                message="All permitted pipeline stages completed.",
            )
            self._terminal = True
        return False

    def stage(self, stage_id: str, stage_name: str) -> StageContext:
        return StageContext(self, stage_id, stage_name)

    def publish_findings(
        self,
        stage_id: str,
        stage_name: str,
        findings: Iterable[dict[str, Any]],
    ) -> None:
        if self._active_stage_id != stage_id:
            raise RuntimeError(
                "Findings must be published inside their active detector stage."
            )
        for index, finding in enumerate(findings):
            baseline = finding.get("baseline_value")
            current = finding.get("current_value")
            safe_finding = SafeFinding(
                finding_id=f"{stage_id}-{index + 1}-{uuid4().hex[:12]}",
                detector_type=str(finding.get("type", "unknown"))[:80],
                severity=finding.get("severity", "low"),
                column=(
                    str(finding["column"])[:128]
                    if finding.get("column") is not None
                    else None
                ),
                description=str(
                    finding.get("description", "Detector finding.")
                )[:400],
                detection_method=str(
                    finding.get("detection_method", "unknown")
                )[:100],
                baseline_metrics=_safe_metrics(baseline),
                current_metrics=_safe_metrics(current),
            )
            self._emit(
                "finding_detected",
                stage_id=stage_id,
                stage_name=stage_name,
                status="running",
                finding=safe_finding,
                finding_count=1,
                message="A detector reported a finding.",
            )

    def progress(
        self,
        stage_id: str,
        stage_name: str,
        progress: float,
        message: str,
    ) -> None:
        if self._active_stage_id != stage_id:
            raise RuntimeError("Progress requires the active stage context.")
        if not math.isfinite(progress) or not 0 <= progress <= 100:
            raise ValueError("Progress must be a finite value from 0 to 100.")
        if progress < self._progress_by_stage.get(stage_id, 0):
            raise ValueError("Stage progress cannot move backwards.")
        self._emit(
            "stage_progress",
            stage_id=stage_id,
            stage_name=stage_name,
            status="running",
            progress=progress,
            message=message,
        )
        self._progress_by_stage[stage_id] = progress

    def publish_protection(self, protection: dict[str, Any]) -> None:
        if self._active_stage_id != "protection_gate":
            raise RuntimeError(
                "Protection decisions must be published inside the gate stage."
            )
        decision = protection.get("decision")
        if decision not in {"ALLOW", "REVIEW_REQUIRED", "BLOCK"}:
            raise ValueError("Protection decision is missing or invalid.")

        downstream_allowed = protection.get("downstream_processing_allowed")
        expected_allowed = decision == "ALLOW"
        if downstream_allowed is not expected_allowed:
            raise ValueError("Protection decision contradicts its permission.")

        self._emit(
            "protection_decided",
            stage_id="protection_gate",
            stage_name="Deterministic Protection Gate",
            status="completed",
            protection_decision=decision,
            downstream_processing_allowed=expected_allowed,
            finding_counts=protection.get("finding_counts"),
            reasons=[
                str(reason)[:300]
                for reason in protection.get("reasons", [])[:20]
            ],
            message=f"Protection gate returned {decision}.",
        )

    def skip_downstream(self, decision: str) -> None:
        if decision not in {"REVIEW_REQUIRED", "BLOCK"}:
            raise ValueError("Only a restrictive decision can block downstream.")
        self._emit(
            "stage_skipped",
            stage_id="downstream_execution",
            stage_name="Simulated Downstream Processing",
            status="blocked",
            message=f"Downstream execution prohibited by {decision}.",
        )

    def mark_blocked(self, decision: str) -> None:
        if decision not in {"REVIEW_REQUIRED", "BLOCK"}:
            raise ValueError("Only a restrictive decision can block a run.")
        self._emit(
            "pipeline_blocked",
            status="blocked",
            protection_decision=decision,
            message=f"Pipeline stopped by {decision}.",
        )
        self._terminal = True

    def fail(self, error_category: str) -> None:
        if self._terminal:
            return
        self._emit(
            "pipeline_failed",
            status="failed",
            error_category=error_category[:100],
            message=f"Pipeline failed ({error_category[:80]}).",
        )
        self._terminal = True

    @property
    def is_terminal(self) -> bool:
        return self._terminal

    @property
    def sequence(self) -> int:
        return self._sequence

    def _emit(self, event_type: str, **fields: Any) -> PipelineEvent:
        self._sequence += 1
        event = PipelineEvent(
            event_id=uuid4().hex,
            run_id=self.run_id,
            sequence=self._sequence,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            **fields,
        )
        self._publisher(event)
        return event

    def _begin_stage(self, stage_id: str, stage_name: str) -> None:
        if self._active_stage_id is not None:
            raise RuntimeError("Nested pipeline stages are not supported.")
        if stage_id in self._seen_stages:
            raise RuntimeError("A pipeline stage cannot be started twice.")
        self._emit(
            "stage_started",
            stage_id=stage_id,
            stage_name=stage_name,
            status="running",
            message=f"{stage_name} started.",
        )
        self._active_stage_id = stage_id
        self._seen_stages.add(stage_id)

    def _finish_stage(
        self,
        event_type: str,
        *,
        stage_id: str,
        stage_name: str,
        duration_ms: float,
        error_category: str | None = None,
    ) -> None:
        try:
            self._emit(
                event_type,
                stage_id=stage_id,
                stage_name=stage_name,
                status="completed" if event_type == "stage_completed" else "failed",
                duration_ms=duration_ms,
                error_category=error_category,
                message=(
                    f"{stage_name} completed."
                    if event_type == "stage_completed"
                    else f"{stage_name} failed ({error_category})."
                ),
            )
        finally:
            self._active_stage_id = None


class StageContext:
    def __init__(
        self,
        run: PipelineRun,
        stage_id: str,
        stage_name: str,
    ) -> None:
        self._run = run
        self._stage_id = stage_id
        self._stage_name = stage_name
        self._started_at = 0.0

    def __enter__(self) -> StageContext:
        self._started_at = time.perf_counter()
        self._run._begin_stage(self._stage_id, self._stage_name)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        duration_ms = (time.perf_counter() - self._started_at) * 1000
        if exc is None:
            self._run._finish_stage(
                "stage_completed",
                stage_id=self._stage_id,
                stage_name=self._stage_name,
                duration_ms=duration_ms,
            )
            return False

        category = exc_type.__name__ if exc_type else "Exception"
        logger.error(
            "Pipeline stage %s failed (%s).",
            self._stage_id,
            category,
        )
        try:
            self._run._finish_stage(
                "stage_failed",
                stage_id=self._stage_id,
                stage_name=self._stage_name,
                duration_ms=duration_ms,
                error_category=category[:100],
            )
        except Exception:
            logger.exception(
                "Could not publish failure event for stage %s.",
                self._stage_id,
            )
        return False
