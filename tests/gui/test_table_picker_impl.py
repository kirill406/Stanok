# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for variant 2: column + value picker."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from openpyxl import Workbook
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from stanok.gui.strings import STRINGS
from stanok.gui.table_picker import picker_available
from stanok.gui.table_picker_impl import PickerDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _book(tmp_path, rows=(("Иван", 100), ("Петр", 200))):
    wb = Workbook()
    ws = wb.active
    ws.append(["ФИО", "Сумма"])
    for row in rows:
        ws.append(list(row))
    path = tmp_path / "data.xlsx"
    wb.save(path)
    return path


def test_picker_module_is_available():
    assert picker_available() is True


def test_columns_list_headers(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    assert [
        dlg.column_combo.itemText(i) for i in range(dlg.column_combo.count())
    ] == ["ФИО", "Сумма"]
    dlg.close()


def test_column_fills_distinct_numbers(qapp, tmp_path):
    _book(tmp_path, rows=(("Иван", 100), ("Петр", 200), ("Анна", 100)))
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    dlg.column_combo.setCurrentIndex(1)
    assert [
        dlg.value_combo.itemText(i) for i in range(dlg.value_combo.count())
    ] == ["100", "200"]
    dlg.close()


def test_non_numeric_column_has_no_values(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    dlg.column_combo.setCurrentIndex(0)
    assert dlg.value_combo.count() == 0
    assert dlg.hint.text() == STRINGS.PICK_NO_VALUES
    assert not dlg.ok_btn.isEnabled()
    dlg.close()


def test_choose_writes_value(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    dlg.column_combo.setCurrentIndex(1)
    dlg.value_combo.setCurrentIndex(dlg.value_combo.findData(200))
    assert dlg.ok_btn.isEnabled()
    dlg._on_accept()
    assert dlg.value == 200
    assert dlg.result() == QDialog.Accepted
    dlg.close()


def test_preselects_current_value(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx", 200)
    assert dlg.column_combo.currentText() == "Сумма"
    assert dlg.value_combo.currentData() == 200
    assert dlg.ok_btn.isEnabled()
    dlg.close()


def test_empty_table(qapp, tmp_path):
    _book(tmp_path, rows=())
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    assert dlg.hint.text() == STRINGS.PICK_EMPTY
    assert not dlg.column_combo.isEnabled()
    assert not dlg.value_combo.isEnabled()
    assert not dlg.ok_btn.isEnabled()
    dlg.close()


def test_missing_file_reports_error(qapp, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )
    dlg = PickerDialog(str(tmp_path), "missing.xlsx")
    assert warnings
    assert dlg.column_combo.count() == 0
    dlg.close()
