from io import BytesIO

import pandas as pd
import pytest

from src.utils.data_loader import load_csv


def test_load_valid_csv_bytes():
    csv_content = b"id,amount\n1,100\n2,200\n3,300\n"

    dataframe = load_csv(csv_content)

    assert len(dataframe) == 3
    assert list(dataframe.columns) == ["id", "amount"]
    assert dataframe["amount"].tolist() == [100, 200, 300]


def test_load_csv_file_like_object():
    csv_file = BytesIO(
        b"name,status\nAlice,Approved\nBob,Pending\n"
    )

    dataframe = load_csv(csv_file)

    assert len(dataframe) == 2
    assert dataframe["name"].tolist() == ["Alice", "Bob"]


def test_load_csv_from_file_path(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "id,value\n1,10\n2,20\n",
        encoding="utf-8",
    )

    dataframe = load_csv(str(csv_path))

    assert dataframe.shape == (2, 2)


def test_missing_file_raises_error():
    with pytest.raises(FileNotFoundError):
        load_csv("this_file_does_not_exist.csv")


def test_empty_csv_raises_error():
    with pytest.raises(ValueError, match="empty"):
        load_csv(b"")


def test_csv_with_headers_but_no_rows_raises_error():
    with pytest.raises(ValueError, match="no data rows"):
        load_csv(b"id,name\n")


def test_duplicate_column_names_are_rejected():
    with pytest.raises(ValueError, match="Duplicate column names"):
        load_csv(b"id,name,name\n1,Alice,Bob\n")


def test_blank_column_name_is_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        load_csv(b"id,   \n1,10\n")


def test_file_size_limit_is_enforced(tmp_path):
    csv_path = tmp_path / "large.csv"

    # Generate a file larger than 1 MB.
    csv_path.write_bytes(
        b"id,value\n" + b"1,100\n" * 200_000
    )

    with pytest.raises(ValueError, match="exceeds"):
        load_csv(str(csv_path), max_file_size_mb=1)


def test_invalid_file_input_type_is_rejected():
    with pytest.raises(TypeError):
        load_csv(12345)


def test_invalid_size_limit_is_rejected():
    with pytest.raises(ValueError, match="at least 1"):
        load_csv(
            b"id,value\n1,100\n",
            max_file_size_mb=0,
        )
