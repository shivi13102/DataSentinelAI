from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class ExperimentStore:
    """SQLite metadata and isolated, versioned CSV copies for experiments."""

    _lock = threading.RLock()

    def __init__(self, reports_dir: Path) -> None:
        self._root = reports_dir / "experiments"
        self._root.mkdir(parents=True, exist_ok=True)
        self._database = reports_dir / "experiments.sqlite3"
        with self._transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    record_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    FOREIGN KEY (experiment_id)
                        REFERENCES experiments(experiment_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create(
        self,
        record: dict[str, Any],
        source_csv: bytes,
        injected_csv: bytes,
    ) -> None:
        experiment_id = record["experiment_id"]
        source_path = self._source_path(experiment_id)
        injected_path = self._injected_path(experiment_id)
        with self._lock:
            try:
                self._write_atomic(source_path, source_csv)
                self._write_atomic(injected_path, injected_csv)
                now = datetime.now(timezone.utc).isoformat()
                with self._transaction() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        """
                        INSERT INTO experiments
                            (experiment_id, created_at, updated_at, revision, record_json)
                        VALUES (?, ?, ?, 1, ?)
                        """,
                        (
                            experiment_id,
                            now,
                            now,
                            json.dumps(record, allow_nan=False),
                        ),
                    )
                    self._append_event(
                        connection,
                        experiment_id,
                        "experiment_created",
                        {
                            "scenario_id": record["scenario_id"],
                            "source_fingerprint": record[
                                "dataset_version_before"
                            ],
                            "injected_fingerprint": record[
                                "dataset_version_after_injection"
                            ],
                        },
                    )
            except Exception:
                source_path.unlink(missing_ok=True)
                injected_path.unlink(missing_ok=True)
                raise

    def get(self, experiment_id: str) -> dict[str, Any] | None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT record_json FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
        return json.loads(row["record_json"]) if row else None

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT record_json FROM experiments
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def update(
        self,
        experiment_id: str,
        changes: dict[str, Any],
        *,
        event_type: str,
        event_details: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock, self._transaction() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT record_json, revision FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
            if row is None:
                raise KeyError(experiment_id)
            record = json.loads(row["record_json"])
            record.update(changes)
            updated_at = datetime.now(timezone.utc).isoformat()
            record["updated_at"] = updated_at
            record["revision"] = row["revision"] + 1
            connection.execute(
                """
                UPDATE experiments
                SET updated_at = ?, revision = ?, record_json = ?
                WHERE experiment_id = ?
                """,
                (
                    updated_at,
                    row["revision"] + 1,
                    json.dumps(record, allow_nan=False),
                    experiment_id,
                ),
            )
            self._append_event(
                connection,
                experiment_id,
                event_type,
                event_details,
            )
            return record

    def read_source_csv(self, experiment_id: str) -> bytes:
        return self._source_path(experiment_id).read_bytes()

    def read_injected_csv(self, experiment_id: str) -> bytes:
        return self._injected_path(experiment_id).read_bytes()

    def save_recovery_csv(self, experiment_id: str, content: bytes) -> None:
        self._write_atomic(self._recovery_path(experiment_id), content)

    def read_recovery_csv(self, experiment_id: str) -> bytes:
        return self._recovery_path(experiment_id).read_bytes()

    def _append_event(
        self,
        connection: sqlite3.Connection,
        experiment_id: str,
        event_type: str,
        details: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO experiment_events
                (experiment_id, recorded_at, event_type, details_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                experiment_id,
                datetime.now(timezone.utc).isoformat(),
                event_type,
                json.dumps(details, allow_nan=False),
            ),
        )

    def _write_atomic(self, path: Path, content: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _source_path(self, experiment_id: str) -> Path:
        return self._root / f"{experiment_id}_source.csv"

    def _injected_path(self, experiment_id: str) -> Path:
        return self._root / f"{experiment_id}_injected.csv"

    def _recovery_path(self, experiment_id: str) -> Path:
        return self._root / f"{experiment_id}_recovered.csv"
