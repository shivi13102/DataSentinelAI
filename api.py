from __future__ import annotations

import asyncio
import json
import logging
import re
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