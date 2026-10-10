# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for the settings dialog + app logging (018)."""

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from stanok.gui.settings_dialog import SettingsDialog
from stanok.gui.strings import STRINGS
from stanok.services.storage import ProjectStore


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / ".stanok")


def test_settings_roundtrip(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(
        "PyQt5.QtGui.QDesktopServices.openUrl", lambda *a, **k: True
    )
    dlg = SettingsDialog(store, None)
    assert dlg.windowTitle() == STRINGS.SET_TITLE
    assert dlg.level_combo.currentText() == "INFO"
    dlg.level_combo.setCurrentText("WARNING")
    dlg._on_save()
    assert dlg.result()
    assert store.get_setting("log_level") == "WARNING"
    assert logging.getLogger().level == logging.WARNING
    logging.getLogger().setLevel(logging.INFO)
    dlg2 = SettingsDialog(store, None)
    assert dlg2.level_combo.currentText() == "WARNING"
    dlg.close()
    dlg2.close()


def test_settings_open_folder(qapp, store, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "PyQt5.QtGui.QDesktopServices.openUrl",
        lambda url: calls.append(url.toLocalFile()),
    )
    dlg = SettingsDialog(store, None)
    dlg._on_open_folder()
    from pathlib import Path

    assert [Path(p) for p in calls] == [store.home_dir]
    dlg.close()


def test_store_settings_roundtrip(store):
    assert store.get_setting("missing", "dflt") == "dflt"
    store.set_setting("k", 42)
    assert store.get_setting("k") == 42


def test_store_settings_missing_and_broken(store):
    (store.home_dir / "settings.json").unlink()
    assert store.get_setting("x", "d") == "d"
    (store.home_dir / "settings.json").write_text("{oops")
    assert store.get_setting("x", "d") == "d"
