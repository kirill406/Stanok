# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Variant 3: choose a row (with a preview), then a number from that row.

Useful when rows have several numeric columns: the first dropdown shows the
0-based data row index plus a short preview, the second lists the distinct
non-negative integers of that row.
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

_PREVIEW_LIMIT = 80


class PickerDialog(ValuePickerDialog):
    """Row + value picker."""

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
        self.resize(520, 240)
        layout = QVBoxLayout(self)
        source = QLabel(STRINGS.PICK_SOURCE.format(name=self.rel), self)
        source.setWordWrap(True)
        layout.addWidget(source)
        self.hint = QLabel(STRINGS.PICK_ROWS_HINT, self)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        form = QFormLayout()
        self.row_combo = QComboBox(self)
        self.row_combo.currentIndexChanged.connect(self._on_row_changed)
        form.addRow(STRINGS.PICK_ROW, self.row_combo)
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
            self.row_combo.setEnabled(False)
            self.value_combo.setEnabled(False)
            return
        self.row_combo.blockSignals(True)
        for index, values in enumerate(grid.rows):
            self.row_combo.addItem(
                STRINGS.PICK_ROW_PREVIEW.format(
                    index=index, preview=self._preview(values)
                ),
                index,
            )
        self.row_combo.blockSignals(False)
        self._select_current_row()
        self._on_row_changed()

    @staticmethod
    def _preview(values) -> str:
        parts = [str(value) for value in values if value is not None]
        text = " | ".join(parts)
        if len(text) > _PREVIEW_LIMIT:
            return text[:_PREVIEW_LIMIT] + "…"
        return text

    def _select_current_row(self) -> None:
        if self.current is None or self.grid is None:
            return
        for index, values in enumerate(self.grid.rows):
            if any(coerce_number(value) == self.current for value in values):
                self.row_combo.setCurrentIndex(index)
                return

    def _on_row_changed(self) -> None:
        self.value_combo.blockSignals(True)
        self.value_combo.clear()
        row = self.row_combo.currentData()
        seen: set[int] = set()
        if row is not None and self.grid is not None:
            for value in self.grid.rows[row]:
                number = coerce_number(value)
                if number is not None and number not in seen:
                    seen.add(number)
                    self.value_combo.addItem(str(number), number)
        self.value_combo.blockSignals(False)
        if self.value_combo.count() == 0:
            self.hint.setText(STRINGS.PICK_NO_VALUES)
            self.ok_btn.setEnabled(False)
            return
        self.hint.setText(STRINGS.PICK_ROWS_HINT)
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
