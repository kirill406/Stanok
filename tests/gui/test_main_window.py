# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for Window 1 (MainWindow) + GenerateWorker."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
)

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


def _make_home_project(store, tmp_path, name="proj"):
    from tests.services.test_storage import _src_files

    xlsx, tpl = _src_files(tmp_path, f"src_{name}")
    store.init_project(tmp_path / name, name, [xlsx], [tpl])
    return tmp_path / name


def test_recent_row_shows_default_template_and_limit(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    row = win.recent_list.itemWidget(win.recent_list.item(0))
    labels = [w.text() for w in row.findChildren(QLabel)]
    assert STRINGS.MAIN_TPL.format(name="Договор") in labels
    spin = row.findChild(QSpinBox)
    assert spin is not None and spin.value() == 0
    buttons = [w for w in row.findChildren(QPushButton) if w.text() == STRINGS.MAIN_GENERATE]
    assert buttons and row.layout().indexOf(spin) < row.layout().indexOf(buttons[0])
    win.close()


def test_recent_row_limit_edit_saves_pj(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    row = win.recent_list.itemWidget(win.recent_list.item(0))
    row.findChild(QSpinBox).setValue(5)
    assert store.load("proj").templates["Договор"].limit == 5
    win.close()


def test_recent_row_limit_save_error_shows(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    monkeypatch.setattr(
        store,
        "set_template_limit",
        lambda *a: (_ for _ in ()).throw(RuntimeError("locked")),
    )
    row = win.recent_list.itemWidget(win.recent_list.item(0))
    row.findChild(QSpinBox).setValue(4)
    assert shown and "locked" in shown[0]
    win.close()


def test_recent_row_broken_project_shows_placeholder(qapp, tmp_path, store):
    win = MainWindow(store=store)
    store.add_recent(str(tmp_path / "gone"), "gone")
    win.refresh_recent()
    row = win.recent_list.itemWidget(win.recent_list.item(0))
    labels = [w.text() for w in row.findChildren(QLabel)]
    assert STRINGS.MAIN_TPL_UNAVAILABLE in labels
    assert row.findChild(QSpinBox) is None
    win.close()


def test_browse_opens_selected(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.main_window as mw
    import stanok.gui.open_project_dialog as opd

    _make_home_project(store, tmp_path)
    opened = {}

    class FakeOpen:
        def __init__(self, *a, **k):
            self.selected_config = "proj"

        def exec_(self):
            return True

    monkeypatch.setattr(opd, "OpenProjectDialog", FakeOpen)
    monkeypatch.setattr(
        mw,
        "ProjectDialog",
        lambda ref, st, parent, **k: type(
            "F", (), {"exec_": lambda self: opened.update(ref=ref, **k)}
        )(),
    )
    win = MainWindow(store=store)
    win._on_browse()
    assert opened["ref"] == "proj"
    assert any(r.config == "proj" for r in store.get_recent())
    win.close()


def test_browse_cancelled_noop(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.open_project_dialog as opd

    class FakeOpen:
        def __init__(self, *a, **k):
            self.selected_config = ""

        def exec_(self):
            return False

    monkeypatch.setattr(opd, "OpenProjectDialog", FakeOpen)
    win = MainWindow(store=store)
    win._on_browse()
    assert win.recent_list.count() == 0
    win.close()


def test_browse_accepted_without_selection(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.open_project_dialog as opd

    class FakeOpen:
        def __init__(self, *a, **k):
            self.selected_config = ""

        def exec_(self):
            return True

    monkeypatch.setattr(opd, "OpenProjectDialog", FakeOpen)
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
        lambda ref, st, parent, **k: type(
            "Fake", (), {"exec_": lambda self: exec_calls.append(ref)}
        )(),
    )
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    win = MainWindow(store=store)
    win._on_row_clicked(win.recent_list.item(0))
    assert exec_calls == ["proj"]
    win.close()


def test_settings_opens_dialog(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.settings_dialog as sd

    opened = []

    class FakeDialog:
        def __init__(self, *a, **k):
            opened.append(a)

        def exec_(self):
            return False

    monkeypatch.setattr(sd, "SettingsDialog", FakeDialog)
    win = MainWindow(store=store)
    win._on_settings()
    assert opened and opened[0][0] is store
    win.close()


def test_create_dialog_builds_project(qapp, tmp_path, store, monkeypatch):
    from tests.services.test_storage import _src_files

    from stanok.gui.create_dialog import CreateDialog

    xlsx, tpl = _src_files(tmp_path)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    monkeypatch.setattr("stanok.gui.create_dialog.ask_yes_no", lambda *a, **k: True)
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
    assert (tmp_path / "proj" / "nov" / "Данные" / "data.xlsx").is_file()
    assert (tmp_path / "proj" / "nov" / "Результат").is_dir()
    assert any(r.config == "nov" for r in store.get_recent())
    dlg.close()


def test_create_dialog_name_taken_disabled(qapp, tmp_path, store, monkeypatch):
    from tests.services.test_storage import _src_files

    from stanok.gui.create_dialog import CreateDialog

    xlsx, tpl = _src_files(tmp_path)
    store.init_project(tmp_path / "proj", "dup", [xlsx], [tpl])
    dlg = CreateDialog(store, str(tmp_path), None)
    dlg.folder_edit.setText(str(tmp_path / "other"))
    dlg.xlsx_list.addItem(str(xlsx))
    dlg.docx_list.addItem(str(tpl))
    dlg.name_edit.setText("dup")
    dlg._update_create_enabled()
    assert not dlg.create_btn.isEnabled()
    assert STRINGS.CRT_NAME_TAKEN.format(name="dup") == dlg.path_label.text()
    dlg.close()


def test_create_dialog_bad_dir_disabled(qapp, tmp_path, store):
    from tests.services.test_storage import _src_files

    from stanok.gui.create_dialog import CreateDialog

    xlsx, tpl = _src_files(tmp_path)
    dlg = CreateDialog(store, str(tmp_path), None)
    dlg.xlsx_list.addItem(str(xlsx))
    dlg.docx_list.addItem(str(tpl))
    dlg.name_edit.setText("p")
    dlg.folder_edit.setText(str(tmp_path / "Данные"))
    dlg._update_create_enabled()
    assert not dlg.create_btn.isEnabled()
    assert "Данные" in dlg.path_label.text()
    dlg.close()


def test_create_dialog_preview_path(qapp, tmp_path, store):
    from stanok.gui.create_dialog import CreateDialog

    dlg = CreateDialog(store, str(tmp_path), None)
    dlg.name_edit.setText("p")
    dlg.folder_edit.setText(str(tmp_path / "box"))
    dlg._update_create_enabled()
    text = dlg.path_label.text()
    base = tmp_path / "box" / "p"
    assert str(base) in text
    assert str(base / "Данные") in text
    assert str(base / "Шаблоны") in text
    assert str(base / "Результат") in text
    dlg.close()


def test_create_dialog_mkdir_accepted(qapp, tmp_path, store, monkeypatch):
    from tests.services.test_storage import _src_files

    from stanok.gui.create_dialog import CreateDialog

    xlsx, tpl = _src_files(tmp_path)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    monkeypatch.setattr("stanok.gui.create_dialog.ask_yes_no", lambda *a, **k: True)
    dlg = CreateDialog(store, str(tmp_path), None)
    dlg.name_edit.setText("nov")
    dlg.folder_edit.setText(str(tmp_path / "base"))
    dlg.xlsx_list.addItem(str(xlsx))
    dlg.docx_list.addItem(str(tpl))
    dlg._on_create()
    assert dlg.result()
    assert (tmp_path / "base" / "nov" / "Данные" / "data.xlsx").is_file()
    dlg.close()


def test_create_dialog_mkdir_declined(qapp, tmp_path, store, monkeypatch):
    from tests.services.test_storage import _src_files

    from stanok.gui.create_dialog import CreateDialog

    xlsx, tpl = _src_files(tmp_path)
    monkeypatch.setattr("stanok.gui.create_dialog.ask_yes_no", lambda *a, **k: False)
    dlg = CreateDialog(store, str(tmp_path), None)
    dlg.name_edit.setText("nov")
    dlg.folder_edit.setText(str(tmp_path / "missing"))
    dlg.xlsx_list.addItem(str(xlsx))
    dlg.docx_list.addItem(str(tpl))
    dlg._on_create()
    assert not dlg.result()
    assert not (tmp_path / "missing").exists()
    dlg.close()


def test_create_dialog_shows_error(qapp, tmp_path, store, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )

    from stanok.gui.create_dialog import CreateDialog

    monkeypatch.setattr("stanok.gui.create_dialog.ask_yes_no", lambda *a, **k: True)
    dlg = CreateDialog(store, str(tmp_path), None)
    dlg.name_edit.setText("  ")
    dlg.folder_edit.setText(str(tmp_path / "proj"))
    dlg._on_create()
    assert warnings
    assert not dlg.result()
    dlg.close()


def test_create_dialog_settings_mode(qapp, tmp_path, store):
    from stanok.gui.create_dialog import CreateDialog

    folder = make_project(tmp_path / "proj")
    dlg = CreateDialog(store, "", None, edit_ref=str(folder))
    assert dlg.windowTitle() == STRINGS.CRT_EDIT_TITLE
    assert dlg.name_edit.isReadOnly()
    assert dlg.name_edit.text() == "proj"
    assert dlg.default_combo.currentData() == "Договор"
    text = dlg.path_label.text()
    assert str(folder) in text
    assert str(folder / "Данные") in text
    assert str(folder / "Шаблоны") in text
    assert str(folder / "Результат") in text
    new_folder = tmp_path / "moved"
    new_folder.mkdir()
    dlg.folder_edit.setText(str(new_folder))
    dlg._on_create()
    assert dlg.result()
    pj = store.load("proj")
    assert pj.folder == str(new_folder.resolve())
    dlg.close()


def test_create_dialog_create_mode_has_no_orphan_widgets(qapp, tmp_path, store):
    from stanok.gui.create_dialog import CreateDialog

    dlg = CreateDialog(store, str(tmp_path), None)
    assert dlg.findChildren(QComboBox) == []
    dlg.close()


def test_create_dialog_settings_mode_has_no_orphan_widgets(qapp, tmp_path, store):
    from stanok.gui.create_dialog import CreateDialog

    folder = make_project(tmp_path / "proj")
    dlg = CreateDialog(store, "", None, edit_ref=str(folder))
    assert dlg.findChildren(QListWidget) == []
    dlg.close()


def test_create_dialog_settings_error_warns(qapp, tmp_path, store, monkeypatch):
    from stanok.gui.create_dialog import CreateDialog

    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = CreateDialog(store, "", None, edit_ref=str(folder))

    def boom(*a, **k):
        raise RuntimeError("locked")

    monkeypatch.setattr(store, "set_project_folder", boom)
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


def test_main_create_opens_window2(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.create_dialog as cd
    import stanok.gui.main_window as mw

    opened = {}

    class FakeDialog:
        project_name = "nov"

        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return True

    monkeypatch.setattr(cd, "CreateDialog", FakeDialog)
    monkeypatch.setattr(
        mw,
        "ProjectDialog",
        lambda ref, st, parent, **k: type(
            "F", (), {"exec_": lambda self: opened.update(ref=ref, **k)}
        )(),
    )
    win = MainWindow(store=store)
    win._on_create()
    assert opened["ref"] == "nov"
    assert opened["highlight_new"] is True
    win.close()


def test_open_missing_folder_relocate(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.main_window as mw
    from stanok.engine.schema import validate_pj
    from stanok.services.storage import StorageError

    calls = {"n": 0}
    new = tmp_path / "newfolder"
    new.mkdir()

    def fake_pd(ref, st, parent, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise StorageError("resolve", ["project folder not found: x"])
        return type("F", (), {"exec_": lambda self: None})()

    monkeypatch.setattr(mw, "ProjectDialog", fake_pd)
    monkeypatch.setattr(mw, "ask_yes_no", lambda *a, **k: True)
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(new)
    )
    store.save(validate_pj(_bare_pj()), name="proj")
    win = MainWindow(store=store)
    win._open_project_dialog("proj")
    assert calls["n"] == 2
    assert store.load("proj").folder == str(new.resolve())
    win.close()


def test_open_missing_folder_declined(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.main_window as mw
    from stanok.services.storage import StorageError

    def fake_pd(ref, st, parent, **k):
        raise StorageError("resolve", ["project folder not found: x"])

    monkeypatch.setattr(mw, "ProjectDialog", fake_pd)
    monkeypatch.setattr(mw, "ask_yes_no", lambda *a, **k: False)
    win = MainWindow(store=store)
    win._open_project_dialog("x")
    win.close()


def test_open_missing_folder_pick_cancelled(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.main_window as mw
    from stanok.services.storage import StorageError

    def fake_pd(ref, st, parent, **k):
        raise StorageError("resolve", ["project folder not found: x"])

    monkeypatch.setattr(mw, "ProjectDialog", fake_pd)
    monkeypatch.setattr(mw, "ask_yes_no", lambda *a, **k: True)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    win = MainWindow(store=store)
    win._open_project_dialog("x")
    win.close()


def test_open_missing_folder_relocate_error(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.main_window as mw
    from stanok.services.storage import StorageError

    shown = []
    new = tmp_path / "newfolder"
    new.mkdir()

    def fake_pd(ref, st, parent, **k):
        raise StorageError("resolve", ["project folder not found: x"])

    monkeypatch.setattr(mw, "ProjectDialog", fake_pd)
    monkeypatch.setattr(mw, "ask_yes_no", lambda *a, **k: True)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(new)
    )
    monkeypatch.setattr(
        store,
        "set_project_folder",
        lambda *a: (_ for _ in ()).throw(RuntimeError("weird")),
    )
    win = MainWindow(store=store)
    win._open_project_dialog("x")
    assert shown and "weird" in shown[0]
    win.close()


def test_open_project_dialog_storage_error(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.main_window as mw
    from stanok.services.storage import StorageError

    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(
        mw,
        "ProjectDialog",
        lambda *a, **k: (_ for _ in ()).throw(StorageError("load", ["badness"])),
    )
    win = MainWindow(store=store)
    win._open_project_dialog("x")
    assert shown and "badness" in shown[0]
    win.close()


def test_open_project_dialog_unexpected_error(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.main_window as mw

    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(
        mw, "ProjectDialog", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("weird"))
    )
    win = MainWindow(store=store)
    win._open_project_dialog("x")
    assert shown and "weird" in shown[0]
    win.close()


def _bare_pj():
    return {
        "version": "0.0.0",
        "templates": {"t": {"file": "Шаблоны/t.docx", "fields": {}}},
        "data_sources": [],
        "counters": {},
        "filename_template": "proj",
    }


def test_remove_recent_row(qapp, tmp_path, store):
    win = MainWindow(store=store)
    store.add_recent(str(tmp_path / "a"), "a")
    store.add_recent(str(tmp_path / "b"), "b")
    win.refresh_recent()
    assert win.recent_list.count() == 2
    win._on_remove_recent(str(tmp_path / "a"), "a")
    assert win.recent_list.count() == 1
    assert [r.config for r in store.get_recent()] == ["b"]
    win.close()
