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


def test_browse_cancelled_noop(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    win = MainWindow(store=store)
    win._on_browse()
    assert win.recent_list.count() == 0
    win.close()


def test_open_broken_dialog_shows_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    win = MainWindow(store=store)
    win._open_project_dialog("nope")
    assert shown
    win.close()


def test_generate_one_failure_shows_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    win = MainWindow(store=store)
    win._on_generate_one(str(tmp_path / "gone"))
    _await_queue(win)
    assert shown
    win.close()


def test_generate_one_row_errors_shown(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    import stanok.services.generate as gen

    real_render = gen.render
    calls = {"n": 0}

    def flaky(fj, template_path):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real_render(fj, template_path)

    monkeypatch.setattr(gen, "render", flaky)
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    win._on_generate_one(str(folder))
    _await_queue(win)
    assert infos and "boom" in infos[0]
    win.close()


def test_row_click_opens_real_dialog(qapp, tmp_path, store, monkeypatch):
    exec_calls = []
    monkeypatch.setattr(
        "stanok.gui.main_window.ProjectDialog",
        lambda ref, st, parent: type(
            "Fake", (), {"exec_": lambda self: exec_calls.append(ref)}
        )(),
    )
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    win._on_row_clicked(win.recent_list.item(0))
    assert exec_calls == [str(folder)]
    win.close()


def test_settings_stub(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    win = MainWindow(store=store)
    win._on_settings()
    assert infos == [STRINGS.MAIN_SETTINGS_STUB]
    win.close()


def test_create_dialog_builds_project(qapp, tmp_path, store, monkeypatch):
    from tests.services.test_storage import _src_files

    from stanok.gui.create_dialog import CreateDialog

    xlsx, tpl = _src_files(tmp_path)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    dlg = CreateDialog(store, str(tmp_path), None)
    assert not dlg.create_btn.isEnabled()
    dlg.name_edit.setText("nov")
    assert not dlg.create_btn.isEnabled()
    dlg.folder_edit.setText(str(tmp_path / "proj"))
    dlg.xlsx_list.addItem(str(xlsx))
    dlg.docx_list.addItem(str(tpl))
    dlg._update_create_enabled()
    assert dlg.create_btn.isEnabled()
    dlg._on_create()
    assert dlg.result()
    assert (tmp_path / "proj" / "Данные" / "data.xlsx").is_file()
    assert any(r.config == "nov" for r in store.get_recent())
    dlg.close()


def test_create_dialog_shows_error(qapp, tmp_path, store, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )

    from stanok.gui.create_dialog import CreateDialog

    dlg = CreateDialog(store, str(tmp_path), None)
    dlg.name_edit.setText("  ")
    dlg.folder_edit.setText(str(tmp_path / "proj"))
    dlg._on_create()
    assert warnings
    assert not dlg.result()
    dlg.close()


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


def test_create_dialog_file_slots(qapp, tmp_path, store, monkeypatch):
    from PyQt5.QtWidgets import QFileDialog

    from stanok.gui.create_dialog import CreateDialog

    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames",
        lambda *a, **k: (["/tmp/a.xlsx", "/tmp/a.xlsx", "/tmp/b.xlsx"], ""),
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *a, **k: "/tmp/proj",
    )
    dlg = CreateDialog(store, "", None)
    dlg._on_add_files(dlg.xlsx_list, "Excel (*.xlsx)")
    assert dlg.xlsx_list.count() == 2
    dlg.xlsx_list.setCurrentRow(0)
    dlg._on_remove_selected(dlg.xlsx_list)
    assert dlg.xlsx_list.count() == 1
    dlg._on_browse_folder()
    assert dlg.folder_edit.text() == "/tmp/proj"
    dlg.close()


def test_main_create_opens_dialog(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.create_dialog as cd

    opened = {}

    class FakeDialog:
        def __init__(self, *a, **k):
            opened["args"] = a

        def exec_(self):
            return True

    monkeypatch.setattr(cd, "CreateDialog", FakeDialog)
    store.add_recent(str(tmp_path), "old")
    win = MainWindow(store=store)
    refreshed = []
    monkeypatch.setattr(win, "refresh_recent", lambda: refreshed.append(True))
    win._on_create()
    assert opened and refreshed
    win.close()


def test_browse_empty_folder_friendly_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(empty)
    )
    win = MainWindow(store=store)
    win._on_browse()
    assert shown and STRINGS.MAIN_NO_PROJECT in shown[0]
    assert win.recent_list.count() == 0
    win.close()


def test_browse_broken_config_raw_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    folder = make_project(tmp_path / "proj")
    (folder / "project.stanok").write_text("{broken")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder)
    )
    win = MainWindow(store=store)
    win._on_browse()
    assert shown and STRINGS.MAIN_NO_PROJECT not in shown[0]
    win.close()


def test_browse_unexpected_error_shown(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
    )

    def boom(ref):
        raise RuntimeError("weird")

    monkeypatch.setattr(store, "resolve_project", boom)
    win = MainWindow(store=store)
    win._on_browse()
    assert shown and "weird" in shown[0]
    win.close()


def test_browse_storage_error_raw(qapp, tmp_path, store, monkeypatch):
    from stanok.services.storage import StorageError

    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
    )

    def boom(ref):
        raise StorageError("load", ["badness"])

    monkeypatch.setattr(store, "resolve_project", boom)
    win = MainWindow(store=store)
    win._on_browse()
    assert shown and "badness" in shown[0]
    win.close()
