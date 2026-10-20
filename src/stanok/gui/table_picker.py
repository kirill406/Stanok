# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared support for picking a numeric value from a data table (Window 3).

The common part owns: reading the table the same way the generator does,
validating the chosen cell, and the eye icon. The concrete selection UI lives
in ``table_picker_impl`` (one variant per feature branch).
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QIcon, QPainter, QPalette, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from ..tables.excel import ExcelReader, TableReadError
from .strings import STRINGS

logger = logging.getLogger(__name__)

PICKER_MODULE = "stanok.gui.table_picker_impl"


@dataclass
class TableGrid:
    headers: list[str]
    rows: list[list[Any]]


def load_grid(folder: str | Path, rel: str) -> TableGrid:
    """Read a data table as headers plus data rows (same as the generator)."""
    records = ExcelReader().read(Path(folder) / rel)
    headers = list(records[0]) if records else []
    return TableGrid(
        headers=headers,
        rows=[[record.get(header) for header in headers] for record in records],
    )


def coerce_number(value: Any) -> int | None:
    """Return a non-negative integer for a cell value, else ``None``."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if value.is_integer() and value >= 0:
            return int(value)
        return None
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def eye_icon(size: int = 16) -> QIcon:
    """Draw a small eye in the current text color (no external assets)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    color = QApplication.palette().color(QPalette.WindowText)
    pen = QPen(color)
    pen.setWidthF(1.4)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QRectF(1.5, 4.0, size - 3.0, size - 8.0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawEllipse(QPointF(size / 2.0, size / 2.0), 2.0, 2.0)
    painter.end()
    return QIcon(pixmap)


def picker_available() -> bool:
    """True when a variant module provides ``PickerDialog``."""
    try:
        return find_spec(PICKER_MODULE) is not None
    except (ImportError, ValueError):
        return False


class ValuePickerDialog(QDialog):
    """Base dialog: load the table, validate the number, expose it as ``value``."""

    def __init__(
        self,
        folder: str | Path,
        rel: str,
        current: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.folder = Path(folder)
        self.rel = rel
        self.current = current
        self.value: int | None = None
        self.grid: TableGrid | None = None
        self.setWindowTitle(STRINGS.FLD_PICK_TITLE)
        self.setModal(True)

    def load(self) -> TableGrid | None:
        try:
            self.grid = load_grid(self.folder, self.rel)
        except TableReadError as e:
            logger.warning(f"read picker table {self.rel}: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return None
        return self.grid

    def choose(self, cell: Any) -> None:
        number = coerce_number(cell)
        if number is None:
            QMessageBox.warning(
                self, STRINGS.MAIN_ERROR_TITLE, STRINGS.FLD_PICK_NOT_NUMBER
            )
            return
        self.value = number
        self.accept()


def open_picker(
    parent,
    folder: str | Path,
    rel: str,
    current: int | None = None,
) -> int | None:
    """Run the variant picker; return the chosen number or ``None``."""
    if not picker_available():
        return None
    module = importlib.import_module(PICKER_MODULE)
    dialog = module.PickerDialog(Path(folder), rel, current, parent)
    if dialog.exec_() == QDialog.Accepted and dialog.value is not None:
        return dialog.value
    return None
