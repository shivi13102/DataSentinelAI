from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EventType = Literal[
    "pipeline_started",
    "stage_started",
    "stage_progress",
    "stage_completed",
    "stage_failed",
    "stage_skipped",
    "finding_detected",
    "investigation_updated",
    "protection_decided",
    "pipeline_completed",
    "pipeline_failed",
    "pipeline_blocked",
]
StageStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "blocked",
]
ProtectionDecision = Literal["ALLOW", "REVIEW_REQUIRED", "BLOCK"]
Scalar = str | int | float | bool | None
SafeMetric = Annotated[Scalar, Field()]


class SafeFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(min_length=1, max_length=80)
    detector_type: str = Field(min_length=1, max_length=80)
    severity: Literal["low", "medium", "high", "critical"]
    column: str | None = Field(default=None, max_length=128)
    description: str = Field(min_length=1, max_length=400)
    detection_method: str = Field(min_length=1, max_length=100)
    baseline_metrics: dict[str, SafeMetric] = Field(default_factory=dict)
    current_metrics: dict[str, SafeMetric] = Field(default_factory=dict)

    @field_validator("baseline_metrics", "current_metrics")
    @classmethod
    def limit_metrics(cls, value: dict[str, Scalar]) -> dict[str, Scalar]:
        if len(value) > 20:
            raise ValueError("A finding may contain at most 20 metrics.")
        if any(len(key) > 64 for key in value):
            raise ValueError("Metric names must not exceed 64 characters.")
        return value


class PipelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=80)
    run_id: str = Field(min_length=1, max_length=80)
    sequence: int = Field(ge=1)
    timestamp: datetime
    event_type: EventType
    stage_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    stage_name: str | None = Field(default=None, max_length=100)
    status: StageStatus | None = None
    progress: float | None = Field(default=None, ge=0, le=100)
    duration_ms: float | None = Field(default=None, ge=0)
    finding_count: int | None = Field(default=None, ge=0)
    finding: SafeFinding | None = None
    investigation: dict | None = None
    protection_decision: ProtectionDecision | None = None
    downstream_processing_allowed: bool | None = None
    finding_counts: dict[str, int] | None = None
    reasons: list[str] | None = None
    error_category: str | None = Field(default=None, max_length=100)
    message: str | None = Field(default=None, max_length=300)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("run_id must be a UUID.") from exc
        return value

    @field_validator("timestamp")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone.")
        if value.utcoffset() != timedelta(0):
            raise ValueError("timestamp must be UTC.")
        return value

    @field_validator("finding_counts")
    @classmethod
    def validate_finding_counts(
        cls,
        value: dict[str, int] | None,
    ) -> dict[str, int] | None:
        if value is None:
            return None
        allowed = {"critical", "high", "medium", "low", "total"}
        if set(value) - allowed:
            raise ValueError("finding_counts contains an unknown severity.")
        if any(isinstance(count, bool) or count < 0 for count in value.values()):
            raise ValueError("finding counts must be non-negative integers.")
        return value

    @field_validator("reasons")
    @classmethod
    def limit_reasons(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (
            len(value) > 20 or any(len(reason) > 300 for reason in value)
        ):
            raise ValueError("Protection reasons exceed event limits.")
        return value

    @model_validator(mode="after")
    def validate_event_payload(self) -> PipelineEvent:
        if self.event_type in {
            "stage_started",
            "stage_progress",
            "stage_completed",
            "stage_failed",
            "stage_skipped",
            "finding_detected",
        } and self.stage_id is None:
            raise ValueError(f"{self.event_type} requires stage_id.")

        if self.event_type == "finding_detected" and self.finding is None:
            raise ValueError("finding_detected requires finding metadata.")

        if self.event_type == "protection_decided":
            if self.protection_decision is None:
                raise ValueError("protection_decided requires a decision.")
            if self.downstream_processing_allowed is None:
                raise ValueError(
                    "protection_decided requires downstream permission."
                )

        if self.event_type == "stage_completed" and self.duration_ms is None:
            raise ValueError("stage_completed requires a measured duration.")

        if len(json.dumps(self.model_dump(mode="json"))) > 8_192:
            raise ValueError("Event payload exceeds 8 KiB.")
        return self
