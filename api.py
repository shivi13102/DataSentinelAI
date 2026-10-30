from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from src.graph.workflow import data_sentinel_workflow
from src.monitoring.execution import execute_monitored_pipeline
from src.monitoring.run_manager import (
    RunCapacityError,
    RunManager,
    RunNotFoundError,
    TERMINAL_STATUSES,
)
from src.experiments.lab import (
    SCENARIOS as EXPERIMENT_SCENARIOS,
    ScenarioValidationError,
    canonical_csv_bytes,
    correct_experiment,
    dataset_fingerprint,
    dataframe_from_bytes,
    inject_scenario,
    verify_recovery,
)
from src.experiments.store import ExperimentStore
from src.utils.data_loader import load_csv


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

AI_MODEL = "gemma3:1b"
MAX_UPLOAD_SIZE_MB = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
PROTECTION_FIXTURE_DIR = (
    PROJECT_ROOT / "tests" / "fixtures" / "protection"
)
PROTECTION_SCENARIOS = {
    "healthy",
    "suspicious",
    "critical",
    "duplicate",
    "numerical_drift",
    "categorical_drift",
    "multiple",
}
run_manager = RunManager()
_experiment_recovery_lock = threading.Lock()

app = FastAPI(
    title="DataSentinel AI API",
    description=(
        "API for data-quality analysis, AI-assisted investigation "
        "and pipeline safety decisions."
    ),
    version="1.0.0",
)

# Vite's development server runs on localhost:5173.
# Restrict browser access to the local development frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)


