# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for OpenProjectDialog (020, 022)."""

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

from stanok.engine.schema import validate_pj
from stanok.gui.project_check_dialog import ProjectCheckDialog
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


def _write_config(path, folder=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_bare(folder).model_dump(mode="json")), encoding="utf-8"
    )


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


def test_pick_folder_button_exists(qapp, store):
    dlg = OpenProjectDialog(store)
    assert dlg.pick_btn.text() == STRINGS.OPEN_PICK
    dlg.close()


def test_pick_folder_cancel_noop(qapp, store, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    dlg = OpenProjectDialog(store)
    dlg._on_pick_folder()
    assert dlg.list.count() == 0
    assert dlg.selected_config == ""
    dlg.close()


def test_pick_folder_imports_and_refreshes(qapp, tmp_path, store, monkeypatch):
    ext = tmp_path / "ext"
    proj = tmp_path / "proj"
    proj.mkdir()
    _write_config(ext / "imp.stanok", proj)
    messages = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a: messages.append(a[-1])
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(ext)
    )
    dlg = OpenProjectDialog(store)

    dlg._on_pick_folder()

    assert messages == [STRINGS.OPEN_IMPORTED.format(count=1)]
    assert dlg.list.count() == 1
    assert dlg.list.currentItem().data(Qt.UserRole) == "imp"
    assert (store.home_dir / "imp.stanok").is_file()
    dlg.close()


def test_pick_folder_unknown_warns(qapp, tmp_path, store, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(empty)
    )
    dlg = OpenProjectDialog(store)

    dlg._on_pick_folder()

    assert warnings == [STRINGS.OPEN_FAILED]
    dlg.close()


def test_pick_folder_opens_check_and_accepts(qapp, tmp_path, store, monkeypatch):
    root = tmp_path / "Мой проект"
    (root / "Данные").mkdir(parents=True)
    (root / "Шаблоны").mkdir()
    (root / "Результат").mkdir()
    (root / "Данные" / "data.xlsx").write_bytes(b"x")
    (root / "Шаблоны" / "tpl.docx").write_bytes(b"x")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(root)
    )
    seen = {}

    def fake_exec(self):
        seen["folder"] = self._folder
        seen["name"] = self.name_edit.text()
        seen["editable"] = not self.name_edit.isReadOnly()
        self.project_name = self.name_edit.text()
        return 1

    monkeypatch.setattr(ProjectCheckDialog, "exec_", fake_exec)
    dlg = OpenProjectDialog(store)

    dlg._on_pick_folder()

    assert seen == {"folder": root.resolve(), "name": root.name, "editable": True}
    assert dlg.created_config == root.name
    assert dlg.selected_config == root.name
    dlg.close()


