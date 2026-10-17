# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for OpenProjectDialog (020)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from stanok.engine.schema import validate_pj
from stanok.gui.open_project_dialog import OpenProjectDialog
from stanok.gui.strings import STRINGS
from stanok.services.storage import ProjectStore


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / ".stanok")


def _bare(folder=None):
    data = {
        "version": "0.0.0",
        "templates": {"t": {"file": "Шаблоны/t.docx", "fields": {}}},
        "data_sources": [],
        "counters": {},
        "filename_template": "p",
    }
    if folder is not None:
        data["folder"] = str(folder)
    return validate_pj(data)


def test_lists_projects_sorted(qapp, tmp_path, store):
    store.save(_bare(str(tmp_path / "f1")), name="zebra")
    store.save(_bare(), name="alpha")
    dlg = OpenProjectDialog(store)
    assert dlg.list.count() == 2
    assert [dlg.list.item(i).data(Qt.UserRole) for i in range(2)] == ["alpha", "zebra"]
    assert dlg.open_btn.isEnabled()
    assert dlg.list.currentRow() == 0
    assert STRINGS.OPEN_NO_FOLDER in dlg.list.item(0).text()
    dlg.close()


def test_empty_disables(qapp, tmp_path, store):
    dlg = OpenProjectDialog(store)
    assert dlg.list.count() == 0
    assert not dlg.open_btn.isEnabled()
    assert not dlg.list.isEnabled()
    dlg.close()


def test_open_selects_config(qapp, tmp_path, store):
    store.save(_bare(), name="only")
    dlg = OpenProjectDialog(store)
    dlg._on_open()
    assert dlg.selected_config == "only"
    dlg.close()


def test_open_without_selection_noop(qapp, tmp_path, store):
    store.save(_bare(), name="only")
    dlg = OpenProjectDialog(store)
    dlg.list.setCurrentRow(-1)
    dlg._on_open()
    assert dlg.selected_config == ""
    dlg.close()


def test_double_click_opens(qapp, tmp_path, store):
    store.save(_bare(), name="only")
    dlg = OpenProjectDialog(store)
    dlg.list.itemDoubleClicked.emit(dlg.list.item(0))
    assert dlg.selected_config == "only"
    dlg.close()
