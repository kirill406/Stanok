# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared (сквозные) counters: window 1 dialog and the counter field list (026)."""

import json

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton, QSpinBox

import stanok.gui.field_editor as fe
from stanok.gui.fields_dialog import FieldsDialog
from stanok.gui.global_counters_dialog import GlobalCountersDialog
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


def test_dialog_adds_and_lists_shared_counter(qapp, store, monkeypatch):
    import stanok.gui.global_counters_dialog as gcd

    class FakeAdd:
        def __init__(self, parent=None):
            pass

        def exec_(self):
            return 1

        def name(self):
            return "invoice"

        def fmt(self):
            return "0001"

        def start(self):
            return 41

    monkeypatch.setattr(gcd, "AddSharedCounterDialog", FakeAdd)
    dlg = GlobalCountersDialog(store)
    dlg._on_add()
    assert store.global_counters()["invoice"].format == "0001"
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 0).text() == "invoice"
    assert dlg.table.cellWidget(0, 2).findChild(QSpinBox).value() == 41
    dlg.close()


def test_add_button_sits_at_bottom_next_to_close(qapp, store):
    dlg = GlobalCountersDialog(store)
    texts = [b.text() for b in dlg.findChildren(QPushButton)]
    assert STRINGS.GCNT_ADD in texts and STRINGS.START_CLOSE in texts
    assert not hasattr(dlg, "name_edit")  # the add form lives in its own dialog
    dlg.close()


def test_add_dialog_collects_name_format_and_start(qapp):
    from stanok.gui.global_counters_dialog import AddSharedCounterDialog

    dlg = AddSharedCounterDialog()
    dlg.name_edit.setText("cnt")
    dlg.format_combo.setCurrentIndex(dlg.format_combo.findData("01"))
    dlg.start_spin.setValue(5)
    assert (dlg.name(), dlg.fmt(), dlg.start()) == ("cnt", "01", 5)
    dlg.close()


def test_dialog_value_change_persists(qapp, store):
    store.add_global_counter("n", "1", 0)
    dlg = GlobalCountersDialog(store)
    spin = dlg.table.cellWidget(0, 2).findChild(QSpinBox)
    spin.setValue(9)
    dlg._on_value_changed("n", 9)
    assert store.global_counters()["n"].pos == 9
    dlg.close()


def test_dialog_remove_refused_while_used(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    store.migrate_from_project(folder)
    store.add_global_counter("shared_num", "1", 0)
    data = json.loads((store.home_dir / "proj.stanok").read_text())
    data["templates"]["Договор"]["fields"]["Номер"] = {
        "source": "counter",
        "value": "shared_num",
    }
    data["counters"].pop("num", None)
    (store.home_dir / "proj.stanok").write_text(json.dumps(data, ensure_ascii=False))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
    monkeypatch.setattr(
        "stanok.gui.global_counters_dialog.ask_yes_no", lambda *a, **k: True
    )
    dlg = GlobalCountersDialog(store)
    dlg._on_remove("shared_num")
    assert warnings and "используют проекты" in warnings[0]
    assert "shared_num" in store.global_counters()
    dlg.close()


def _field_editor(tmp_path, store, field="Номер"):
    """Window 3 and the field editor for `field`, with one shared counter."""
    folder = make_project(tmp_path / "proj")
    store.migrate_from_project(folder)
    store.add_global_counter("shared_num", "1", 3)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    ed = fe.FieldEditDialog(dlg._pj, "Договор", field, dlg._sources, store, dlg)
    return dlg, ed


def test_field_counter_list_offers_shared_counter(qapp, tmp_path, store):
    dlg, ed = _field_editor(tmp_path, store)
    tagged = f"shared_num ({STRINGS.GCNT_SHARED_TAG})"
    assert ed._counter_combo.findText(tagged) >= 0
    assert ed._counter_combo.findData("shared_num") >= 0
    ed.close()
    dlg.close()


def test_shared_counter_preview_shows_its_value(qapp, tmp_path, store):
    dlg, ed = _field_editor(tmp_path, store)
    ed._counter_combo.setCurrentIndex(ed._counter_combo.findData("shared_num"))
    assert ed._current_pos("shared_num") == 3
    ed.close()
    dlg.close()


def test_clashing_shared_counter_is_disabled_in_fields_combo(qapp, tmp_path, store):
    import json

    folder = make_project(tmp_path / "proj")
    store.migrate_from_project(folder)
    store.add_global_counter("v", "1", 0)
    data = json.loads((store.home_dir / "proj.stanok").read_text())
    data["counters"]["v"] = {"pos": 0, "format": "1"}
    (store.home_dir / "proj.stanok").write_text(json.dumps(data, ensure_ascii=False))
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    ed = fe.FieldEditDialog(dlg._pj, "Договор", "Номер", dlg._sources, store, dlg)
    combo = ed._counter_combo
    idx = combo.findText(f"v ({STRINGS.GCNT_CLASH_TAG})")
    assert idx >= 0
    assert not combo.model().item(idx).isEnabled()
    ed.close()
    dlg.close()


def test_double_click_renames_shared_counter(qapp, store, monkeypatch):
    import stanok.gui.global_counters_dialog as gcd

    store.add_global_counter("before", "1", 0)
    monkeypatch.setattr(gcd, "ask_text", lambda *a, **k: ("after", True))
    dlg = GlobalCountersDialog(store)
    dlg._on_name_double_clicked(dlg.table.item(0, 0))
    assert list(store.global_counters()) == ["after"]
    dlg.close()


def test_saving_shared_field_does_not_copy_name_into_project(qapp, tmp_path, store):
    dlg, ed = _field_editor(tmp_path, store)
    ed._counter_combo.setCurrentIndex(ed._counter_combo.findData("shared_num"))
    ed._on_ok()
    dlg._mark_dirty()
    dlg._on_save()
    pj = store.load("proj")
    assert "shared_num" not in pj.counters
    assert pj.templates["Договор"].fields["Номер"].value == "shared_num"
    ed.close()
    dlg.close()
