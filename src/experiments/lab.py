from __future__ import annotations

import hashlib
import math
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from src.detectors.distribution_detector import _is_identifier_column
from src.utils.data_loader import load_csv


SCENARIOS: dict[str, dict[str, str]] = {
    "missing_values": {
        "name": "Missing-value injection",
        "description": "Set a controlled portion of one populated column to missing.",
        "finding_type": "missing_value_anomaly",
        "correction": "Restore only the injected cells from the preserved source dataset.",
    },
    "duplicate_records": {
        "name": "Duplicate-record injection",
        "description": "Append copies of source rows to raise the duplicate-row rate.",
        "finding_type": "duplicate_anomaly",
        "correction": "Remove only the appended rows created by this experiment.",
    },
    "schema_change": {
        "name": "Unexpected schema change",
        "description": "Add a clearly named column that is absent from the source schema.",
        "finding_type": "schema_change",
        "correction": "Remove only the experiment-added column.",
    },
    "numeric_drift": {
        "name": "Numeric distribution drift",
        "description": "Multiply a measured numeric column by a controlled factor.",
        "finding_type": "distribution_drift",
        "correction": "Restore the transformed column from the preserved source dataset.",
    },
    "categorical_drift": {
        "name": "Unexpected categorical values",
        "description": "Replace a controlled portion of a categorical column with a new category.",
        "finding_type": "categorical_drift",
        "correction": "Restore only the injected category values from the source dataset.",
    },
    "combined": {
        "name": "Combined data-quality incident",
        "description": "Inject missing values and duplicate rows in one isolated dataset copy.",
        "finding_type": "multiple",
        "correction": "Restore the injected missing cells and remove only appended duplicate rows.",
    },
}

_INJECTED_COLUMN = "__datasentinel_experiment_column__"
_INJECTED_CATEGORY = "__DATASENTINEL_INJECTED_CATEGORY__"


class ScenarioValidationError(ValueError):
    """The selected scenario cannot be applied safely to this dataset."""


def canonical_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    """Serialize a normalized dataset deterministically for hashing/storage."""

    text = dataframe.to_csv(
        index=False,
        lineterminator="\n",
        na_rep="",
    )
    return text.encode("utf-8")


def dataset_fingerprint(dataframe: pd.DataFrame) -> str:
    """Hash the canonical, parsed CSV representation including row order."""

    return hashlib.sha256(canonical_csv_bytes(dataframe)).hexdigest()


def _column_with_values(dataframe: pd.DataFrame) -> str:
    minimum_values = max(1, math.ceil(len(dataframe) * 0.15))
    candidates = [
        column
        for column in dataframe.columns
        if not _is_identifier_column(column)
    ] + [
        column
        for column in dataframe.columns
        if _is_identifier_column(column)
    ]
    for column in candidates:
        if dataframe[column].notna().sum() >= minimum_values:
            return str(column)
    raise ScenarioValidationError(
        "Missing-value injection requires at least 15% populated cells in one column."
    )


def _numeric_column(dataframe: pd.DataFrame) -> str:
    for column in dataframe.columns:
        values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        if (
            is_numeric_dtype(dataframe[column])
            and not is_bool_dtype(dataframe[column])
            and not _is_identifier_column(column)
            and len(values) >= 8
            and values.nunique() >= 2
        ):
            return str(column)
    raise ScenarioValidationError(
        "Numeric drift requires a numeric column with at least 8 populated values."
    )


def _categorical_column(dataframe: pd.DataFrame) -> str:
    for column in dataframe.columns:
        values = dataframe[column].dropna()
        if (
            not is_numeric_dtype(dataframe[column])
            and not is_bool_dtype(dataframe[column])
            and len(values) >= 34
            and values.astype(str).nunique() >= 2
        ):
            return str(column)
    raise ScenarioValidationError(
        "Categorical drift requires a non-numeric column with at least 20 populated values and 2 categories."
    )


