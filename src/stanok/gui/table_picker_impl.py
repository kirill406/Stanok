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
from .table_picker import TableGrid, ValuePickerDialog


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
        self.value_label = QLabel(
            STRINGS.PICK_WILL_WRITE.format(value=STRINGS.PICK_NO_VALUE), self
        )
        layout.addWidget(self.value_label)
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
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
            index_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            index_item.setToolTip(STRINGS.PICK_ROW_TIP)
            self.table.setItem(row, 0, index_item)
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setData(Qt.UserRole, value)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()

    def _clear_choice(self) -> None:
        self._cell = None
        self.ok_btn.setEnabled(False)
        self.value_label.setText(
            STRINGS.PICK_WILL_WRITE.format(value=STRINGS.PICK_NO_VALUE)
        )

    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._clear_choice()
            return
        self._cell = rows[0].row()
        self.ok_btn.setEnabled(True)
        self.value_label.setText(
            STRINGS.PICK_WILL_WRITE.format(value=self._cell)
        )
        self.hint.setText(STRINGS.PICK_TABLE_HINT)

    def _on_double_click(self, row: int, col: int) -> None:
        self._cell = row
        self._on_accept()

    def _on_accept(self) -> None:
        if self._cell is None:
            return
        self.choose(self._cell)
