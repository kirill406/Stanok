# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small reusable widgets shared by the GUI windows."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    """Single-line label that shortens long text instead of widening the layout."""

    def __init__(
        self,
        text: str = "",
        parent=None,
        mode: Qt.TextElideMode = Qt.ElideRight,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setTextFormat(Qt.PlainText)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_text()

    def _update_text(self) -> None:
        width = max(0, self.width())
        elided = self.fontMetrics().elidedText(self._full_text, self._mode, width)
        super().setText(elided)
