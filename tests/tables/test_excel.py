# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for Excel table reading."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

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


def test_empty_file():
    # Create temporary empty xlsx with only headers
    import openpyxl
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["col1", "col2"])
        wb.save(tmp.name)
        reader = ExcelReader()
        result = reader.read(Path(tmp.name))
        assert result == []


def test_missing_file_raises():
    with pytest.raises(TableReadError):
        ExcelReader().read(Path("nonexistent.xlsx"))


def test_corrupted_file_raises():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(b"not an xlsx file")
        tmp.flush()
        with pytest.raises(TableReadError):
            ExcelReader().read(Path(tmp.name))


def test_headers_with_spaces():
    import openpyxl
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([" col 1 ", "col 2"])
        ws.append(["a", "b"])
        wb.save(tmp.name)
        reader = ExcelReader()
        result = reader.read(Path(tmp.name))
        assert list(result[0].keys()) == ["col 1", "col 2"]