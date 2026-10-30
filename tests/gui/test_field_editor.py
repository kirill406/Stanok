# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for the field editor (027): one field and its counter."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox

import stanok.gui.field_editor as fe
from stanok.gui.fields_dialog import FieldsDialog
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
def warnings(monkeypatch):
    """Capture QMessageBox warnings and information boxes instead of blocking."""
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: shown.append(a[-1]))
    monkeypatch.setattr(QMessageBox, "information", lambda *a: shown.append(a[-1]))
    return shown


def _editor(tmp_path, store, field, shared=None, project_counter=None):
    """A window 3 and a field editor for `field`; the project is migrated to Home.

    `project_counter` adds a project counter under a name that is also shared,
    which can only be written by hand (the store refuses the clash).
    """
    folder = make_project(tmp_path / "proj")
    store.migrate_from_project(folder)
    for name, cdef in (shared or {}).items():
        store.add_global_counter(name, cdef.get("fmt", "1"), cdef.get("pos", 0))
    if project_counter:
        path = store.home_dir / "proj.stanok"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["counters"][project_counter] = {"pos": 0, "format": "1"}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    ed = fe.FieldEditDialog(dlg._pj, "Договор", field, dlg._sources, store, dlg)
    return dlg, ed


def _pj_field(ed, name):
    return ed._pj.templates["Договор"].fields[name]


def test_field_editor_table_field_shows_counter_and_column(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "ФИО")

    assert ed.type_combo.currentData() == "table"
    assert ed._counter_combo.currentData() == "data"
    assert ed._column_combo.currentText() == "ФИО"
    dlg.close()
    ed.close()


def test_field_editor_ok_writes_field_and_counter(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "ФИО")
    ed._column_combo.setCurrentText("Сумма")
    ed._blk_fmt.setCurrentIndex(ed._blk_fmt.findData("01"))
    ed._blk_pos.setText("0")

    ed._on_ok()

    field = _pj_field(ed, "ФИО")
    assert (field.source.value, field.value, field.counter_name) == ("table", "Сумма", "data")
    counter = ed._pj.counters["data"]
    assert (counter.pos, counter.format) == (0, "01")
    assert ed.changed is True
    dlg.close()
    ed.close()


def test_field_editor_cancel_keeps_field(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "ФИО")
    before = _pj_field(ed, "ФИО").model_dump()
    ed._column_combo.setCurrentText("Сумма")

    ed.reject()

    assert _pj_field(ed, "ФИО").model_dump() == before
    assert ed.changed is False
    dlg.close()
    ed.close()


def test_field_editor_table_without_column_blocks_ok(qapp, tmp_path, store, warnings):
    dlg, ed = _editor(tmp_path, store, "ФИО")
    ed._column_combo.setCurrentIndex(-1)

    ed._on_ok()

    assert warnings and STRINGS.FLD_EMPTY_VALUE.format(name="ФИО") in warnings
    assert ed.result() == 0
    dlg.close()
    ed.close()


def test_field_editor_bad_position_blocks_ok(qapp, tmp_path, store, warnings):
    dlg, ed = _editor(tmp_path, store, "ФИО")
    ed._blk_pos.setText("abc")

    ed._on_ok()

    assert warnings and STRINGS.FLD_CNT_POS_BAD.format(name="data") in warnings
    dlg.close()
    ed.close()


def test_field_editor_negative_position_blocks_ok(qapp, tmp_path, store, warnings):
    dlg, ed = _editor(tmp_path, store, "ФИО")
    ed._blk_pos.setText("-1")

    ed._on_ok()

    assert warnings and STRINGS.FLD_CNT_POS_BAD.format(name="data") in warnings
    dlg.close()
    ed.close()


def test_field_editor_table_preview_follows_position(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "ФИО")
    assert ed._preview.text() == "Иван"  # sequential, pos 1 -> first data row

    ed._blk_pos.setText("2")

    assert ed._preview.text() == "Петр"
    dlg.close()
    ed.close()


def test_field_editor_switch_to_constant_saves_text(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "ФИО")
    ed.type_combo.setCurrentIndex(ed.type_combo.findData("constant"))
    ed._const_edit.setText("Иванов")

    ed._on_ok()

    field = _pj_field(ed, "ФИО")
    assert (field.source.value, field.value) == ("constant", "Иванов")
    assert field.counter_name is None
    dlg.close()
    ed.close()


def test_field_editor_today_saves_preset(qapp, tmp_path, store):
    from stanok.engine.resolve import TODAY_PRESETS

    dlg, ed = _editor(tmp_path, store, "ФИО")
    ed.type_combo.setCurrentIndex(ed.type_combo.findData("today"))
    preset = TODAY_PRESETS[-1]
    ed._date_combo.setCurrentIndex(ed._date_combo.findData(preset))

    ed._on_ok()

    field = _pj_field(ed, "ФИО")
    assert (field.source.value, field.value) == ("today", preset)
    dlg.close()
    ed.close()


