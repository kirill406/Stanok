# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for variant 1: full-table grid picker."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from openpyxl import Workbook
from PyQt5.QtCore import Qt
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


def test_picker_lists_whole_table(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    assert dlg.table.columnCount() == 3
    assert dlg.table.rowCount() == 2
    assert [
        dlg.table.horizontalHeaderItem(c).text()
        for c in range(dlg.table.columnCount())
    ] == [STRINGS.PICK_ROW, "ФИО", "Сумма"]
    assert dlg.table.item(0, 0).text() == "0"
    assert dlg.table.item(1, 0).text() == "1"
    assert dlg.table.item(1, 1).text() == "Петр"
    assert dlg.table.item(1, 2).text() == "200"
    dlg.close()


def test_picker_chooses_numeric_cell(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    dlg._on_cell_clicked(1, 2)
    assert dlg.ok_btn.isEnabled()
    assert dlg.value_label.text() == STRINGS.PICK_WILL_WRITE.format(value=200)
    dlg._on_accept()
    assert dlg.value == 200
    assert dlg.result() == QDialog.Accepted
    dlg.close()


def test_picker_double_click_accepts(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    dlg._on_double_click(0, 2)
    assert dlg.value == 100
    assert dlg.result() == QDialog.Accepted
    dlg.close()


def test_picker_rejects_text_cell(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    dlg._on_cell_clicked(0, 1)
    assert not dlg.ok_btn.isEnabled()
    assert dlg.hint.text() == STRINGS.FLD_PICK_NOT_NUMBER
    assert dlg._cell is None
    assert dlg.value_label.text() == STRINGS.PICK_WILL_WRITE.format(
        value=STRINGS.PICK_NO_VALUE
    )
    dlg._on_accept()
    assert dlg.value is None
    dlg.close()


def test_picker_row_index_is_not_selectable(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    index_item = dlg.table.item(0, 0)
    assert index_item.flags() == Qt.NoItemFlags
    dlg._on_cell_clicked(0, 0)
    assert dlg._cell is None
    assert not dlg.ok_btn.isEnabled()
    dlg.close()


def test_picker_does_not_preselect_current_value(qapp, tmp_path):
    _book(tmp_path)
    dlg = PickerDialog(str(tmp_path), "data.xlsx", 200)
    assert dlg._cell is None
    assert not dlg.ok_btn.isEnabled()
    assert dlg.value_label.text() == STRINGS.PICK_WILL_WRITE.format(
        value=STRINGS.PICK_NO_VALUE
    )
    dlg.close()


def test_picker_empty_table(qapp, tmp_path):
    _book(tmp_path, rows=())
    dlg = PickerDialog(str(tmp_path), "data.xlsx")
    assert dlg.table.rowCount() == 0
    assert dlg.hint.text() == STRINGS.PICK_EMPTY
    assert not dlg.ok_btn.isEnabled()
    dlg.close()


def test_picker_missing_file_reports_error(qapp, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )
    dlg = PickerDialog(str(tmp_path), "missing.xlsx")
    assert warnings
    assert dlg.table.rowCount() == 0
    dlg.close()
