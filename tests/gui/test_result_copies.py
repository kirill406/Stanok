# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project settings: three sections and result copy folders (025)."""

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton

from stanok.gui.create_dialog import CreateDialog
from stanok.gui.strings import STRINGS
from stanok.services.storage import ProjectStore
from tests.services.test_generate import make_project


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / ".stanok")


def _dialog(store, folder):
    return CreateDialog(store, "", None, edit_ref=str(folder))


def _add_button(dlg):
    return next(
        b for b in dlg.findChildren(QPushButton) if b.text() == "+"
    )


def test_result_section_has_plus_with_tooltip(qapp, tmp_path, store):
    dlg = _dialog(store, make_project(tmp_path / "proj"))
    btn = _add_button(dlg)
    assert btn.toolTip() == STRINGS.CRT_RESULT_COPY_TIP
    dlg.close()


def test_add_result_copy_folder_shows_and_saves(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    copy = tmp_path / "copy"
    copy.mkdir()
    monkeypatch.setattr(
        "stanok.gui.create_dialog.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(copy),
    )
    dlg = _dialog(store, folder)
    dlg._on_add_result_dir()
    assert dlg._result_dirs == [str(copy.resolve())]
    assert dlg._copies_layout.count() == 1
    dlg._on_create()
    assert dlg.result()
    assert store.load("proj").result_dirs == [str(copy.resolve())]
    dlg.close()


def test_add_result_copy_refuses_own_result_folder(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    info = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: info.append(a[-1]))
    monkeypatch.setattr(
        "stanok.gui.create_dialog.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(folder / "Результат"),
    )
    dlg = _dialog(store, folder)
    dlg._on_add_result_dir()
    assert dlg._result_dirs == []
    assert info == [STRINGS.CRT_RESULT_COPY_OWN]
    dlg.close()


def test_add_result_copy_refuses_duplicate(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    copy = tmp_path / "copy"
    copy.mkdir()
    info = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: info.append(a[-1]))
    monkeypatch.setattr(
        "stanok.gui.create_dialog.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(copy),
    )
    dlg = _dialog(store, folder)
    dlg._on_add_result_dir()
    dlg._on_add_result_dir()
    assert dlg._result_dirs == [str(copy.resolve())]
    assert info == [STRINGS.CRT_RESULT_COPY_DUP]
    dlg.close()


def test_remove_result_copy_folder(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    copy = tmp_path / "copy"
    dlg = _dialog(store, folder)
    dlg._result_dirs = [str(copy)]
    dlg._refresh_copies()
    dlg._on_remove_result_dir(str(copy))
    assert dlg._result_dirs == []
    assert dlg._copies_layout.count() == 1  # the "not configured" hint
    dlg.close()


def test_sections_show_paths_under_project_folder(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = _dialog(store, folder)
    assert dlg._section_paths[STRINGS.DATA_DIR].text() == str(folder / "Данные")
    assert dlg._section_paths[STRINGS.TPL_DIR].text() == str(folder / "Шаблоны")
    assert dlg._section_paths[STRINGS.GEN_RESULT_DIR].text() == str(folder / "Результат")
    dlg.close()
