# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for Window 3 (FieldsDialog)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import logging
import shutil

import pytest
from openpyxl import Workbook
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from stanok.gui.fields_dialog import FieldsDialog
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


def _add_constant(folder):
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["templates"]["Договор"]["fields"]["Город"] = {
        "source": "constant",
        "value": "Москва",
    }
    pj_path.write_text(json.dumps(data, ensure_ascii=False))


def _saved_value(store, field="Город"):
    raw = json.loads((store.home_dir / "proj.stanok").read_text())
    return raw["templates"]["Договор"]["fields"][field]["value"]


def test_open_shows_fields(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg.table.rowCount() == 4
    names = [dlg.table.item(r, 0).text() for r in range(4)]
    assert names == ["ФИО", "Сумма", "Номер", "Город"]
    types = [dlg._rows[n]["type"].currentText() for n in names]
    assert types == [
        STRINGS.FLD_SRC_TABLE,
        STRINGS.FLD_SRC_TABLE,
        STRINGS.FLD_SRC_COUNTER,
        STRINGS.FLD_SRC_CONSTANT,
    ]
    # Table row: file + column combos with headers
    assert dlg._rows["ФИО"]["col"].count() == 2
    assert dlg._rows["ФИО"]["col"].currentText() == "ФИО"
    assert isinstance(dlg._rows["Город"]["const"], QLineEdit)
    dlg.close()


def test_edit_save_persists(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._rows["Город"]["const"].setText("Казань")
    assert dlg._dirty
    dlg._on_save()
    assert not dlg._dirty
    assert _saved_value(store) == "Казань"
    dlg.close()


def test_close_clean_no_question(qapp, tmp_path, store, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("question must not appear")

    monkeypatch.setattr("stanok.gui.fields_dialog.ask_save_discard_cancel", boom)
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg.reject()
    assert dlg.result() == QDialog.Rejected


def test_close_dirty_discard(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(
        "stanok.gui.fields_dialog.ask_save_discard_cancel",
        lambda *a, **k: QMessageBox.Discard,
    )
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._rows["Город"]["const"].setText("Казань")
    dlg.reject()
    assert dlg.result() == QDialog.Rejected
    assert _saved_value(store) == "Москва"


def test_close_dirty_save(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr("stanok.gui.fields_dialog.ask_save_discard_cancel", lambda *a, **k: QMessageBox.Save)
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._rows["Город"]["const"].setText("Казань")
    dlg.reject()
    assert dlg.result() == QDialog.Accepted
    assert _saved_value(store) == "Казань"


def test_close_dirty_cancel_stays(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr("stanok.gui.fields_dialog.ask_save_discard_cancel", lambda *a, **k: QMessageBox.Cancel)
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._rows["Город"]["const"].setText("Казань")
    dlg.reject()
    assert dlg.result() == 0
    assert _saved_value(store) == "Москва"
    dlg.close()


def test_open_missing_project_raises(qapp, tmp_path, store):
    with pytest.raises(StorageError):
        FieldsDialog("nope", "Договор", store=store)


def test_open_missing_template_raises(qapp, tmp_path, store):
    from stanok.services.generate import TemplateError

    folder = make_project(tmp_path / "proj")
    with pytest.raises(TemplateError, match="template not found"):
        FieldsDialog(str(folder), "Чужой", store=store)


def _add_today(folder):
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["templates"]["Договор"]["fields"]["Дата"] = {"source": "today"}
    pj_path.write_text(json.dumps(data, ensure_ascii=False))


def test_today_preview(qapp, tmp_path, store):
    import datetime

    folder = make_project(tmp_path / "proj")
    _add_today(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert "Дата" in dlg._rows
    assert "dlabel" in dlg._rows["Дата"]
    assert datetime.date.today().isoformat() in dlg._rows["Дата"]["dlabel"].text()
    dlg.close()


def test_headers_nondir_ref(qapp, tmp_path, store):
    from stanok.services.generate import generate_documents, GenerateCommand

    folder = make_project(tmp_path / "proj")
    generate_documents(GenerateCommand(project_ref=folder), store=store)
    store.add_recent(str(folder), "proj")
    dlg = FieldsDialog("proj", "Договор", store=store)
    assert dlg._read_headers(None) == ["ФИО", "Сумма"]
    dlg.close()


def test_headers_no_sources(qapp, tmp_path, store):
    import json as _json

    folder = make_project(tmp_path / "proj")
    data = _json.loads((folder / "project.stanok").read_text())
    data["data_sources"] = []
    data["counters"] = {}
    data["templates"]["Договор"]["fields"] = {}
    (folder / "project.stanok").write_text(_json.dumps(data, ensure_ascii=False))
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg._read_headers(None) == []
    dlg.close()


def test_headers_read_failure_warns(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.fields_dialog as fd

    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )

    def boom(self, path):
        raise OSError("locked")

    monkeypatch.setattr(fd.ExcelReader, "read", boom)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg._read_headers("Данные/data.xlsx") == []
    assert warnings and "data.xlsx" in warnings[0]
    dlg.close()


def test_headers_skip_blank_columns_with_warning(qapp, tmp_path, store, monkeypatch):
    folder = make_project(
        tmp_path / "proj",
        headers=("ФИО", None, "Сумма"),
        rows=(("Иван", "лишнее", 100),),
    )
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert warnings
    assert "B" in warnings[0]
    assert "пропущены столбцы" in warnings[0]
    assert dlg._rows["ФИО"]["col"].count() == 2
    dlg.close()


def test_save_failure_shows_critical(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    shown = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *a: shown.append(a[-1])
    )

    def boom(*a, **k):
        raise OSError("read-only")

    dlg = FieldsDialog(str(folder), "Договор", store=store)
    monkeypatch.setattr(store, "save", boom)
    dlg._dirty = True
    dlg._on_save()
    assert shown
    assert dlg._dirty
    dlg.close()


def test_dirty_save_failure_stays_open(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    shown = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *a: shown.append(a[-1])
    )
    monkeypatch.setattr(
        "stanok.gui.fields_dialog.ask_save_discard_cancel",
        lambda *a, **k: QMessageBox.Save,
    )

    def boom(*a, **k):
        raise OSError("read-only")

    dlg = FieldsDialog(str(folder), "Договор", store=store)
    monkeypatch.setattr(store, "save", boom)
    dlg._dirty = True
    dlg.reject()
    assert shown
    dlg.close()


def _saved_pj(store):
    return json.loads((store.home_dir / "proj.stanok").read_text())


def _set_type(dlg, name, source):
    dlg._rows[name]["type"].setCurrentIndex(["constant", "table", "counter", "today"].index(source))


def test_switch_to_constant_prefills_and_saves(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "constant")
    assert dlg._dirty
    assert dlg._rows["ФИО"]["const"].text() == "{{ФИО}}"
    dlg._on_save()
    saved = _saved_pj(store)["templates"]["Договор"]["fields"]["ФИО"]
    assert saved == {"source": "constant", "value": "{{ФИО}}", "counter_name": None}
    dlg.close()


def test_table_counter_and_column_saved(qapp, tmp_path, store):
    from tests.services.test_storage import _src_files

    folder = make_project(tmp_path / "proj")
    xlsx, _ = _src_files(tmp_path, "src2")
    (folder / "Данные").mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy(xlsx, folder / "Данные" / "data2.xlsx")
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["data_sources"].append({"file": "Данные/data2.xlsx", "mode": "sequential"})
    data["counters"]["data2"] = {
        "pos": 0,
        "format": "1",
        "table": "Данные/data2.xlsx",
        "resume": 1,
    }
    pj_path.write_text(json.dumps(data, ensure_ascii=False))
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["ФИО"]
    assert st["cname"].count() == 3
    st["cname"].setCurrentIndex(st["cname"].findData("data2"))
    assert st["col"].count() == 2
    st["col"].setCurrentIndex(0)
    dlg._on_save()
    saved = _saved_pj(store)["templates"]["Договор"]["fields"]["ФИО"]
    assert saved["counter_name"] == "data2"
    assert saved["value"] == "ФИО"
    dlg.close()


def test_legacy_table_without_file(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["ФИО"]
    assert st["cname"].currentData() == "data"
    assert st["cname"].count() == 2
    assert st["col"].currentText() == "ФИО"
    dlg.close()


def test_counter_create_via_table(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    monkeypatch.setattr(
        "stanok.gui.fields_dialog.ask_text", lambda *a, **k: ("doc", True)
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg.ctable.rowCount() == 2
    dlg._on_counter_create()
    assert dlg.ctable.rowCount() == 3
    assert dlg._rows["Номер"]["cname"].findData("doc") >= 0
    _set_type(dlg, "ФИО", "counter")
    st = dlg._rows["ФИО"]
    st["cname"].setCurrentIndex(st["cname"].findData("doc"))
    cfmt = dlg._crows["doc"]["fmt"]
    cfmt.setCurrentIndex(cfmt.findData("001"))
    dlg._on_save()
    saved = _saved_pj(store)
    assert saved["templates"]["Договор"]["fields"]["ФИО"]["value"] == "doc"
    assert saved["counters"]["doc"] == {
        "pos": 0,
        "format": "001",
        "table": None,
        "resume": 1,
    }
    dlg.close()


def test_resume_checkbox_inverted_label(qapp, tmp_path, store):
    """Column «Начинать заново»: checked means resume=0 (start over)."""
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    box = dlg._crows["data"]["resume"]
    assert box.isChecked() is False  # resume=1 → не «начинать заново»
    box.setChecked(True)
    dlg._on_save()
    assert _saved_pj(store)["counters"]["data"]["resume"] == 0
    dlg.close()


def test_counter_create_duplicate_warns(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    monkeypatch.setattr("stanok.gui.fields_dialog.ask_text", lambda *a, **k: ("num", True))
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._on_counter_create()
    assert warnings and "num" in warnings[0]
    assert dlg.ctable.rowCount() == 2
    dlg.close()


def test_empty_column_blocks_save(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    monkeypatch.setattr(FieldsDialog, "_ask_source_recovery", lambda self, name: None)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg._rows["ФИО"]["col"].count() == 0
    dlg._on_save()
    assert any("ФИО" in w and "пустое" in w for w in warnings)
    assert _saved_pj(store)["templates"]["Договор"]["fields"]["ФИО"]["value"] == "ФИО"
    dlg.close()


def test_type_switch_marks_dirty(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert not dlg._dirty
    _set_type(dlg, "Номер", "today")
    assert dlg._dirty
    assert "dlabel" in dlg._rows["Номер"]
    dlg.close()


def test_counter_row_has_no_value_editor(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "counter")
    st = dlg._rows["ФИО"]
    assert "cprev" in st
    st["cname"].setCurrentIndex(st["cname"].findData("num"))
    assert st["cprev"].text() == "0"
    dlg.close()


def test_today_type_saves(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "Номер", "today")
    dlg._on_save()
    saved = _saved_pj(store)["templates"]["Договор"]["fields"]["Номер"]
    assert saved == {"source": "today", "value": "dmy", "counter_name": None}
    dlg.close()


def test_dirty_close_save_blocked_stays_open(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    monkeypatch.setattr(
        "stanok.gui.fields_dialog.ask_save_discard_cancel",
        lambda *a, **k: QMessageBox.Save,
    )
    monkeypatch.setattr(FieldsDialog, "_ask_source_recovery", lambda self, name: None)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._dirty = True
    dlg.reject()
    assert any("пустое" in w for w in warnings)
    assert dlg.result() == 0
    dlg.close()


def test_counter_select_existing_loads(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "counter")
    st = dlg._rows["ФИО"]
    st["cname"].setCurrentIndex(st["cname"].findData("num"))
    cfmt = dlg._crows["num"]["fmt"]
    cfmt.setCurrentIndex(cfmt.findData("01"))
    dlg._crows["num"]["pos"].setText("7")
    assert st["cprev"].text() == "07"
    dlg._on_save()
    saved = _saved_pj(store)
    assert saved["counters"]["num"]["pos"] == 7
    assert saved["counters"]["num"]["format"] == "01"
    dlg.close()


def test_counter_create_cancel_noop(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    monkeypatch.setattr("stanok.gui.fields_dialog.ask_text", lambda *a, **k: ("", False))
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._on_counter_create()
    assert dlg.ctable.rowCount() == 2
    dlg.close()


def test_date_format_saves_preset(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_today(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["Дата"]
    assert st["dfmt"].currentData() is None
    st["dfmt"].setCurrentIndex(st["dfmt"].findData("month_ru"))
    assert st["dlabel"].text() == "октября"
    dlg._on_save()
    saved = _saved_pj(store)["templates"]["Договор"]["fields"]["Дата"]
    assert saved == {"source": "today", "value": "month_ru", "counter_name": None}
    dlg.close()


def test_table_value_label(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["ФИО"]
    assert st["clabel"].text() == "Иван"
    st["col"].setCurrentIndex(-1)
    dlg._update_table_value("ФИО")
    assert st["clabel"].text() == "Иван"
    dlg.close()


def test_counter_select_other_counter(qapp, tmp_path, store):
    import json as _json

    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._pj.counters["doc2"] = __import__(
        "stanok.engine.schema", fromlist=["CounterDef"]
    ).CounterDef(pos=5, format="001")
    _set_type(dlg, "ФИО", "counter")
    st = dlg._rows["ФИО"]
    st["cname"].setCurrentIndex(st["cname"].findData("doc2"))
    assert st["cprev"].text() == "005"
    dlg._on_save()
    saved = _saved_pj(store)
    assert saved["counters"]["doc2"]["pos"] == 5
    assert saved["counters"]["num"]["pos"] == 0
    dlg.close()


def test_date_preset_reopen_selects(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_today(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["Дата"]
    st["dfmt"].setCurrentIndex(st["dfmt"].findData("month_ru"))
    dlg._on_save()
    dlg.close()
    dlg2 = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg2._rows["Дата"]["dfmt"].currentData() == "month_ru"
    assert dlg2._rows["Дата"]["dlabel"].text() == "октября"
    dlg2.close()


def test_result_column(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    _add_today(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    headers = [
        dlg.table.horizontalHeaderItem(c).text()
        for c in range(dlg.table.columnCount())
    ]
    assert headers == ["Поле", "Тип", "Данные", "Значение"]
    assert dlg._rows["ФИО"]["clabel"].text() == "Иван"
    assert dlg._rows["Город"]["result"].text() == "Москва"
    dlg._rows["Город"]["const"].setText("Казань")
    assert dlg._rows["Город"]["result"].text() == "Казань"
    assert "Дата" in dlg._rows
    dlg.close()


def test_save_button_visibility(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg.save_btn.isHidden()
    dlg._rows["Город"]["const"].setText("Казань")
    assert not dlg.save_btn.isHidden()
    assert dlg.save_btn.property("role") == "primary"
    dlg._on_save()
    assert dlg.save_btn.isHidden()
    dlg.close()


def test_headers_and_close_button(qapp, tmp_path, store):
    from PyQt5.QtWidgets import QHeaderView

    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    header = dlg.table.horizontalHeader()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeToContents
    assert header.sectionResizeMode(1) == QHeaderView.ResizeToContents
    assert header.sectionResizeMode(2) == QHeaderView.Stretch
    assert header.sectionResizeMode(3) == QHeaderView.ResizeToContents
    assert dlg.findChild(type(dlg.save_btn)).text() != ""
    close_btns = [
        b for b in dlg.findChildren(type(dlg.save_btn))
        if b.text() == STRINGS.FLD_CLOSE
    ]
    assert len(close_btns) == 1
    dlg.close()


def test_today_keep_only_for_legacy(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "today")
    items = [
        dlg._rows["ФИО"]["dfmt"].itemData(i)
        for i in range(dlg._rows["ФИО"]["dfmt"].count())
    ]
    assert None not in items
    assert dlg._rows["ФИО"]["dfmt"].currentData() == "dmy"
    dlg.close()


def test_today_empty_format_blocks_save(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    _add_today(folder)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg._rows["Дата"]["dfmt"].currentData() is None
    dlg._on_save()
    assert any("Дата" in w for w in warnings)
    import json as _json

    data = _json.loads((store.home_dir / "proj.stanok").read_text())
    assert data["templates"]["Договор"]["fields"]["Дата"]["value"] is None
    dlg.close()


def test_counters_table_binding_saves(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg.ctable.rowCount() == 2
    assert dlg._crows["num"]["table"].currentData() is None
    bind = dlg._crows["num"]["table"]
    bind.setCurrentIndex(bind.findData("Данные/data.xlsx"))
    dlg._crows["num"]["pos"].setText("9")
    dlg._on_save()
    saved = _saved_pj(store)["counters"]["num"]
    assert saved["table"] == "Данные/data.xlsx"
    assert saved["pos"] == 9
    dlg.close()


def test_counters_table_bad_pos_blocks(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._crows["num"]["pos"].setText("xx")
    dlg._on_save()
    assert any("num" in w for w in warnings)
    dlg.close()


def test_dangling_counter_resurrected(qapp, tmp_path, store):
    """Defensive: a counter field naming a missing counter is recreated on save.

    Such a PJ can no longer be loaded (schema rejects it), so simulate
    in-memory divergence instead.
    """
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    del dlg._pj.counters["num"]
    del dlg._crows["num"]
    st = dlg._rows["Номер"]
    assert st["cname"].currentData() == "num"
    dlg._on_save()
    saved = _saved_pj(store)
    assert saved["counters"]["num"]["pos"] == 0
    assert saved["templates"]["Договор"]["fields"]["Номер"]["value"] == "num"
    dlg.close()


def test_counters_table_negative_blocks(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._crows["num"]["pos"].setText("-1")
    dlg._on_save()
    assert any("num" in w for w in warnings)
    dlg.close()


def test_single_scroll_area(qapp, tmp_path, store):
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QScrollArea

    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    areas = dlg.findChildren(QScrollArea)
    assert len(areas) == 1
    assert dlg.table.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert dlg.ctable.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert dlg.table.height() > 0
    dlg.close()


def test_filename_template_edits(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg.fname_edit.text() == "Договор_{ФИО}_{i}.docx"
    dlg.fname_edit.setText("Акт_{Номер}")
    dlg._on_save()
    import json as _json

    data = _json.loads((store.home_dir / "proj.stanok").read_text())
    assert data["filename_template"] == "Акт_{Номер}"
    assert dlg.save_btn.isHidden()
    dlg.fname_edit.setText("   ")
    dlg._on_save()
    assert warnings
    dlg.close()


def test_insert_field_menu(qapp, tmp_path, store, monkeypatch):
    from PyQt5.QtWidgets import QMenu

    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg.fname_insert_btn.text() == STRINGS.FLD_INSERT_FIELD
    shown = []
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a: shown.append(self))
    dlg._on_insert_field()
    assert shown
    actions = [a.text() for a in shown[0].actions() if a.text()]
    assert "ФИО" in actions
    assert "{i}" in actions and "{template}" in actions
    fio = next(a for a in shown[0].actions() if a.text() == "ФИО")
    dlg.fname_edit.clear()
    fio.trigger()
    assert dlg.fname_edit.text() == "{ФИО}"
    dlg.close()


def _xlsx(path, headers=("ФИО", "Сумма"), rows=(("Иван", 100),)):
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    wb.save(path)


def test_missing_source_pick_copies_into_project(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    other = tmp_path / "elsewhere"
    other.mkdir()
    _xlsx(other / "data.xlsx")
    monkeypatch.setattr(FieldsDialog, "_ask_source_recovery", lambda self, name: "pick")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(other)
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert (folder / "Данные" / "data.xlsx").is_file()
    assert dlg._rows["ФИО"]["col"].count() == 2
    dlg.close()


def test_missing_source_pick_rebinds_relative(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    _xlsx(folder / "data.xlsx")
    monkeypatch.setattr(FieldsDialog, "_ask_source_recovery", lambda self, name: "pick")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *a, **k: str(folder)
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    pj, _ = store.resolve_project(str(folder))
    assert pj.data_sources[0].file == "data.xlsx"
    assert pj.counters["data"].table == "data.xlsx"
    assert dlg._rows["ФИО"]["col"].count() == 2
    dlg.close()


def test_missing_source_create_folders(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    shutil.rmtree(folder / "Данные")
    infos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a: infos.append(a[-1])
    )
    monkeypatch.setattr(
        FieldsDialog, "_ask_source_recovery", lambda self, name: "create"
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert (folder / "Данные").is_dir()
    assert (folder / "Шаблоны").is_dir()
    assert infos
    dlg.close()


def test_missing_source_cancel_prompts_once(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
    calls = {"n": 0}

    def ask(self, name):
        calls["n"] += 1
        return None

    monkeypatch.setattr(FieldsDialog, "_ask_source_recovery", ask)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    assert calls["n"] == 1
    assert len(warnings) == 1
    dlg._resolve_source_path("Данные/data.xlsx")
    assert calls["n"] == 1
    dlg.close()


def test_counters_table_column_order(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.fields_dialog as fields_module

    monkeypatch.setattr(fields_module, "picker_available", lambda: False)
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    labels = [
        dlg.ctable.horizontalHeaderItem(c).text()
        for c in range(dlg.ctable.columnCount())
    ]
    assert labels == [
        STRINGS.FLD_CNT_NAME,
        STRINGS.FLD_CNT_SOURCE,
        STRINGS.FLD_CNT_FORMAT,
        STRINGS.FLD_CNT_POS,
        STRINGS.FLD_CNT_RESUME,
    ]
    st = dlg._crows["data"]
    assert dlg.ctable.cellWidget(0, 1) is st["table"]
    assert dlg.ctable.cellWidget(0, 2) is st["fmt"]
    assert dlg.ctable.cellWidget(0, 3) is st["pos_box"]
    assert dlg.ctable.cellWidget(0, 4) is st["resume"]
    assert st["pos_box"].findChild(QLineEdit) is st["pos"]
    assert not st["pick"].isEnabled()
    assert st["pick"].toolTip() == STRINGS.FLD_PICK_DISABLED_TIP
    tips = [
        dlg.ctable.horizontalHeaderItem(c).toolTip()
        for c in range(dlg.ctable.columnCount())
    ]
    assert tips == [
        STRINGS.FLD_CNT_NAME_TIP,
        STRINGS.FLD_CNT_SOURCE_TIP,
        STRINGS.FLD_CNT_FORMAT_TIP,
        STRINGS.FLD_POS_TIP,
        STRINGS.FLD_CNT_RESUME_TIP,
    ]
    assert st["table"].toolTip() == STRINGS.FLD_CNT_SOURCE_TIP
    assert st["fmt"].toolTip() == STRINGS.FLD_CNT_FORMAT_TIP
    assert st["pos"].toolTip() == STRINGS.FLD_POS_TIP
    assert st["resume"].toolTip() == STRINGS.FLD_CNT_RESUME_TIP
    assert STRINGS.FLD_CNT_HINT in [
        w.text() for w in dlg.findChildren(QLabel)
    ]
    dlg.close()


def test_counters_table_fits_text(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    header = dlg.ctable.horizontalHeader()
    assert header.stretchLastSection() is False
    for col in range(dlg.ctable.columnCount()):
        assert header.sectionResizeMode(col) == QHeaderView.ResizeToContents
    dlg.close()


def test_counter_constant_mode_row_read_only(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj", mode="constant")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._crows["data"]
    assert st["pos"].isReadOnly()
    assert st["pos"].toolTip() == STRINGS.FLD_POS_CONST_TIP
    assert not st["resume"].isEnabled()
    combo = st["table"]
    combo.setCurrentIndex(combo.findData(None))
    assert not st["pos"].isReadOnly()
    assert st["pos"].toolTip() == STRINGS.FLD_POS_TIP
    assert not st["pick"].isEnabled()
    assert st["pick"].toolTip() == STRINGS.FLD_PICK_NO_SOURCE_TIP
    dlg.close()


def test_counter_pos_updates_field_preview(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._crows["num"]
    st["pos"].setText("7")
    assert dlg._rows["Номер"]["cprev"].text() == "7"
    st["fmt"].setCurrentIndex(st["fmt"].findData("0001"))
    assert dlg._rows["Номер"]["cprev"].text() == "0007"
    dlg.close()


def test_counter_change_skips_constant_field(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._crows["num"]["pos"].setText("7")
    assert dlg._rows["Номер"]["cprev"].text() == "7"
    assert dlg._rows["Город"]["const"].text() == "Москва"
    dlg.close()


def test_counter_change_error_logged_and_shown(
    qapp, tmp_path, store, monkeypatch, caplog
):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))

    def boom(_cname):
        raise RuntimeError("boom")

    monkeypatch.setattr(dlg, "_update_counter_row_state", boom)
    with caplog.at_level(logging.CRITICAL):
        dlg._on_counter_source_changed("data")
    assert "counter change source failed" in caplog.text
    assert shown and "boom" in shown[0]
    dlg.close()


def test_counter_pos_updates_table_field_preview(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._crows["data"]
    assert dlg._rows["ФИО"]["clabel"].text() == "Иван"
    st["pos"].setText("1")
    assert dlg._rows["ФИО"]["clabel"].text() == "Петр"
    dlg.close()


def test_counter_pick_writes_value_and_preview(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.fields_dialog as fields_module

    folder = make_project(tmp_path / "proj")
    monkeypatch.setattr(fields_module, "picker_available", lambda: True)
    monkeypatch.setattr(fields_module, "open_picker", lambda *a, **k: 42)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._crows["data"]
    assert st["pick"].isEnabled()
    assert st["pick"].toolTip() == STRINGS.FLD_PICK_TIP
    st["pick"].click()
    assert st["pos"].text() == "42"
    assert dlg._crows["data"]["touched"] is True
    dlg.close()



def test_ask_source_recovery_choices(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    buttons = [object(), object(), object()]
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: 0)
    for idx, expected in ((0, "pick"), (1, "create"), (2, None)):
        it = iter(buttons)
        monkeypatch.setattr(
            QMessageBox, "addButton", lambda self, *a, **k: next(it)
        )
        monkeypatch.setattr(
            QMessageBox, "clickedButton", lambda self, i=idx: buttons[i]
        )
        assert dlg._ask_source_recovery("x.xlsx") == expected
    dlg.close()


def test_restore_source_not_found(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert dlg._restore_source("Данные/data.xlsx", "data.xlsx", empty) is None
    dlg.close()


def test_resolve_source_uses_remembered_dir(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    donor = make_project(tmp_path / "donor")
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    monkeypatch.setattr(FieldsDialog, "_ask_source_recovery", lambda self, name: None)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._recovery_dir = donor / "Данные"
    dlg._rows_cache.clear()
    path = dlg._resolve_source_path("Данные/data.xlsx")
    assert path is not None and path.is_file()
    dlg.close()


def test_rebind_source_save_error_logged(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(dlg._store, "save", boom)
    dlg._rebind_source("Данные/data.xlsx", "x.xlsx")
    dlg.close()


def test_restore_source_copy_error_warns(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.fields_dialog as fd

    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    donor = make_project(tmp_path / "donor")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
    monkeypatch.setattr(FieldsDialog, "_ask_source_recovery", lambda self, name: None)
    dlg = FieldsDialog(str(folder), "Договор", store=store)

    def boom(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(fd.shutil, "copy2", boom)
    assert (
        dlg._restore_source("Данные/data.xlsx", "data.xlsx", donor / "Данные")
        is None
    )
    assert warnings
    dlg.close()


def test_counter_create_button_click(qapp, tmp_path, store, monkeypatch):
    import stanok.gui.fields_dialog as fields_module

    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    monkeypatch.setattr(
        fields_module, "ask_text", lambda *a, **k: ("Клиент", True)
    )
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: shown.append(a[-1]))
    dlg.counter_add_btn.click()
    assert "Клиент" in dlg._pj.counters
    assert not shown
    dlg.close()