def test_field_editor_counter_field_formats_preview(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "Номер")
    ed._blk_fmt.setCurrentIndex(ed._blk_fmt.findData("001"))
    ed._blk_pos.setText("7")

    assert ed._preview.text() == "007"
    dlg.close()
    ed.close()


def test_field_editor_shared_counter_is_read_only_and_not_copied(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "Номер", shared={"shared_num": {"pos": 3}})
    ed._counter_combo.setCurrentIndex(ed._counter_combo.findData("shared_num"))

    assert ed._blk_pos.isReadOnly()
    assert ed._blk_pos.text() == "3"
    ed._on_ok()

    assert "shared_num" not in ed._pj.counters
    assert _pj_field(ed, "Номер").value == "shared_num"
    assert ed.changed is True
    dlg.close()
    ed.close()


def test_field_editor_table_field_does_not_offer_shared_counter(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "ФИО", shared={"shared_num": {}})

    assert ed._counter_combo.findData("shared_num") < 0
    dlg.close()
    ed.close()


def test_field_editor_clashing_shared_name_is_disabled(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "Номер", shared={"v": {}}, project_counter="v")
    idx = ed._counter_combo.findText(f"v ({STRINGS.GCNT_CLASH_TAG})")

    assert idx >= 0
    assert not ed._counter_combo.model().item(idx).isEnabled()
    dlg.close()
    ed.close()


def test_field_editor_create_counter_adds_project_counter(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(fe, "ask_text", lambda *a, **k: ("новый", True))
    dlg, ed = _editor(tmp_path, store, "Номер")

    ed._on_create_counter()

    assert "новый" in ed._pj.counters
    assert ed._counter_combo.currentData() == "новый"
    assert ed.changed is True
    dlg.close()
    ed.close()


def test_field_editor_create_duplicate_counter_warns(qapp, tmp_path, store, monkeypatch, warnings):
    monkeypatch.setattr(fe, "ask_text", lambda *a, **k: ("data", True))
    dlg, ed = _editor(tmp_path, store, "Номер")

    ed._on_create_counter()

    assert warnings and STRINGS.FLD_DUP_COUNTER.format(name="data") in warnings
    assert ed.changed is False
    dlg.close()
    ed.close()


def test_field_editor_create_empty_name_is_noop(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(fe, "ask_text", lambda *a, **k: ("   ", True))
    dlg, ed = _editor(tmp_path, store, "Номер")
    before = set(ed._pj.counters)

    ed._on_create_counter()

    assert set(ed._pj.counters) == before
    dlg.close()
    ed.close()


def test_field_editor_remove_unused_counter(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(fe, "ask_text", lambda *a, **k: ("временный", True))
    monkeypatch.setattr(fe, "ask_yes_no", lambda *a, **k: True)
    dlg, ed = _editor(tmp_path, store, "Номер")
    ed._on_create_counter()

    ed._on_remove_counter()

    assert "временный" not in ed._pj.counters
    dlg.close()
    ed.close()


def test_field_editor_remove_refused_while_field_reads_counter(qapp, tmp_path, store, warnings):
    dlg, ed = _editor(tmp_path, store, "Номер")
    ed._counter_combo.setCurrentIndex(ed._counter_combo.findData("num"))

    ed._on_remove_counter()

    assert "num" in ed._pj.counters
    assert warnings and "Номер" in warnings[0]
    dlg.close()
    ed.close()


def test_field_editor_remove_button_is_off_for_source_bound_counter(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "ФИО")

    assert not ed._blk_remove.isEnabled()
    dlg.close()
    ed.close()


def test_field_editor_remove_refused_for_source_bound_counter(qapp, tmp_path, store, warnings):
    dlg, ed = _editor(tmp_path, store, "ФИО")

    ed._on_remove_counter()

    assert "data" in ed._pj.counters
    assert warnings == [STRINGS.FLD_CNT_REMOVE_BOUND]
    dlg.close()
    ed.close()


def test_field_editor_unknown_counter_name_stays_visible(qapp, tmp_path, store):
    dlg, ed = _editor(tmp_path, store, "Номер")
    ed._pj.templates["Договор"].fields["Номер"].value = "давно_нет"
    ed._on_type_changed()
    ed.type_combo.setCurrentIndex(ed.type_combo.findData("counter"))

    assert ed._counter_combo.findData("давно_нет") >= 0
    dlg.close()
    ed.close()
