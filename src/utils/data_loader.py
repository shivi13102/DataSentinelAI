from __future__ import annotations

import csv
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pandas as pd


def load_csv(
    file: Any,
    *,
    max_file_size_mb: int = 100,
) -> pd.DataFrame:
    """
    Load and validate a CSV file.

    Accepts a file path, bytes object, or file-like object,
    including Streamlit's UploadedFile.

    Returns a DataFrame without modifying the source file.
    """

    if max_file_size_mb < 1:
        raise ValueError("max_file_size_mb must be at least 1.")

    max_file_size_bytes = max_file_size_mb * 1024 * 1024

    # Resolve the input source and validate its size.
    if isinstance(file, bytes):
        content = file
        source = BytesIO(content)

    elif isinstance(file, (str, Path)):
        path = Path(file)

        if not path.is_file():
            raise FileNotFoundError(f"CSV file not found: {path}")

        if path.stat().st_size > max_file_size_bytes:
            raise ValueError(
                f"CSV file exceeds the {max_file_size_mb} MB limit."
            )

        source = path
        content = None

    elif hasattr(file, "read"):
        if hasattr(file, "getvalue"):
            content = file.getvalue()
        else:
            original_position = (
                file.tell() if hasattr(file, "tell") else None
            )
            content = file.read()

            if original_position is not None and hasattr(file, "seek"):
                file.seek(original_position)

        if not isinstance(content, bytes):
            raise ValueError("The uploaded file must contain bytes.")

        if len(content) > max_file_size_bytes:
            raise ValueError(
                f"CSV file exceeds the {max_file_size_mb} MB limit."
            )

        source = BytesIO(content)

    else:
        raise TypeError(
            "file must be a file path, bytes object, or file-like object."
        )

    # Inspect the original CSV header before Pandas can rename
    # duplicate column names automatically.
    try:
        if content is None:
            with open(
                source,
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as header_file:
                original_columns = next(
                    csv.reader(header_file),
                    [],
                )
        else:
            decoded_content = content.decode("utf-8-sig")
            original_columns = next(
                csv.reader(StringIO(decoded_content)),
                [],
            )

        if not original_columns:
            raise ValueError("The CSV file is empty.")

        if len(original_columns) != len(set(original_columns)):
            seen = set()
            duplicate_columns = []

            for column in original_columns:
                if column in seen and column not in duplicate_columns:
                    duplicate_columns.append(column)

                seen.add(column)

            raise ValueError(
                f"Duplicate column names found: {duplicate_columns}"
            )

        # Parse the CSV.
        dataframe = pd.read_csv(source)

    except pd.errors.EmptyDataError as exc:
        raise ValueError("The CSV file is empty.") from exc

    except ValueError:
        raise

    except (
        pd.errors.ParserError,
        UnicodeDecodeError,
        csv.Error,
    ) as exc:
        raise ValueError(
            f"Unable to parse the CSV file: {exc}"
        ) from exc

    # Validate the resulting DataFrame.
    if dataframe.empty:
        raise ValueError(
            "The CSV contains column headers but no data rows."
        )

    if len(dataframe.columns) == 0:
        raise ValueError("The CSV does not contain any columns.")

    if dataframe.columns.duplicated().any():
        duplicate_columns = dataframe.columns[
            dataframe.columns.duplicated()
        ].tolist()

        raise ValueError(
            f"Duplicate column names found: {duplicate_columns}"
        )

    if any(
        not isinstance(column, str) or not column.strip()
        for column in dataframe.columns
    ):
        raise ValueError(
            "Column names must be non-empty strings."
        )

    return dataframe
