# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for Window 2 (ProjectDialog)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox, QSpinBox

from stanok.gui.project_dialog import ProjectDialog
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


def _await_run(dlg, timeout_ms=15000):
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(lambda: dlg._progress_dialog is None and loop.quit())
    poll.start(50)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec_()
    poll.stop()


def test_open_lists_templates(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = ProjectDialog(str(folder), store=store)
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 0).text() == "Договор"
    assert dlg.table.cellWidget(0, 1).value() == 0
    assert "proj" in dlg.windowTitle()
    dlg.close()


def test_run_template_with_limit(qapp, tmp_path, store, monkeypatch):
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    folder = make_project(
        tmp_path / "proj", rows=(("А", 1), ("Б", 2), ("В", 3))
    )
    dlg = ProjectDialog(str(folder), store=store)
    dlg.table.cellWidget(0, 1).setValue(1)
    dlg._on_run_template("Договор")
    _await_run(dlg)
    assert infos and "создано 1" in infos[0]
    assert len(list((folder / "Результат").glob("*.docx"))) == 1
    dlg.close()


def test_cell_click_opens_real_dialog(qapp, tmp_path, store, monkeypatch):
    exec_calls = []
    monkeypatch.setattr(
        "stanok.gui.project_dialog.FieldsDialog",
        lambda ref, name, st, parent: type(
            "Fake", (), {"exec_": lambda self: exec_calls.append((ref, name))}
        )(),
    )
    folder = make_project(tmp_path / "proj")
    dlg = ProjectDialog(str(folder), store=store)
    dlg._on_cell_clicked(0, 0)
    assert exec_calls == [(str(folder), "Договор")]
    dlg.close()


def test_run_row_errors_shown(qapp, tmp_path, store, monkeypatch):
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
    dlg = ProjectDialog(str(folder), store=store)
    dlg._on_run_template("Договор")
    _await_run(dlg)
    assert infos and "boom" in infos[0]
    dlg.close()


def test_double_run_ignored(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    folder = make_project(tmp_path / "proj")
    dlg = ProjectDialog(str(folder), store=store)
    dlg._on_run_template("Договор")
    first_worker = dlg._worker
    dlg._on_run_template("Договор")
    assert dlg._worker is first_worker
    _await_run(dlg)
    dlg.close()


def test_broken_template_shows_error(qapp, tmp_path, store, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    folder = make_project(tmp_path / "proj")
    (folder / "Шаблоны" / "tpl.docx").unlink()
    dlg = ProjectDialog(str(folder), store=store)
    dlg._on_run_template("Договор")
    _await_run(dlg)
    assert shown
    assert dlg.isEnabled()
    dlg.close()


def test_open_missing_project_raises(qapp, tmp_path, store):
    with pytest.raises(StorageError):
        ProjectDialog("nope", store=store)


def test_source_combo_runs_selected_only(qapp, tmp_path, store, monkeypatch):
    from tests.services.test_generate import _add_source

    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    folder = make_project(tmp_path / "proj")
    second = _add_source(folder)
    dlg = ProjectDialog(str(folder), store=store)
    assert dlg.source_combo.count() == 3
    assert dlg.source_combo.itemText(0) == STRINGS.PROJ_SOURCE_ALL
    dlg.source_combo.setCurrentIndex(2)
    assert dlg.source_combo.currentData() == second
    dlg._on_run_template("Договор")
    _await_run(dlg)
    assert infos and "создано 1" in infos[0]
    dlg.close()


def _extra_docx(path, text="Акт {{Номер}}"):
    from docx import Document as DocxDocument

    doc = DocxDocument()
    doc.add_paragraph(text)
    doc.save(path)
    return path


def test_add_template_reloads_table(qapp, tmp_path, store, monkeypatch):
    from PyQt5.QtWidgets import QFileDialog

    folder = make_project(tmp_path / "proj")
    extra = _extra_docx(tmp_path / "extra.docx")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(extra), "")
    )
    dlg = ProjectDialog(str(folder), store=store)
    assert dlg.table.rowCount() == 1
    dlg._on_add_template()
    assert dlg.table.rowCount() == 2
    assert dlg.table.item(1, 0).text() == "extra"
    dlg.close()


def test_remove_template_with_confirm(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    extra = _extra_docx(tmp_path / "extra.docx")
    store.add_template(folder, extra)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    dlg = ProjectDialog(str(folder), store=store)
    assert dlg.table.rowCount() == 2
    dlg._on_remove_template("Договор")
    assert dlg.table.rowCount() == 1
    dlg._on_remove_template("extra")
    assert infos == [STRINGS.TPL_LAST_KEPT]
    assert dlg.table.rowCount() == 1
    dlg.close()


def test_delete_project_closes_dialog(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    store.add_recent(str(folder), "proj")
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: QMessageBox.Yes)
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: infos.append(a[-1]))
    dlg = ProjectDialog(str(folder), store=store)
    dlg._on_delete_project()
    assert dlg.result()
    assert not (store.home_dir / "proj.stanok").exists()
    assert infos and "удалён" in infos[0]
    dlg.close()


def test_manage_slots_guards_and_errors(qapp, tmp_path, store, monkeypatch):
    from PyQt5.QtWidgets import QFileDialog

    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.No
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: ("", "")
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    dlg = ProjectDialog(str(folder), store=store)

    dlg._running = True

    dlg._running = True
    dlg._on_add_template()
    dlg._on_remove_template("Договор")
    dlg._on_delete_project()
    assert dlg.table.rowCount() == 1
    dlg._running = False

    dlg._on_add_template()
    assert dlg.table.rowCount() == 1

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(tmp_path / "gone.docx"), "")
    )
    dlg._on_add_template()
    assert warnings and dlg.table.rowCount() == 1

    extra = _extra_docx(tmp_path / "extra2.docx")
    store.add_template(folder, extra)
    dlg._reload_templates()
    assert dlg.table.rowCount() == 2
    dlg._on_remove_template("extra2")
    assert dlg.table.rowCount() == 2

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.Yes
    )
    dlg._on_remove_template("extra2")
    assert dlg.table.rowCount() == 1

    def boom(*a, **k):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(store, "remove_template", boom)
    extra = _extra_docx(tmp_path / "extra.docx")
    store.add_template(folder, extra)
    dlg._reload_templates()
    assert dlg.table.rowCount() == 2
    dlg._on_remove_template("extra")
    assert len(warnings) == 2
    dlg.close()


def test_delete_project_errors(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: QMessageBox.No)
    dlg = ProjectDialog(str(folder), store=store)
    dlg._on_delete_project()
    assert not dlg.result()
    assert (store.home_dir / "proj.stanok").exists()

    monkeypatch.setattr(QMessageBox, "exec_", lambda self: QMessageBox.Yes)

    def boom(*a, **k):
        raise RuntimeError("locked")

    monkeypatch.setattr(store, "delete_project", boom)
    dlg._on_delete_project()
    assert warnings
    assert (store.home_dir / "proj.stanok").exists()
    dlg.close()
