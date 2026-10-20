# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Smooth green background pulse for onboarding hints on window 2."""

from __future__ import annotations

from PyQt5.QtCore import QAbstractAnimation, QEasingCurve, QVariantAnimation
from PyQt5.QtWidgets import QWidget

GREEN_RGB = "76, 175, 80"


class GreenBlink:
    """Pulse a widget's background green until stopped."""

    def __init__(self, widget: QWidget, duration_ms: int = 1600) -> None:
        self._widget = widget
        self._base_style = widget.styleSheet()
        self._anim = QVariantAnimation(widget)
        self._anim.setStartValue(0.0)
        self._anim.setKeyValueAt(0.5, 0.55)
        self._anim.setEndValue(0.0)
        self._anim.setDuration(duration_ms)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.valueChanged.connect(self._apply)

    @property
    def running(self) -> bool:
        return self._anim.state() == QAbstractAnimation.Running

    def start(self) -> None:
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()
        self._widget.setStyleSheet(self._base_style)

    def _apply(self, alpha) -> None:
        percent = max(0, min(100, round(float(alpha) * 100)))
        self._widget.setStyleSheet(
            f"{self._base_style}\n"
            f"background-color: rgba({GREEN_RGB}, {percent}%);"
        )
