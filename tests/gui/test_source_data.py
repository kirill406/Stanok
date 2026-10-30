# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for SourceData (027): rows, headers and missing-source recovery."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil

import pytest
from openpyxl import Workbook
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

import stanok.gui.source_data as sd
from stanok.gui.source_data import SourceData
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


@pytest.fixture
def parent(qapp):
    widget = QWidget()
    yield widget
    widget.close()


@pytest.fixture
def messages(monkeypatch):
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(QMessageBox, "information", lambda *a: shown.append(a[-1]))
    return shown


def _xlsx(path, headers=("ФИО", "Сумма"), rows=(("Иван", 100),)):
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    wb.save(path)


def _sources(folder, store, parent):
    pj, config_path = store.resolve_project(str(folder))
    return SourceData(pj, folder, store, config_path.stem, parent), pj


def test_source_data_reads_headers_and_rows(qapp, tmp_path, store, parent):
    folder = make_project(tmp_path / "proj")
    sources, _ = _sources(folder, store, parent)

    assert sources.headers("Данные/data.xlsx") == ["ФИО", "Сумма"]
    assert sources.rows("Данные/data.xlsx")[1]["ФИО"] == "Иван"


def test_source_data_caches_rows_per_source(qapp, tmp_path, store, parent):
    folder = make_project(tmp_path / "proj")
    sources, _ = _sources(folder, store, parent)
    first = sources.rows("Данные/data.xlsx")

    assert sources.rows("Данные/data.xlsx") is first


def test_source_data_missing_source_pick_copies_into_project(
    qapp, tmp_path, store, parent, monkeypatch
):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    other = tmp_path / "elsewhere"
    other.mkdir()
    _xlsx(other / "data.xlsx")
    monkeypatch.setattr(sd.SourceData, "_ask_recovery", lambda self, name: "pick")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(other))
    sources, _ = _sources(folder, store, parent)

    assert sources.headers("Данные/data.xlsx") == ["ФИО", "Сумма"]
    assert (folder / "Данные" / "data.xlsx").is_file()


def test_source_data_missing_source_pick_rebinds_relative(
    qapp, tmp_path, store, parent, monkeypatch
):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    _xlsx(folder / "data.xlsx")
    monkeypatch.setattr(sd.SourceData, "_ask_recovery", lambda self, name: "pick")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder))
    sources, _ = _sources(folder, store, parent)

    assert sources.headers("Данные/data.xlsx") == ["ФИО", "Сумма"]
    pj, _ = store.resolve_project(str(folder))
    assert pj.data_sources[0].file == "data.xlsx"
    assert pj.counters["data"].table == "data.xlsx"


def test_source_data_missing_source_create_makes_folders(
    qapp, tmp_path, store, parent, monkeypatch, messages
):
    folder = make_project(tmp_path / "proj")
    shutil.rmtree(folder / "Данные")
    monkeypatch.setattr(sd.SourceData, "_ask_recovery", lambda self, name: "create")
    sources, _ = _sources(folder, store, parent)

    sources.rows("Данные/data.xlsx")

    assert (folder / "Данные").is_dir()
    assert (folder / "Шаблоны").is_dir()
    assert messages and messages[0] == STRINGS.FLD_SRC_DIR_MADE.format(folder=folder)


def test_source_data_cancelled_recovery_asks_once(qapp, tmp_path, store, parent, monkeypatch, messages):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    asked = {"n": 0}

    def ask(self, name):
        asked["n"] += 1
        return None

    monkeypatch.setattr(sd.SourceData, "_ask_recovery", ask)
    sources, _ = _sources(folder, store, parent)

    sources.rows("Данные/data.xlsx")
    sources.rows("Данные/data.xlsx")

    assert asked["n"] == 1
    assert messages == [STRINGS.FLD_SRC_MISSING.format(name="data.xlsx")]


def test_source_data_remembered_folder_restores_without_asking(
    qapp, tmp_path, store, parent, monkeypatch, messages
):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    donor = make_project(tmp_path / "donor")
    monkeypatch.setattr(sd.SourceData, "_ask_recovery", lambda self, name: None)
    sources, _ = _sources(folder, store, parent)
    sources._recovery_dir = donor / "Данные"

    path = sources._resolve_path("Данные/data.xlsx")

    assert path is not None and path.is_file()


def test_source_data_restore_not_found_returns_none(qapp, tmp_path, store, parent):
    folder = make_project(tmp_path / "proj")
    sources, _ = _sources(folder, store, parent)
    empty = tmp_path / "empty"
    empty.mkdir()

    assert sources._restore("Данные/data.xlsx", "data.xlsx", empty) is None


def test_source_data_rebind_save_error_is_logged_not_raised(
    qapp, tmp_path, store, parent, monkeypatch
):
    folder = make_project(tmp_path / "proj")
    sources, _ = _sources(folder, store, parent)

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(store, "save", boom)
    sources._rebind("Данные/data.xlsx", "x.xlsx")


def test_source_data_unreadable_table_warns_once(qapp, tmp_path, store, parent, messages):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").write_bytes(b"not an xlsx")
    sources, _ = _sources(folder, store, parent)

    sources.rows("Данные/data.xlsx")
    sources.rows("Данные/data.xlsx")

    assert len(messages) == 1
