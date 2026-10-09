# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for Excel table reading."""

import json
import re
import openpyxl
from datetime import date, datetime
from pathlib import Path

import pytest

from stanok.gui.strings import STRINGS
from stanok.tables import ExcelReader, TableReadError


FIXTURE_DIR = Path(__file__).parent.parent / "json" / "001-tables"


def _normalize_for_json(obj):
    """Convert datetime/date to ISO format strings for JSON comparison."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _normalize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_for_json(v) for v in obj]
    return obj


def _make_xlsx(path: Path, rows: list) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()
    return path


def test_read_basic():
    reader = ExcelReader()
    result = reader.read(FIXTURE_DIR / "input.xlsx")
    with open(FIXTURE_DIR / "expected.json") as f:
        expected = json.load(f)
    assert _normalize_for_json(result) == expected


def test_empty_rows_included():
    reader = ExcelReader()
    result = reader.read(FIXTURE_DIR / "input.xlsx")
    assert len(result) == 5  # 4 data + 1 empty
    empty_row = result[3]
    assert all(v is None for v in empty_row.values())


def test_types_preserved():
    reader = ExcelReader()
    result = reader.read(FIXTURE_DIR / "input.xlsx")
    assert isinstance(result[0]["integer"], int)
    assert isinstance(result[0]["float"], float)
    assert isinstance(result[0]["date"], date)


def test_empty_file(tmp_path):
    path = _make_xlsx(tmp_path / "empty.xlsx", [["col1", "col2"]])
    assert ExcelReader().read(path) == []


def test_missing_file_raises():
    with pytest.raises(TableReadError):
        ExcelReader().read(Path("nonexistent.xlsx"))


def test_corrupted_file_raises(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"not an xlsx file")
    with pytest.raises(TableReadError):
        ExcelReader().read(path)


def test_headers_with_spaces(tmp_path):
    path = _make_xlsx(tmp_path / "spaces.xlsx", [[" col 1 ", "col 2"], ["a", "b"]])
    result = ExcelReader().read(path)
    assert list(result[0].keys()) == ["col 1", "col 2"]


def test_duplicate_headers_raises(tmp_path):
    path = _make_xlsx(tmp_path / "dups.xlsx", [["a", "a", "b"], [1, 2, 3]])
    with pytest.raises(
        TableReadError,
        match=re.escape(STRINGS.TBL_DUP_HEADERS.format(headers="a")),
    ):
        ExcelReader().read(path)


def test_empty_header_in_middle_raises(tmp_path):
    path = _make_xlsx(tmp_path / "gap.xlsx", [["a", None, "b"], [1, 2, 3]])
    with pytest.raises(
        TableReadError,
        match=re.escape(STRINGS.TBL_EMPTY_HEADER.format(column="B")),
    ):
        ExcelReader().read(path)


def test_trailing_empty_headers_trimmed(tmp_path):
    path = _make_xlsx(tmp_path / "tail.xlsx", [["a", "b", None, None], [1, 2, None, None]])
    result = ExcelReader().read(path)
    assert list(result[0].keys()) == ["a", "b"]


def test_ragged_rows_normalized(tmp_path):
    path = _make_xlsx(
        tmp_path / "ragged.xlsx",
        [["a", "b"], [1], [1, 2, 999]],
    )
    result = ExcelReader().read(path)
    assert result[0] == {"a": 1, "b": None}
    assert result[1] == {"a": 1, "b": 2}  # лишнее отброшено, ключей-мусора нет


def test_workbook_closed_after_read(tmp_path):
    # На Windows незакрытый read_only-workbook лочит файл.
    path = _make_xlsx(tmp_path / "lock.xlsx", [["a"], [1]])
    ExcelReader().read(path)
    path.unlink()  # упадёт, если файл всё ещё открыт