def inject_scenario(
    source: pd.DataFrame,
    scenario_id: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, str | None]]]:
    if scenario_id not in SCENARIOS:
        raise ScenarioValidationError("Unknown experiment scenario.")
    if source.empty or source.columns.empty:
        raise ScenarioValidationError("The selected dataset has no usable data.")

    current = source.copy(deep=True)
    operations: list[dict[str, Any]] = []
    targets: list[dict[str, str | None]] = []

    if scenario_id in {"missing_values", "combined"}:
        column = _column_with_values(source)
        affected_rows = max(1, math.ceil(len(source) * 0.15))
        missing_positions = [
            int(position)
            for position in source[column].notna().to_numpy().nonzero()[0][
                :affected_rows
            ]
        ]
        if len(missing_positions) != affected_rows:
            raise ScenarioValidationError(
                "Missing-value injection requires at least 15% populated cells in its selected column."
            )
        current.iloc[
            missing_positions, current.columns.get_loc(column)
        ] = pd.NA
        operations.append(
            {
                "kind": "missing_values",
                "column": column,
                "affected_rows": affected_rows,
            }
        )
        targets.append(
            {"finding_type": "missing_value_anomaly", "column": column}
        )

    if scenario_id in {"duplicate_records", "combined"}:
        duplicate_rows = max(1, math.ceil(len(source) * 0.1))
        unavailable_rows = set()
        missing_operation = next(
            (
                operation
                for operation in operations
                if operation["kind"] == "missing_values"
            ),
            None,
        )
        if missing_operation is not None:
            unavailable_rows.update(
                int(position)
                for position in source[
                    missing_operation["column"]
                ].notna().to_numpy().nonzero()[0][
                    :missing_operation["affected_rows"]
                ]
            )
        duplicate_positions = [
            position
            for position in range(len(source))
            if position not in unavailable_rows
        ][:duplicate_rows]
        copies = source.iloc[duplicate_positions].copy(deep=True)
        if len(copies) != duplicate_rows:
            raise ScenarioValidationError(
                "The combined scenario requires enough unaffected rows to inject duplicates."
            )
        current = pd.concat([current, copies], ignore_index=True)
        operations.append(
            {"kind": "duplicate_records", "affected_rows": duplicate_rows}
        )
        targets.append(
            {"finding_type": "duplicate_anomaly", "column": None}
        )

    if scenario_id == "schema_change":
        if _INJECTED_COLUMN in source.columns:
            raise ScenarioValidationError(
                "The dataset already contains the reserved experiment column."
            )
        current[_INJECTED_COLUMN] = "experiment_added"
        operations.append(
            {"kind": "schema_change", "column": _INJECTED_COLUMN}
        )
        targets.append({"finding_type": "schema_change", "column": _INJECTED_COLUMN})

    if scenario_id == "numeric_drift":
        column = _numeric_column(source)
        current[column] = pd.to_numeric(current[column], errors="coerce") * 5
        operations.append(
            {
                "kind": "numeric_drift",
                "column": column,
                "affected_rows": int(source[column].notna().sum()),
                "factor": 5,
            }
        )
        targets.append(
            {"finding_type": "distribution_drift", "column": column}
        )

    if scenario_id == "categorical_drift":
        column = _categorical_column(source)
        affected_rows = max(1, math.ceil(len(source) * 0.3))
        existing_categories = set(source[column].dropna().astype(str))
        injected_category = _INJECTED_CATEGORY
        suffix = 1
        while injected_category in existing_categories:
            injected_category = f"{_INJECTED_CATEGORY}_{suffix}"
            suffix += 1
        if not is_numeric_dtype(current[column]):
            current[column] = current[column].astype("object")
        current.iloc[:affected_rows, current.columns.get_loc(column)] = (
            injected_category
        )
        operations.append(
            {
                "kind": "categorical_drift",
                "column": column,
                "affected_rows": affected_rows,
                "injected_category": injected_category,
            }
        )
        targets.append(
            {"finding_type": "categorical_drift", "column": column}
        )

    return current, operations, targets


def correct_experiment(
    source: pd.DataFrame,
    injected: pd.DataFrame,
    operations: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[str]]:
    corrected = injected.copy(deep=True)
    actions: list[str] = []

    for operation in reversed(operations):
        kind = operation["kind"]
        column = operation.get("column")
        affected_rows = operation.get("affected_rows", 0)

        if kind == "duplicate_records":
            corrected = corrected.iloc[:-affected_rows].reset_index(drop=True)
            actions.append(f"Removed {affected_rows} experiment-added duplicate rows.")
        elif kind == "schema_change":
            corrected = corrected.drop(columns=[column])
            actions.append(f"Removed experiment-added column {column}.")
        elif kind in {"missing_values", "numeric_drift", "categorical_drift"}:
            if column not in source.columns or column not in corrected.columns:
                raise ScenarioValidationError(
                    "The experiment copy no longer matches its source schema."
                )
            if kind == "numeric_drift":
                corrected[column] = source[column].to_numpy()
            else:
                if kind == "missing_values":
                    positions = source[column].notna().to_numpy().nonzero()[0][
                        :affected_rows
                    ]
                else:
                    positions = range(affected_rows)
                column_index = corrected.columns.get_loc(column)
                corrected.iloc[positions, column_index] = (
                    source.iloc[positions][column].to_numpy()
                )
                corrected[column] = corrected[column].astype(
                    source[column].dtype
                )
            if kind == "missing_values":
                actions.append(
                    f"Restored {affected_rows} injected missing cells in {column}."
                )
            elif kind == "numeric_drift":
                actions.append(f"Restored transformed column {column} from source.")
            else:
                actions.append(
                    f"Restored {affected_rows} injected category values in {column}."
                )

    if dataset_fingerprint(corrected) != dataset_fingerprint(source):
        raise ScenarioValidationError(
            "The controlled correction did not restore the source dataset version."
        )
    return corrected, actions


def verify_recovery(
    targets: list[dict[str, Any]],
    findings_before: list[dict[str, Any]],
    findings_after: list[dict[str, Any]],
    *,
    analysis_failed: bool = False,
) -> dict[str, Any]:
    def detected(
        finding: dict[str, Any],
        target: dict[str, Any],
    ) -> bool:
        return (
            finding.get("detector_type", finding.get("type"))
            == target["finding_type"]
            and finding.get("column") == target.get("column")
        )

    before_flags = [
        any(detected(finding, target) for finding in findings_before)
        for target in targets
    ]
    after_flags = [
        any(detected(finding, target) for finding in findings_after)
        for target in targets
    ]
    if analysis_failed:
        status = "analysis_failed"
    elif not all(before_flags):
        status = "injection_not_detected"
    elif any(after_flags):
        status = "unresolved"
    else:
        status = "resolved"

    targeted_signatures = {
        (target["finding_type"], target.get("column"))
        for target in targets
    }
    unrelated_remaining = sum(
        (
            finding.get("detector_type", finding.get("type")),
            finding.get("column"),
        )
        not in targeted_signatures
        for finding in findings_after
    )
    return {
        "status": status,
        "target_findings_detected_before": before_flags,
        "target_findings_detected_after": after_flags,
        "unrelated_findings_remaining": unrelated_remaining,
    }


def dataframe_from_bytes(content: bytes) -> pd.DataFrame:
    try:
        dataframe = load_csv(content)
    except (TypeError, ValueError) as exc:
        raise ScenarioValidationError(
            "The uploaded CSV is empty or could not be parsed."
        ) from exc
    return dataframe
