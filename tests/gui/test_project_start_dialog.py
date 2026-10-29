# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Start window of project creation: three ways in (024), headless."""

import pytest
from PyQt5.QtWidgets import QApplication, QFileDialog

import stanok.gui.project_start_dialog as psd
from stanok.services.storage import ProjectStore


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "home")


class _Form:
    """Stand-in for _ProjectForm: accepted, fixed values."""

    last = None

    def __init__(self, title, base_hint, sources, parent=None):
        _Form.last = self
        self.sources = sources
        self.name = "новый"
        self.base = self._base
        self.source = sources[0] if sources else ""

    def exec_(self):
        return 1


def _record_check(monkeypatch):
    seen = {}

    def fake_run(self, folder, name, editable):
        seen.update(folder=folder, name=name, editable=editable)
        self.project_name = name
        self.accept()

    monkeypatch.setattr(psd.ProjectStartDialog, "_run_check", fake_run)
    return seen


def test_minimal_creates_skeleton_and_runs_check(qapp, store, tmp_path, monkeypatch):
    seen = _record_check(monkeypatch)
    _Form._base = str(tmp_path)
    monkeypatch.setattr(psd, "_ProjectForm", _Form)
    dlg = psd.ProjectStartDialog(store, str(tmp_path))
    dlg._on_minimal()
    assert seen == {"folder": tmp_path / "новый", "name": "новый", "editable": False}
    assert (tmp_path / "новый" / "Шаблоны").is_dir()
    assert not store.config_exists("новый")
    dlg.close()


def test_minimal_taken_name_shows_error_and_creates_nothing(
    qapp, store, tmp_path, monkeypatch
):
    seen = _record_check(monkeypatch)
    (store.home_dir / "новый.stanok").write_text("{}", encoding="utf-8")
    _Form._base = str(tmp_path)
    monkeypatch.setattr(psd, "_ProjectForm", _Form)
    warned = []
    monkeypatch.setattr(
        psd.QMessageBox, "warning", lambda *a, **k: warned.append(a[-1])
    )
    dlg = psd.ProjectStartDialog(store, str(tmp_path))
    dlg._on_minimal()
    assert seen == {}
    assert warned and "уже существует" in warned[0]
    assert not (tmp_path / "новый").exists()
    dlg.close()


def test_pick_existing_config_opens_directly(qapp, store, tmp_path, monkeypatch):
    seen = _record_check(monkeypatch)
    folder = tmp_path / "есть"
    folder.mkdir()
    (store.home_dir / "есть.stanok").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder)
    )
    dlg = psd.ProjectStartDialog(store, str(tmp_path))
    dlg._on_pick()
    assert seen == {}
    assert dlg.project_name == "есть"
    dlg.close()


def test_pick_missing_subfolders_asks_and_creates(qapp, store, tmp_path, monkeypatch):
    seen = _record_check(monkeypatch)
    folder = tmp_path / "готовая"
    folder.mkdir()
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder)
    )
    monkeypatch.setattr(psd, "ask_yes_no", lambda *a, **k: True)
    dlg = psd.ProjectStartDialog(store, str(tmp_path))
    dlg._on_pick()
    assert (folder / "Данные").is_dir()
    assert (folder / "Шаблоны").is_dir()
    assert seen == {"folder": folder, "name": "готовая", "editable": True}
    dlg.close()


def test_pick_declined_subfolders_stays_open(qapp, store, tmp_path, monkeypatch):
    seen = _record_check(monkeypatch)
    folder = tmp_path / "отказ"
    folder.mkdir()
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder)
    )
    monkeypatch.setattr(psd, "ask_yes_no", lambda *a, **k: False)
    dlg = psd.ProjectStartDialog(store, str(tmp_path))
    dlg._on_pick()
    assert not (folder / "Данные").exists()
    assert seen == {"folder": folder, "name": "отказ", "editable": True}
    dlg.close()


def test_clone_without_sources_informs(qapp, store, tmp_path, monkeypatch):
    info = []
    monkeypatch.setattr(
        psd.QMessageBox, "information", lambda *a, **k: info.append(a[-1])
    )
    dlg = psd.ProjectStartDialog(store, str(tmp_path))
    dlg._on_clone()
    assert info
    dlg.close()
