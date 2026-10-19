# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Variant 2: choose a column, then a numeric value from that column.

The first dropdown lists the table headers. The second lists the distinct
non-negative integers of the selected column; the chosen number is written to
the counter's ``last`` value.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from .strings import STRINGS
from .table_picker import ValuePickerDialog, coerce_number


class PickerDialog(ValuePickerDialog):
    """Column + value picker."""

    def __init__(
        self,
        folder,
        rel: str,
        current: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(folder, rel, current, parent)
        self._build()
        self._fill()

    def _build(self) -> None:
        self.resize(420, 240)
        layout = QVBoxLayout(self)
        source = QLabel(STRINGS.PICK_SOURCE.format(name=self.rel), self)
        source.setWordWrap(True)
        layout.addWidget(source)
        self.hint = QLabel(STRINGS.PICK_COLUMNS_HINT, self)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        form = QFormLayout()
        self.column_combo = QComboBox(self)
        self.column_combo.currentIndexChanged.connect(self._on_column_changed)
        form.addRow(STRINGS.PICK_COLUMN, self.column_combo)
        self.value_combo = QComboBox(self)
        self.value_combo.currentIndexChanged.connect(self._on_value_changed)
        form.addRow(STRINGS.PICK_VALUE, self.value_combo)
        layout.addLayout(form)
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
            self.column_combo.setEnabled(False)
            self.value_combo.setEnabled(False)
            return
        self.column_combo.blockSignals(True)
        for idx, header in enumerate(grid.headers):
            self.column_combo.addItem(header, idx)
        self.column_combo.blockSignals(False)
        self._select_current_column()
        self._on_column_changed()

    def _select_current_column(self) -> None:
        if self.current is None or self.grid is None:
            return
        for idx in range(len(self.grid.headers)):
            for row in self.grid.rows:
                if coerce_number(row[idx]) == self.current:
                    self.column_combo.setCurrentIndex(idx)
                    return

    def _on_column_changed(self) -> None:
        self.value_combo.blockSignals(True)
        self.value_combo.clear()
        column = self.column_combo.currentData()
        seen: set[int] = set()
        if column is not None and self.grid is not None:
            for row in self.grid.rows:
                number = coerce_number(row[column])
                if number is not None and number not in seen:
                    seen.add(number)
                    self.value_combo.addItem(str(number), number)
        self.value_combo.blockSignals(False)
        if self.value_combo.count() == 0:
            self.hint.setText(STRINGS.PICK_NO_VALUES)
            self.ok_btn.setEnabled(False)
            return
        self.hint.setText(STRINGS.PICK_COLUMNS_HINT)
        if self.current is not None:
            idx = self.value_combo.findData(self.current)
            if idx >= 0:
                self.value_combo.setCurrentIndex(idx)
        self._on_value_changed()

    def _on_value_changed(self) -> None:
        self.ok_btn.setEnabled(self.value_combo.currentData() is not None)

    def _on_accept(self) -> None:
        value = self.value_combo.currentData()
        if value is None:
            return
        self.choose(value)
