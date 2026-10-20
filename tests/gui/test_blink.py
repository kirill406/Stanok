# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for the green onboarding pulse."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QComboBox, QPushButton

from stanok.gui.blink import GreenBlink


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_green_blink_start_and_stop_restore_style(qapp):
    button = QPushButton("x")
    button.setStyleSheet("color: red;")
    blink = GreenBlink(button, duration_ms=80)
    blink.start()
    QTest.qWait(50)
    assert blink.running
    assert "rgba(76, 175, 80" in button.styleSheet()
    blink.stop()
    assert not blink.running
    assert button.styleSheet() == "color: red;"


def test_combo_blink_styles_only_combo_surface(qapp):
    combo = QComboBox()
    combo.addItem("x")
    blink = GreenBlink(combo, duration_ms=80)
    blink.start()
    QTest.qWait(30)
    style = combo.styleSheet()
    assert "QComboBox { background-color: rgba(76, 175, 80" in style
    assert "QComboBox QAbstractItemView" not in style
    blink.stop()
    assert combo.styleSheet() == ""
