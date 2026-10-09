# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for Window 1 (MainWindow) + GenerateWorker."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

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


def _await_queue(win, timeout_ms=20000):
    """Pump events until window-1 queue dialog closes."""
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(lambda: win._progress_dialog is None and loop.quit())
    poll.start(50)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec_()
    poll.stop()


def test_window_shows_recent(qapp, tmp_path, store):
    store.add_recent(str(tmp_path / "a"), "a")
    store.add_recent(str(tmp_path / "b"), "b")
    win = MainWindow(store=store)
    assert win.windowTitle() == STRINGS.MAIN_TITLE
    assert win.recent_list.count() == 2
    assert win.generate_all_btn.text() == STRINGS.MAIN_GENERATE_ALL
    assert win.settings_btn.text() == STRINGS.MAIN_SETTINGS
    win.close()


def test_browse_adds_project(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder)
    )
    win = MainWindow(store=store)
    win._on_browse()
    assert win.recent_list.count() == 1
    assert (store.home_dir / "proj.stanok").exists()
    win.close()


def test_browse_broken_shows_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path / "nope")
    )
    win = MainWindow(store=store)
    win._on_browse()
    assert shown
    win.close()


def test_row_click_opens_window2_hook(qapp, tmp_path, store, monkeypatch):
    opened = []
    monkeypatch.setattr(
        MainWindow, "_open_project_dialog", lambda self, ref: opened.append(ref)
    )
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    win._on_row_clicked(win.recent_list.item(0))
    assert opened == [str(folder)]
    win.close()


def test_row_click_stub_without_009(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    win._on_row_clicked(win.recent_list.item(0))
    assert infos == [STRINGS.MAIN_PROJECT_TBD]
    win.close()


def test_settings_stub(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    win = MainWindow(store=store)
    win._on_settings()
    assert infos == [STRINGS.MAIN_SETTINGS_STUB]
    win.close()


def test_generate_one_end_to_end(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    folder = make_project(tmp_path / "proj", rows=(("Иван", 100),))
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    win._on_generate_one(str(folder))
    _await_queue(win)
    assert infos and "создано 1" in infos[0]
    assert win.generate_all_btn.isEnabled()
    assert (folder / "Результат" / "Договор_Иван_1.docx").exists()
    win.close()


def test_generate_all_two_projects(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    for name in ("p1", "p2"):
        folder = make_project(tmp_path / name, rows=(("Иван", 100),))
        store.add_recent(str(folder), name)
    win = MainWindow(store=store)
    win._on_generate_all()
    _await_queue(win)
    assert infos and "p1" in infos[0] and "p2" in infos[0]
    win.close()


def test_generate_all_broken_continues(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    good = make_project(tmp_path / "good", rows=(("Иван", 100),))
    store.add_recent(str(good), "good")
    store.add_recent(str(tmp_path / "gone"), "gone")
    win = MainWindow(store=store)
    win._on_generate_all()
    _await_queue(win)
    assert infos and "Ошибка" in infos[0]
    assert (good / "Результат" / "Договор_Иван_1.docx").exists()
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
