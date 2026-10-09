# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for Window 3 (FieldsDialog)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox

from stanok.gui.fields_dialog import FieldsDialog
from stanok.gui.strings import STRINGS
from stanok.services.storage import ProjectStore, StorageError
from tests.services.test_generate import make_project


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / ".stanok")


def _add_constant(folder):
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["templates"]["Договор"]["fields"]["Город"] = {
        "source": "constant",
        "value": "Москва",
    }
    pj_path.write_text(json.dumps(data, ensure_ascii=False))


def _saved_value(store, field="Город"):
    raw = json.loads((store.home_dir / "proj.stanok").read_text())
    return raw["templates"]["Договор"]["fields"][field]["value"]


def test_open_shows_fields(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg.table.rowCount() == 4
    names = [dlg.table.item(r, 0).text() for r in range(4)]
    assert names == ["ФИО", "Сумма", "Номер", "Город"]
    # Only constant is editable
    assert isinstance(dlg.table.cellWidget(3, 2), QLineEdit)
    assert not (dlg.table.item(0, 2).flags() & Qt.ItemIsEditable)
    # Previews
    assert "Иван" in dlg.table.item(0, 2).text()
    assert "last=0" in dlg.table.item(2, 2).text()
    dlg.close()


def test_edit_save_persists(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._editors["Город"].setText("Казань")
    assert dlg._dirty
    dlg._on_save()
    assert not dlg._dirty
    assert _saved_value(store) == "Казань"
    dlg.close()


def test_close_clean_no_question(qapp, tmp_path, store, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("question must not appear")

    monkeypatch.setattr(QMessageBox, "question", boom)
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg.reject()
    assert dlg.result() == QDialog.Rejected


def test_close_dirty_discard(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.Discard
    )
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._editors["Город"].setText("Казань")
    dlg.reject()
    assert dlg.result() == QDialog.Rejected
    assert _saved_value(store) == "Москва"


def test_close_dirty_save(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Save)
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._editors["Город"].setText("Казань")
    dlg.reject()
    assert dlg.result() == QDialog.Accepted
    assert _saved_value(store) == "Казань"


def test_close_dirty_cancel_stays(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Cancel)
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._editors["Город"].setText("Казань")
    dlg.reject()
    assert dlg.result() == 0
    assert _saved_value(store) == "Москва"
    dlg.close()


def test_open_missing_project_raises(qapp, tmp_path, store):
    with pytest.raises(StorageError):
        FieldsDialog("nope", "Договор", store=store)
