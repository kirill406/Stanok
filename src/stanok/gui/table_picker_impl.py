# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Variant 1: show the whole table and pick a cell value.

The dialog lists every data row (0-based index, same as ``start_row``) and
every column; the user clicks a numeric cell and confirms (or double-clicks).
"""

from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .strings import STRINGS
from .table_picker import TableGrid, ValuePickerDialog, coerce_number


class PickerDialog(ValuePickerDialog):
    """Full-table grid picker."""

    def __init__(
        self,
        folder,
        rel: str,
        current: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(folder, rel, current, parent)
        self._cell: Any = None
        self._build()
        self._fill()

    def _build(self) -> None:
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        self.hint = QLabel(STRINGS.PICK_TABLE_HINT, self)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.ok_btn = buttons.button(QDialogButtonBox.Ok)
        self.ok_btn.setText(STRINGS.PICK_CHOOSE)
        self.ok_btn.setEnabled(False)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill(self) -> None:
        grid = self.load()
        if grid is None:
            return
        if not grid.headers or not grid.rows:
            self.hint.setText(STRINGS.PICK_EMPTY)
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return
        self._fill_grid(grid)

    def _fill_grid(self, grid: TableGrid) -> None:
        self.table.setColumnCount(len(grid.headers) + 1)
        self.table.setHorizontalHeaderLabels(
            [STRINGS.PICK_ROW] + list(grid.headers)
        )
        self.table.setRowCount(len(grid.rows))
        for row, values in enumerate(grid.rows):
            index_item = QTableWidgetItem(str(row))
            index_item.setFlags(Qt.ItemIsEnabled)
            index_item.setToolTip(STRINGS.PICK_ROW_TIP)
            self.table.setItem(row, 0, index_item)
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setData(Qt.UserRole, value)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self._select_current(grid)

    def _select_current(self, grid: TableGrid) -> None:
        if self.current is None:
            return
        for row, values in enumerate(grid.rows):
            for col, value in enumerate(values, start=1):
                if coerce_number(value) == self.current:
                    self.table.setCurrentCell(row, col)
                    self._cell = value
                    self.ok_btn.setEnabled(True)
                    return

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col == 0:
            self._cell = None
            self.ok_btn.setEnabled(False)
            self.table.clearSelection()
            self.hint.setText(STRINGS.PICK_TABLE_HINT)
            return
        item = self.table.item(row, col)
        self._cell = item.data(Qt.UserRole) if item is not None else None
        valid = coerce_number(self._cell) is not None
        self.ok_btn.setEnabled(valid)
        self.hint.setText(
            STRINGS.PICK_TABLE_HINT if valid else STRINGS.FLD_PICK_NOT_NUMBER
        )

    def _on_double_click(self, row: int, col: int) -> None:
        if col == 0:
            return
        self._on_cell_clicked(row, col)
        if self.ok_btn.isEnabled():
            self._on_accept()

    def _on_accept(self) -> None:
        if self._cell is None or coerce_number(self._cell) is None:
            return
        self.choose(self._cell)