def json_safe(value: Any) -> Any:
    """Convert common Python and Pandas values into JSON-safe values."""

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except (ValueError, TypeError):
            pass

    if hasattr(value, "tolist"):
        try:
            return json_safe(value.tolist())
        except (ValueError, TypeError):
            pass

    if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
        return None

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def save_report(
    report: dict[str, Any],
    *,
    report_id: str | None = None,
) -> str:
    """Persist an analysis report and return its report ID."""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if report_id is None:
        report_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "_"
            + uuid4().hex
        )
    elif not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", report_id):
        raise ValueError("Invalid report ID.")

    report_path = REPORTS_DIR / f"analysis_{report_id}.json"
    temporary_path = REPORTS_DIR / f".{report_id}.tmp"

    report_with_id = {
        **report,
        "report_id": report_id,
    }

    safe_report = json_safe(report_with_id)

    try:
        temporary_path.write_text(
            json.dumps(
                safe_report,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(report_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return report_id


def _validate_pipeline_run_id(run_id: str) -> None:
    try:
        UUID(run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid pipeline run ID.",
        ) from exc


def _get_pipeline_run(run_id: str) -> dict[str, Any]:
    _validate_pipeline_run_id(run_id)
    try:
        return run_manager.get_snapshot(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Pipeline run not found.",
        ) from exc


def _experiment_store() -> ExperimentStore:
    return ExperimentStore(REPORTS_DIR)


def _submit_experiment_run(
    *,
    run_id: str,
    experiment_id: str,
    baseline_content: bytes,
    current_content: bytes,
    baseline_filename: str,
    current_filename: str,
) -> str:
    def execute(run: Any) -> None:
        try:
            execute_monitored_pipeline(
                run,
                baseline_source=baseline_content,
                current_source=current_content,
                baseline_filename=baseline_filename,
                current_filename=current_filename,
                baseline_size_bytes=len(baseline_content),
                current_size_bytes=len(current_content),
                write_report=save_report,
                snapshot_run=run_manager.get_snapshot,
                set_report_id=run_manager.set_report_id,
            )
        finally:
            try:
                record = _experiment_store().get(experiment_id)
                if record is not None:
                    _sync_experiment(record)
            except (HTTPException, sqlite3.Error, OSError):
                logger.exception(
                    "Could not persist completed experiment (%s).",
                    experiment_id,
                )

    try:
        run_manager.submit(run_id, execute)
    except RunCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return run_id


def _experiment_report_ai(report_id: str | None) -> dict[str, Any] | None:
    if report_id is None:
        return None
    report_path = REPORTS_DIR / f"analysis_{report_id}.json"
    if not report_path.is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read report for experiment (%s).", report_id)
        return {"status": "error", "error": "The saved AI explanation is unavailable."}
    reasoning = report.get("ai_reasoning")
    return reasoning if isinstance(reasoning, dict) else None


def _sync_experiment(record: dict[str, Any]) -> dict[str, Any]:
    run_id = record.get("recovery_run_id") or record["initial_run_id"]
    try:
        run = run_manager.get_snapshot(run_id)
    except RunNotFoundError:
        record["run"] = None
        summary = record.get("run_summary", {})
        record["ai_reasoning"] = _experiment_report_ai(
            summary.get("report_id")
        )
        if record.get("status") in {"running", "recovery_running"}:
            try:
                updated = _experiment_store().update(
                    record["experiment_id"],
                    {"status": "run_state_unavailable"},
                    event_type="run_state_unavailable",
                    event_details={"run_id": run_id},
                )
                record.update(updated)
            except (sqlite3.Error, OSError, ValueError, KeyError):
                logger.exception(
                    "Could not persist unavailable run state (%s).",
                    record["experiment_id"],
                )
                record["status"] = "run_state_unavailable"
        return record

    record["run"] = run
    record["ai_reasoning"] = _experiment_report_ai(run.get("report_id"))
    if run["status"] not in TERMINAL_STATUSES:
        return record

    is_recovery = record.get("recovery_run_id") == run_id
    last_synced = record.get("last_synced_sequence", -1)
    if (
        last_synced == run["latest_sequence"]
        and record.get("last_synced_report_id") == run.get("report_id")
    ):
        return record

    changes: dict[str, Any] = {
        "last_synced_sequence": run["latest_sequence"],
        "last_synced_report_id": run.get("report_id"),
        "run_summary": {
            "run_id": run_id,
            "status": run["status"],
            "protection_decision": run["protection_decision"],
            "findings": run["findings"],
            "findings_count": run["findings_count"],
            "report_id": run.get("report_id"),
        },
    }
    if is_recovery:
        findings_before = record.get("findings_before", [])
        verification = verify_recovery(
            record["targets"],
            findings_before,
            run["findings"],
            analysis_failed=run["status"] == "failed",
        )
        changes.update(
            status=(
                "recovery_failed"
                if run["status"] == "failed"
                else "recovery_completed"
            ),
            findings_after=run["findings"],
            protection_after=run["protection_decision"],
            recovery_verification=verification,
        )
        event_type = "recovery_analysis_completed"
    else:
        changes.update(
            status=(
                "failed"
                if run["status"] == "failed"
                else "experiment_completed"
            ),
            findings_before=run["findings"],
            protection_before=run["protection_decision"],
        )
        event_type = "experiment_analysis_completed"

    try:
        updated = _experiment_store().update(
            record["experiment_id"],
            changes,
            event_type=event_type,
            event_details={
                "run_id": run_id,
                "run_status": run["status"],
                "protection_decision": run["protection_decision"],
                "findings_count": run["findings_count"],
            },
        )
        updated["run"] = run
        updated["ai_reasoning"] = record["ai_reasoning"]
        return updated
    except (sqlite3.Error, OSError, ValueError, KeyError):
        logger.exception(
            "Could not persist experiment result (%s).",
            record["experiment_id"],
        )
        raise HTTPException(
            status_code=500,
            detail="The experiment ran, but its result could not be persisted.",
        ) from None


@app.get("/api/experiments/scenarios")
def get_experiment_scenarios() -> dict[str, Any]:
    return {
        "scenarios": [
            {"scenario_id": scenario_id, **details}
            for scenario_id, details in EXPERIMENT_SCENARIOS.items()
        ]
    }


@app.get("/api/experiments")
def list_experiments(limit: int = 20) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 100.",
        )
    return {
        "experiments": [
            _sync_experiment(record)
            for record in _experiment_store().list(limit)
        ]
    }


@app.post("/api/experiments", status_code=202)
async def create_experiment(
    scenario_id: str = Form(...),
    dataset_file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    if scenario_id not in EXPERIMENT_SCENARIOS:
        raise HTTPException(status_code=422, detail="Unknown experiment scenario.")

    source_filename = "baseline.csv"
    try:
        if dataset_file is None:
            sample_path = PROJECT_ROOT / "data" / "raw" / "baseline.csv"
            if not sample_path.is_file():
                raise HTTPException(
                    status_code=503,
                    detail="The built-in sample dataset is unavailable.",
                )
            source = load_csv(sample_path)
            source_filename = sample_path.name
        else:
            if (
                dataset_file.filename
                and not dataset_file.filename.lower().endswith(".csv")
            ):
                raise HTTPException(
                    status_code=415,
                    detail="Only CSV uploads are supported.",
                )
            content = await _read_pipeline_upload(dataset_file)
            try:
                source = dataframe_from_bytes(content)
            except ScenarioValidationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            source_filename = (
                (dataset_file.filename or "dataset.csv")
                .replace("\\", "/")
                .rsplit("/", 1)[-1]
            )
    finally:
        if dataset_file is not None:
            await dataset_file.close()

    try:
        injected, operations, targets = inject_scenario(source, scenario_id)
    except ScenarioValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    experiment_id = str(uuid4())
    source_bytes = canonical_csv_bytes(source)
    injected_bytes = canonical_csv_bytes(injected)
    try:
        initial_run_id = run_manager.create_run(
            "DataSentinel Anomaly Experiment"
        )
    except RunCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    record = {
        "experiment_id": experiment_id,
        "scenario_id": scenario_id,
        "scenario_name": EXPERIMENT_SCENARIOS[scenario_id]["name"],
        "description": EXPERIMENT_SCENARIOS[scenario_id]["description"],
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_name": source_filename,
        "dataset_version_before": dataset_fingerprint(source),
        "dataset_version_after_injection": dataset_fingerprint(injected),
        "injection_parameters": operations,
        "targets": targets,
        "initial_run_id": initial_run_id,
        "recovery_run_id": None,
        "findings_before": [],
        "protection_before": None,
        "correction_actions": [],
        "findings_after": [],
        "protection_after": None,
        "recovery_verification": None,
        "last_synced_sequence": -1,
        "last_synced_report_id": None,
    }
    try:
        _experiment_store().create(
            record,
            source_bytes,
            injected_bytes,
        )
    except (sqlite3.Error, OSError, ValueError, KeyError):
        run_manager.discard_queued_run(initial_run_id)
        logger.exception("Could not persist experiment (%s).", experiment_id)
        raise HTTPException(
            status_code=500,
            detail="The experiment could not be persisted.",
        ) from None

    try:
        _submit_experiment_run(
            run_id=initial_run_id,
            experiment_id=experiment_id,
            baseline_content=source_bytes,
            current_content=injected_bytes,
            baseline_filename=source_filename,
            current_filename=f"{experiment_id}_injected.csv",
        )
    except HTTPException:
        run_manager.discard_queued_run(initial_run_id)
        _experiment_store().update(
            experiment_id,
            {"status": "failed"},
            event_type="experiment_start_failed",
            event_details={"reason": "run_capacity"},
        )
        raise

    return _sync_experiment(_experiment_store().get(experiment_id) or record)


def _validate_experiment_id(experiment_id: str) -> None:
    try:
        UUID(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid experiment ID.") from exc


def _load_experiment(experiment_id: str) -> dict[str, Any]:
    _validate_experiment_id(experiment_id)
    record = _experiment_store().get(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return record


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict[str, Any]:
    return _sync_experiment(_load_experiment(experiment_id))


@app.post("/api/experiments/{experiment_id}/correct", status_code=202)
def correct_and_rerun_experiment(experiment_id: str) -> dict[str, Any]:
    with _experiment_recovery_lock:
        return _correct_and_rerun_experiment(experiment_id)


def _correct_and_rerun_experiment(experiment_id: str) -> dict[str, Any]:
    record = _sync_experiment(_load_experiment(experiment_id))
    if record.get("recovery_run_id"):
        return record
    if record.get("status") != "experiment_completed":
        raise HTTPException(
            status_code=409,
            detail="Wait for the initial experiment analysis to finish before recovery.",
        )
    initial_run = record.get("run")
    if not isinstance(initial_run, dict) or initial_run.get("status") == "failed":
        raise HTTPException(
            status_code=409,
            detail="Recovery requires a completed initial pipeline run.",
        )

    store = _experiment_store()
    try:
        source = dataframe_from_bytes(
            store.read_source_csv(experiment_id)
        )
        injected = dataframe_from_bytes(
            store.read_injected_csv(experiment_id)
        )
        corrected, correction_actions = correct_experiment(
            source,
            injected,
            record["injection_parameters"],
        )
    except (OSError, ScenarioValidationError) as exc:
        logger.exception("Experiment recovery preparation failed (%s).", experiment_id)
        raise HTTPException(
            status_code=409,
            detail="The experiment copy could not be safely corrected.",
        ) from exc

    corrected_bytes = canonical_csv_bytes(corrected)
    store.save_recovery_csv(experiment_id, corrected_bytes)
    try:
        recovery_run_id = run_manager.create_run(
            "DataSentinel Experiment Recovery"
        )
    except RunCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    updated = store.update(
        experiment_id,
        {
            "status": "recovery_running",
            "recovery_run_id": recovery_run_id,
            "correction_actions": correction_actions,
            "dataset_version_after_correction": dataset_fingerprint(corrected),
            "recovery_verification": None,
        },
        event_type="controlled_correction_applied",
        event_details={
            "recovery_run_id": recovery_run_id,
            "corrected_dataset_fingerprint": dataset_fingerprint(corrected),
            "actions": correction_actions,
        },
    )
    try:
        _submit_experiment_run(
            run_id=recovery_run_id,
            experiment_id=experiment_id,
            baseline_content=store.read_source_csv(experiment_id),
            current_content=corrected_bytes,
            baseline_filename=record["dataset_name"],
            current_filename=f"{experiment_id}_recovered.csv",
        )
    except HTTPException:
        run_manager.discard_queued_run(recovery_run_id)
        store.update(
            experiment_id,
            {"status": "failed"},
            event_type="recovery_start_failed",
            event_details={"reason": "run_submission_failed"},
        )
        raise
    return _sync_experiment(updated)


async def _read_pipeline_upload(upload: UploadFile) -> bytes:
    if upload.filename and not upload.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Only CSV uploads are supported.",
        )

    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Each CSV upload is limited to {MAX_UPLOAD_SIZE_MB} MB.",
        )
    if not content:
        raise HTTPException(
            status_code=400,
            detail="CSV uploads must not be empty.",
        )
    return content


@app.post("/api/pipeline-runs", status_code=202)
async def create_pipeline_run(
    scenario: str = Form(default="healthy"),
    baseline_file: UploadFile | None = File(default=None),
    current_file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    """Queue a real, monitored analysis using a fixture or uploaded CSVs."""

    baseline_source: bytes | Path
    current_source: bytes | Path
    baseline_filename: str
    current_filename: str
    baseline_size: int
    current_size: int

    try:
        if scenario == "custom":
            if baseline_file is None or current_file is None:
                raise HTTPException(
                    status_code=400,
                    detail="Custom runs require both baseline and current CSV files.",
                )
            baseline_source = await _read_pipeline_upload(baseline_file)
            current_source = await _read_pipeline_upload(current_file)
            baseline_filename = (
                (baseline_file.filename or "baseline.csv")
                .replace("\\", "/")
                .rsplit("/", 1)[-1]
            )
            current_filename = (
                (current_file.filename or "current.csv")
                .replace("\\", "/")
                .rsplit("/", 1)[-1]
            )
            baseline_size = len(baseline_source)
            current_size = len(current_source)
        else:
            if scenario not in PROTECTION_SCENARIOS:
                raise HTTPException(
                    status_code=422,
                    detail="Unknown pipeline scenario.",
                )
            if baseline_file is not None or current_file is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Choose either a fixture scenario or custom CSV uploads.",
                )

            fixture_root = PROTECTION_FIXTURE_DIR.resolve()
            baseline_path = (
                fixture_root / f"{scenario}_baseline.csv"
            ).resolve()
            current_path = (
                fixture_root / f"{scenario}_current.csv"
            ).resolve()
            if (
                not baseline_path.is_relative_to(fixture_root)
                or not current_path.is_relative_to(fixture_root)
                or not baseline_path.is_file()
                or not current_path.is_file()
            ):
                raise HTTPException(
                    status_code=404,
                    detail="The requested scenario fixture is unavailable.",
                )
            baseline_source = baseline_path
            current_source = current_path
            baseline_filename = baseline_path.name
            current_filename = current_path.name
            baseline_size = baseline_path.stat().st_size
            current_size = current_path.stat().st_size
    finally:
        if baseline_file is not None:
            await baseline_file.close()
        if current_file is not None:
            await current_file.close()

    try:
        run_id = run_manager.create_run("DataSentinel CSV Analysis")
    except RunCapacityError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc

    def execute(run: Any) -> None:
        execute_monitored_pipeline(
            run,
            baseline_source=baseline_source,
            current_source=current_source,
            baseline_filename=baseline_filename,
            current_filename=current_filename,
            baseline_size_bytes=baseline_size,
            current_size_bytes=current_size,
            write_report=save_report,
            snapshot_run=run_manager.get_snapshot,
            set_report_id=run_manager.set_report_id,
        )

    try:
        run_manager.submit(run_id, execute)
    except RunCapacityError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc

    return run_manager.get_snapshot(run_id)


@app.get("/api/pipeline-runs/{run_id}")
def get_pipeline_run(run_id: str) -> dict[str, Any]:
    """Return the authoritative current state for a monitored run."""

    return _get_pipeline_run(run_id)


@app.get("/api/pipeline-runs/{run_id}/history")
def get_pipeline_run_history(
    run_id: str,
    after_sequence: int = 0,
) -> dict[str, Any]:
    """Return retained events after a sequence cursor."""

    if after_sequence < 0:
        raise HTTPException(
            status_code=422,
            detail="after_sequence must not be negative.",
        )
    _get_pipeline_run(run_id)
    try:
        events, truncated = run_manager.list_events(run_id, after_sequence)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Pipeline run not found.",
        ) from exc
    return {
        "run_id": run_id,
        "events": [event.model_dump(mode="json") for event in events],
        "history_truncated": truncated,
    }


@app.get("/api/pipeline-runs/{run_id}/events")
async def stream_pipeline_run_events(
    run_id: str,
    request: Request,
    after_sequence: int = 0,
) -> StreamingResponse:
    """Stream ordered run events using Server-Sent Events."""

    snapshot = _get_pipeline_run(run_id)
    if after_sequence < 0:
        raise HTTPException(
            status_code=422,
            detail="after_sequence must not be negative.",
        )
    last_event_id = request.headers.get("last-event-id")
    if last_event_id is not None:
        try:
            after_sequence = max(after_sequence, int(last_event_id))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Last-Event-ID must be a sequence number.",
            ) from None
    after_sequence = min(after_sequence, snapshot["latest_sequence"])

    try:
        run_manager.begin_subscription(run_id)
    except RunCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    async def event_stream():
        nonlocal after_sequence
        try:
            while True:
                if await request.is_disconnected():
                    break

                events, truncated, latest_state = await asyncio.to_thread(
                    run_manager.wait_for_events,
                    run_id,
                    after_sequence,
                    10.0,
                )

                if truncated:
                    sequence = latest_state["latest_sequence"]
                    payload = json.dumps(
                        latest_state,
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    yield (
                        f"id: {sequence}\nevent: reset\ndata: {payload}\n\n"
                    )
                    after_sequence = sequence
                    events = []

                for event in events:
                    yield (
                        f"id: {event.sequence}\nevent: pipeline"
                        f"\ndata: {event.model_dump_json()}\n\n"
                    )
                    after_sequence = event.sequence

                if (
                    latest_state["status"] in TERMINAL_STATUSES
                    and after_sequence >= latest_state["latest_sequence"]
                ):
                    break

                if not events and not truncated:
                    yield ": heartbeat\n\n"
        finally:
            run_manager.end_subscription(run_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/pipeline-runs/{run_id}/report")
def get_pipeline_run_report(run_id: str) -> FileResponse:
    """Download the report produced by a completed monitored run."""

    state = _get_pipeline_run(run_id)
    if state["status"] not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="The pipeline report is not ready yet.",
        )
    report_id = state.get("report_id")
    if not report_id:
        raise HTTPException(
            status_code=409,
            detail="The run has not produced a report yet.",
        )
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", report_id):
        raise HTTPException(
            status_code=500,
            detail="The run contains an invalid report reference.",
        )

    report_path = (REPORTS_DIR / f"analysis_{report_id}.json").resolve()
    if (
        not report_path.is_relative_to(REPORTS_DIR.resolve())
        or not report_path.is_file()
    ):
        raise HTTPException(
            status_code=404,
            detail="The pipeline report is unavailable.",
        )
    return FileResponse(
        path=report_path,
        media_type="application/json",
        filename=f"datasentinel_run_{run_id}.json",
    )


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Return API and model configuration information."""

    return {
        "status": "online",
        "service": "DataSentinel AI",
        "version": "1.0.0",
        "configured_ai_model": AI_MODEL,
        "analysis_engine": "Python",
        "workflow_engine": "LangGraph",
    }


@app.post("/api/analyze")
async def analyze_datasets(
    baseline_file: UploadFile = File(...),
    current_file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Analyze uploaded baseline and current CSV files.

    Python performs the actual analysis. Gemma provides explanations
    through the existing LangGraph workflow.
    """

    for upload in (baseline_file, current_file):
        if upload.filename and not upload.filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=415,
                detail="Only CSV uploads are supported.",
            )

    baseline_bytes = await baseline_file.read(MAX_UPLOAD_BYTES + 1)

    if len(baseline_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"The baseline file exceeds the "
                f"{MAX_UPLOAD_SIZE_MB} MB upload limit."
            ),
        )

    current_bytes = await current_file.read(MAX_UPLOAD_BYTES + 1)

    if len(current_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"The current file exceeds the "
                f"{MAX_UPLOAD_SIZE_MB} MB upload limit."
            ),
        )

    if not baseline_bytes:
        raise HTTPException(
            status_code=400,
            detail="The baseline CSV file is empty.",
        )

    if not current_bytes:
        raise HTTPException(
            status_code=400,
            detail="The current CSV file is empty.",
        )

    try:
        baseline_df = load_csv(BytesIO(baseline_bytes))
        current_df = load_csv(BytesIO(current_bytes))

    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        logger.info("Uploaded CSV failed validation: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail=(
                "CSV validation failed. Check that the file is a valid, "
                "UTF-8 CSV with a header row and data rows."
            ),
        ) from exc

    try:
        workflow_result = data_sentinel_workflow.invoke(
            {
                "baseline": baseline_df,
                "current": current_df,
            }
        )

        report = workflow_result.get("final_report")

        if not isinstance(report, dict):
            raise RuntimeError(
                "The workflow did not produce a valid final report."
            )

    except Exception as exc:
        logger.error(
            "Dataset analysis workflow failed (%s).",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Data analysis workflow failed. No downstream processing was authorized.",
        ) from exc

    report["dataset_metadata"] = {
        "baseline": {
            "filename": (baseline_file.filename or "baseline.csv")
            .replace("\\", "/")
            .rsplit("/", 1)[-1],
            "rows": int(len(baseline_df)),
            "columns": int(len(baseline_df.columns)),
            "size_bytes": len(baseline_bytes),
        },
        "current": {
            "filename": (current_file.filename or "current.csv")
            .replace("\\", "/")
            .rsplit("/", 1)[-1],
            "rows": int(len(current_df)),
            "columns": int(len(current_df.columns)),
            "size_bytes": len(current_bytes),
        },
    }

    report["generated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    report_id = save_report(report)

    return json_safe(
        {
            "report_id": report_id,
            **report,
        }
    )


@app.get("/api/reports")
def list_reports() -> dict[str, Any]:
    """Return saved analysis reports, newest first."""

    reports = []

    for path in sorted(
        REPORTS_DIR.glob("analysis_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))

            analysis = report.get("analysis", {})
            protection = report.get("protection", {})

            reports.append(
                {
                    "report_id": report.get(
                        "report_id",
                        path.stem.removeprefix("analysis_"),
                    ),
                    "generated_at": report.get("generated_at"),
                    "overall_status": report.get(
                        "overall_status",
                        "unknown",
                    ),
                    "workflow_status": report.get(
                        "workflow_status",
                        "unknown",
                    ),
                    "protection_decision": protection.get(
                        "decision",
                        "UNKNOWN",
                    ),
                    "finding_count": len(
                        analysis.get("findings", [])
                    ),
                    "baseline_filename": report.get(
                        "dataset_metadata", {}
                    ).get("baseline", {}).get("filename"),
                    "current_filename": report.get(
                        "dataset_metadata", {}
                    ).get("current", {}).get("filename"),
                }
            )

        except (OSError, json.JSONDecodeError):
            continue

    return {
        "reports": reports,
        "total": len(reports),
    }


@app.get("/api/reports/{report_id}")
def download_report(report_id: str) -> FileResponse:
    """Download a saved JSON report."""

    # Prevent path traversal by accepting only generated ID characters.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", report_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid report ID.",
        )

    report_path = REPORTS_DIR / f"analysis_{report_id}.json"

    reports_root = REPORTS_DIR.resolve()
    resolved_report_path = report_path.resolve()
    if not resolved_report_path.is_relative_to(reports_root):
        raise HTTPException(
            status_code=400,
            detail="Invalid report ID.",
        )

    if not resolved_report_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Report not found.",
        )

    return FileResponse(
        path=resolved_report_path,
        media_type="application/json",
        filename=f"datasentinel_report_{report_id}.json",
    )