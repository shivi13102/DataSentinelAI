from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.graph.workflow import data_sentinel_workflow
from src.utils.data_loader import load_csv


PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

AI_MODEL = "gemma3:1b"

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
    allow_headers=["Content-Type"],
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


def save_report(report: dict[str, Any]) -> str:
    """Persist an analysis report and return its report ID."""

    report_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + uuid4().hex[:8]
    )

    report_path = REPORTS_DIR / f"analysis_{report_id}.json"

    report_with_id = {
        "report_id": report_id,
        **report,
    }

    safe_report = json_safe(report_with_id)

    report_path.write_text(
        json.dumps(safe_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return report_id


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

    baseline_bytes = await baseline_file.read()
    current_bytes = await current_file.read()

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

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"CSV validation failed: {exc}",
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
        raise HTTPException(
            status_code=500,
            detail=f"Data analysis workflow failed: {exc}",
        ) from exc

    report["dataset_metadata"] = {
        "baseline": {
            "filename": Path(
                baseline_file.filename or "baseline.csv"
            ).name,
            "rows": int(len(baseline_df)),
            "columns": int(len(baseline_df.columns)),
            "size_bytes": len(baseline_bytes),
        },
        "current": {
            "filename": Path(
                current_file.filename or "current.csv"
            ).name,
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
    allowed = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_-"
    )

    if not report_id or any(char not in allowed for char in report_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid report ID.",
        )

    report_path = REPORTS_DIR / f"analysis_{report_id}.json"

    if not report_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Report not found.",
        )

    return FileResponse(
        path=report_path,
        media_type="application/json",
        filename=f"datasentinel_report_{report_id}.json",
    )