# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for importing configs and detecting project layout (022)."""

import json

import pytest

from stanok.engine.schema import validate_pj
from stanok.services.import_export import detect_project_layout
from stanok.services.storage import ProjectStore


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / ".stanok")


def _pj(folder=None):
    data = {
        "version": "0.0.0",
        "templates": {"t": {"file": "Шаблоны/t.docx", "fields": {}}},
        "data_sources": [],
        "counters": {},
        "filename_template": "p",
    }
    if folder is not None:
        data["folder"] = str(folder)
    return validate_pj(data)


def _write_config(path, folder=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_pj(folder).model_dump(mode="json")), encoding="utf-8"
    )


def test_import_moves_configs_and_adds_recent(store, tmp_path):
    ext = tmp_path / "ext"
    proj1 = tmp_path / "proj1"
    proj2 = tmp_path / "proj2"
    proj1.mkdir()
    proj2.mkdir()
    _write_config(ext / "nested" / "one.stanok", proj1)
    _write_config(ext / "two.stanok", proj2)

    report = store.import_configs(ext)

    assert report.found == 2
    assert sorted(report.imported) == ["one", "two"]
    assert report.failed == []
    assert report.missing_folder == []
    assert not (ext / "nested" / "one.stanok").exists()
    assert not (ext / "two.stanok").exists()
    assert (store.home_dir / "one.stanok").is_file()
    assert (store.home_dir / "two.stanok").is_file()
    recent = store.get_recent()
    assert {item.config for item in recent} == {"one", "two"}
    assert {item.folder for item in recent} == {
        str(proj1.resolve()),
        str(proj2.resolve()),
    }


def test_import_keeps_existing_config_and_uses_unique_name(store, tmp_path):
    store.save(_pj(), name="dup")
    proj = tmp_path / "proj"
    proj.mkdir()
    _write_config(tmp_path / "ext" / "dup.stanok", proj)

    report = store.import_configs(tmp_path / "ext")

    assert report.imported == ["dup (1)"]
    assert store.load("dup").folder is None
    assert store.load("dup (1)").folder == str(proj.resolve())


def test_import_infers_folder_from_project_structure(store, tmp_path):
    ext = tmp_path / "ext" / "proj"
    (ext / "Данные").mkdir(parents=True)
    (ext / "Шаблоны").mkdir()
    (ext / "Результат").mkdir()
    _write_config(ext / "proj.stanok")

    report = store.import_configs(tmp_path / "ext")

    assert report.imported == ["proj"]
    assert report.missing_folder == []
    assert store.load("proj").folder == str(ext.resolve())
    assert store.get_recent()[0].folder == str(ext.resolve())


def test_import_reports_unreadable_config(store, tmp_path):
    ext = tmp_path / "ext"
    ext.mkdir()
    (ext / "bad.stanok").write_text("{broken", encoding="utf-8")

    report = store.import_configs(ext)

    assert report.found == 1
    assert report.failed == ["bad.stanok"]
    assert report.imported == []
    assert not (store.home_dir / "bad.stanok").exists()
    assert store.get_recent() == []


def test_import_missing_folder_imported_without_recent(store, tmp_path):
    ext = tmp_path / "ext"
    _write_config(ext / "lost.stanok", tmp_path / "gone")

    report = store.import_configs(ext)

    assert report.imported == ["lost"]
    assert report.missing_folder == ["lost"]
    assert (store.home_dir / "lost.stanok").is_file()
    assert store.get_recent() == []


def test_import_skips_configs_already_in_home(store):
    store.save(_pj(), name="already")

    report = store.import_configs(store.home_dir)

    assert report.found == 0
    assert report.imported == []
    assert (store.home_dir / "already.stanok").is_file()


def test_import_nonexistent_folder_is_empty(store, tmp_path):
    report = store.import_configs(tmp_path / "missing")

    assert report.found == 0
    assert report.imported == []
    assert report.failed == []


def test_detect_layout_finds_sources(tmp_path):
    root = tmp_path / "proj"
    (root / "Данные").mkdir(parents=True)
    (root / "Шаблоны").mkdir()
    (root / "Результат").mkdir()
    (root / "Данные" / "b.xlsx").write_bytes(b"x")
    (root / "Данные" / "a.xlsx").write_bytes(b"x")
    (root / "Шаблоны" / "t.docx").write_bytes(b"x")
    (root / "Данные" / "note.txt").write_text("x", encoding="utf-8")

    layout = detect_project_layout(root)

    assert layout is not None
    assert layout.folder == root.resolve()
    assert [p.name for p in layout.xlsx] == ["a.xlsx", "b.xlsx"]
    assert [p.name for p in layout.docx] == ["t.docx"]


def test_detect_layout_requires_all_three_folders(tmp_path):
    root = tmp_path / "proj"
    (root / "Данные").mkdir(parents=True)
    (root / "Шаблоны").mkdir()

    assert detect_project_layout(root) is None


def test_detect_layout_nonexistent(tmp_path):
    assert detect_project_layout(tmp_path / "missing") is None
