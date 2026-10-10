# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Integration: bootstrap, window 1→2→3 chain, CLI regression (offscreen)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from docx import Document as DocxDocument
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

from stanok.app import create_gui, main
from stanok.gui.fields_dialog import FieldsDialog
from stanok.gui.main_window import MainWindow
from stanok.gui.project_dialog import ProjectDialog
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


def _add_constant(folder):
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["templates"]["Договор"]["fields"]["Город"] = {
        "source": "constant",
        "value": "Москва",
    }
    pj_path.write_text(json.dumps(data, ensure_ascii=False))


def _await_dialog_run(dlg, timeout_ms=15000):
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(lambda: dlg._progress_dialog is None and loop.quit())
    poll.start(50)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec_()
    poll.stop()


def test_create_gui_no_exec(qapp, tmp_path, store):
    qt_app, window = create_gui(store)
    assert qt_app is not None
    assert window.windowTitle() == STRINGS.MAIN_TITLE
    window.close()


def test_window_chain_to_docx(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)

    win = MainWindow(store=store)
    assert win.recent_list.count() == 0

    dlg2 = ProjectDialog(str(folder), store=store)
    assert dlg2.table.rowCount() == 1

    dlg3 = FieldsDialog(str(folder), "Договор", store=store)
    dlg3._editors["Город"].setText("Казань")
    dlg3._on_save()
    assert not dlg3._dirty
    dlg3.close()

    dlg2._on_run_template("Договор")
    _await_dialog_run(dlg2)
    out = list((folder / "Результат").glob("*.docx"))
    assert len(out) == 2
    text = "\n".join(p.text for p in DocxDocument(str(out[0])).paragraphs)
    assert "{{" not in text
    saved = json.loads((store.home_dir / "proj.stanok").read_text())
    assert saved["templates"]["Договор"]["fields"]["Город"]["value"] == "Казань"
    assert saved["counters"]["num"]["last"] == 2
    dlg2.close()
    win.close()


def test_cli_generates_to_mocked_home(tmp_path, store, monkeypatch, capsys):
    monkeypatch.setattr(
        "stanok.services.generate.ProjectStore", lambda *a, **k: store
    )
    folder = make_project(tmp_path / "cli")
    assert main([str(folder)]) == 0
    out, _ = capsys.readouterr()
    assert "создано 2" in out
    assert (folder / "Результат" / "Договор_Иван_1.docx").exists()
    assert (store.home_dir / "cli.stanok").exists()


def test_cli_broken_project_returns_1(tmp_path, store, monkeypatch):
    monkeypatch.setattr(
        "stanok.services.generate.ProjectStore", lambda *a, **k: store
    )
    assert main([str(tmp_path / "gone")]) == 1


def test_cli_source_alias(tmp_path, store, monkeypatch, capsys):
    from tests.services.test_generate import _add_source

    monkeypatch.setattr(
        "stanok.services.generate.ProjectStore", lambda *a, **k: store
    )
    folder = make_project(tmp_path / "cli")
    second = _add_source(folder)
    assert main([str(folder), "--source", second]) == 0
    out, _ = capsys.readouterr()
    assert "создано 1" in out
