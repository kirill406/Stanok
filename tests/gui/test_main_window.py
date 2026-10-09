# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for MainWindow + GenerateWorker."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

from stanok.gui.main_window import MainWindow
from stanok.gui.strings import STRINGS
from stanok.gui.worker import GenerateWorker
from stanok.services.generate import GenerateCommand
from stanok.services.storage import ProjectStore
from tests.services.test_generate import make_project


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / ".stanok")


def _await_report(worker, timeout_ms=15000):
    """Run worker thread, pump events until finished/failed/timeout."""
    loop = QEventLoop()
    box = {}
    worker.finished.connect(lambda r: (box.setdefault("report", r), loop.quit()))
    worker.failed.connect(lambda m: (box.setdefault("failed", m), loop.quit()))
    QTimer.singleShot(timeout_ms, loop.quit)
    worker.start()
    loop.exec_()
    worker.wait()
    return box


def test_window_shows_recent(qapp, tmp_path, store):
    store.add_recent(str(tmp_path / "a"), "a")
    store.add_recent(str(tmp_path / "b"), "b")
    win = MainWindow(store=store)
    assert win.windowTitle() == STRINGS.MAIN_TITLE
    assert win.recent_list.count() == 2
    assert win.generate_btn.text() == STRINGS.MAIN_GENERATE
    win.close()


def test_select_project_fills_templates(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    win = MainWindow(store=store)
    win._load_project(str(folder))
    assert win._project_ref == str(folder)
    assert [win.template_combo.itemText(i) for i in range(win.template_combo.count())] == [
        "Договор"
    ]
    assert "data.xlsx" in win.source_label.text()
    win.close()


def test_broken_project_shows_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *a: shown.append(a[-1])
    )
    win = MainWindow(store=store)
    win._load_project("nope")
    assert shown, "error dialog not shown"
    assert win.isEnabled()
    assert win._project_ref is None
    win.close()


def test_generate_without_project_shows_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *a: shown.append(a[-1])
    )
    win = MainWindow(store=store)
    win._on_generate()
    assert shown == [STRINGS.MAIN_NO_PROJECT]
    win.close()


def test_worker_run_to_completion(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    worker = GenerateWorker(GenerateCommand(project_ref=str(folder)), store=store)
    box = _await_report(worker)
    assert "failed" not in box
    assert box["report"].created == 2
    assert all(p.exists() for p in box["report"].output_paths)


def test_worker_execute_direct(qapp, tmp_path, store):
    """Same-thread execution covers worker body (QThread is untraceable)."""
    folder = make_project(tmp_path / "proj")
    worker = GenerateWorker(GenerateCommand(project_ref=str(folder)), store=store)
    got = {}
    worker.finished.connect(lambda r: got.setdefault("report", r))
    worker.failed.connect(lambda m: got.setdefault("failed", m))
    worker._execute()
    assert got["report"].created == 2

    bad = GenerateWorker(GenerateCommand(project_ref="nope"), store=store)
    got2 = {}
    bad.finished.connect(lambda r: got2.setdefault("report", r))
    bad.failed.connect(lambda m: got2.setdefault("failed", m))
    bad._execute()
    assert "failed" in got2 and "report" not in got2


def test_worker_reports_failure(qapp, tmp_path, store):
    worker = GenerateWorker(GenerateCommand(project_ref="nope"), store=store)
    box = _await_report(worker)
    assert "report" not in box
    assert "failed" in box


def test_worker_cancel_after_first(qapp, tmp_path, store):
    folder = make_project(
        tmp_path / "proj", rows=(("А", 1), ("Б", 2), ("В", 3))
    )
    worker = GenerateWorker(GenerateCommand(project_ref=str(folder)), store=store)
    worker.request_cancel()
    box = _await_report(worker)
    assert "failed" not in box
    assert box["report"].created == 1


def test_window_generate_end_to_end(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a: infos.append(a[-1])
    )
    folder = make_project(tmp_path / "proj")
    win = MainWindow(store=store)
    win._load_project(str(folder))
    win._on_generate()
    box = _await_report(win._worker)
    assert "failed" not in box
    assert infos and "создано 2" in infos[0]
    assert win.generate_btn.isEnabled()
    assert win.recent_list.count() == 1
    win.close()
