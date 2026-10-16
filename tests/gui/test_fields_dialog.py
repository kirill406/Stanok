# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for Window 3 (FieldsDialog)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox

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

    monkeypatch.setattr(QMessageBox, "question", boom)
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg.reject()
    assert dlg.result() == QDialog.Rejected


def test_close_dirty_discard(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.Discard
    )
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._rows["Город"]["const"].setText("Казань")
    dlg.reject()
    assert dlg.result() == QDialog.Rejected
    assert _saved_value(store) == "Москва"


def test_close_dirty_save(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Save)
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    dlg._rows["Город"]["const"].setText("Казань")
    dlg.reject()
    assert dlg.result() == QDialog.Accepted
    assert _saved_value(store) == "Казань"


def test_close_dirty_cancel_stays(qapp, tmp_path, store, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Cancel)
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
    assert dlg._read_headers(None) == []
    dlg.close()


def test_headers_no_sources(qapp, tmp_path, store):
    import json as _json

    folder = make_project(tmp_path / "proj")
    data = _json.loads((folder / "project.stanok").read_text())
    data["data_sources"] = []
    (folder / "project.stanok").write_text(_json.dumps(data))
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
        QMessageBox, "question", lambda *a, **k: QMessageBox.Save
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
    assert saved == {"source": "constant", "value": "{{ФИО}}", "table": None}
    dlg.close()


def test_table_file_and_column_saved(qapp, tmp_path, store):
    from tests.services.test_storage import _src_files

    folder = make_project(tmp_path / "proj")
    xlsx, _ = _src_files(tmp_path, "src2")
    (folder / "Данные").mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy(xlsx, folder / "Данные" / "data2.xlsx")
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["data_sources"].append(
        {"file": "Данные/data2.xlsx", "mode": "sequential", "start_row": 0}
    )
    pj_path.write_text(json.dumps(data, ensure_ascii=False))
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["ФИО"]
    assert st["file"].count() == 3
    st["file"].setCurrentIndex(2)
    assert st["col"].count() == 2
    st["col"].setCurrentIndex(0)
    dlg._on_save()
    saved = _saved_pj(store)["templates"]["Договор"]["fields"]["ФИО"]
    assert saved["table"] == "Данные/data2.xlsx"
    assert saved["value"] == "ФИО"
    dlg.close()


def test_legacy_table_without_file(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["ФИО"]
    assert st["file"].currentData() is None
    assert st["file"].currentText() == STRINGS.FLD_TABLE_ANY
    assert st["col"].currentText() == "ФИО"
    dlg.close()


def test_counter_new_name_and_format(qapp, tmp_path, store, monkeypatch):
    from PyQt5.QtWidgets import QInputDialog

    folder = make_project(tmp_path / "proj")
    monkeypatch.setattr(
        QInputDialog, "getText", lambda *a, **k: ("doc", True)
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "counter")
    st = dlg._rows["ФИО"]
    st["cname"].setCurrentIndex(st["cname"].count() - 1)
    assert st["cname"].currentData() == "doc"
    st["fmt"].setCurrentIndex(st["fmt"].findData("001"))
    assert "043" in st["cprev"].text() or st["cprev"].text() == "000"
    dlg._on_save()
    saved = _saved_pj(store)
    assert saved["templates"]["Договор"]["fields"]["ФИО"]["value"] == "doc"
    assert saved["counters"]["doc"] == {"last": 0, "format": "001"}
    dlg.close()


def test_empty_column_blocks_save(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
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


def test_empty_counter_blocks_save(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "counter")
    dlg._rows["ФИО"]["last"].setText("   ")
    dlg._on_save()
    assert any("ФИО" in w for w in warnings)
    dlg.close()


def test_today_type_saves(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "Номер", "today")
    dlg._on_save()
    saved = _saved_pj(store)["templates"]["Договор"]["fields"]["Номер"]
    assert saved == {"source": "today", "value": None, "table": None}
    dlg.close()


def test_dirty_close_save_blocked_stays_open(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    (folder / "Данные" / "data.xlsx").unlink()
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.Save
    )
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
    assert st["last"].text() == "0"
    st["last"].setText("7")
    st["fmt"].setCurrentIndex(st["fmt"].findData("01"))
    assert st["cprev"].text() == "07"
    dlg._on_save()
    saved = _saved_pj(store)
    assert saved["counters"]["num"] == {"last": 7, "format": "01"}
    dlg.close()


def test_counter_new_cancel_reverts(qapp, tmp_path, store, monkeypatch):
    from PyQt5.QtWidgets import QInputDialog

    folder = make_project(tmp_path / "proj")
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "counter")
    st = dlg._rows["ФИО"]
    before = st["cname"].currentData()
    st["cname"].setCurrentIndex(st["cname"].count() - 1)
    assert st["cname"].currentData() == before
    dlg.close()


def test_date_format_saves_preset(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_today(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["Дата"]
    assert st["dfmt"].currentData() is None
    st["dfmt"].setCurrentIndex(st["dfmt"].findData("ru_long"))
    assert "октября" in st["dlabel"].text()
    dlg._on_save()
    saved = _saved_pj(store)["templates"]["Договор"]["fields"]["Дата"]
    assert saved == {"source": "today", "value": "ru_long", "table": None}
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
    ).CounterDef(last=5, format="001")
    _set_type(dlg, "ФИО", "counter")
    st = dlg._rows["ФИО"]
    st["cname"].setCurrentIndex(st["cname"].findData("doc2"))
    assert st["last"].text() == "5"
    assert st["cprev"].text() == "005"
    dlg._on_save()
    saved = _saved_pj(store)
    assert saved["counters"]["doc2"] == {"last": 5, "format": "001"}
    assert saved["counters"]["num"] == {"last": 0, "format": "plain"}
    dlg.close()


def test_date_preset_reopen_selects(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_today(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    st = dlg._rows["Дата"]
    st["dfmt"].setCurrentIndex(st["dfmt"].findData("iso"))
    dlg._on_save()
    dlg.close()
    dlg2 = FieldsDialog(str(folder), "Договор", store=store)
    assert dlg2._rows["Дата"]["dfmt"].currentData() == "iso"
    assert "2026" in dlg2._rows["Дата"]["dlabel"].text()
    dlg2.close()


def test_negative_last_blocks_save(qapp, tmp_path, store, monkeypatch):
    folder = make_project(tmp_path / "proj")
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "counter")
    dlg._rows["ФИО"]["last"].setText("-3")
    dlg._on_save()
    assert any("целое" in w for w in warnings)
    dlg.close()


def test_counter_no_counters_blocks_save(qapp, tmp_path, store, monkeypatch):
    import json as _json

    folder = make_project(tmp_path / "proj", with_counter=False)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: warnings.append(a[-1])
    )
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    _set_type(dlg, "ФИО", "counter")
    assert dlg._rows["ФИО"]["cname"].count() == 1
    dlg._on_save()
    assert any("ФИО" in w for w in warnings)
    data = _json.loads((store.home_dir / "proj.stanok").read_text())
    assert data["counters"] == {}
    dlg.close()


def test_result_column(qapp, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_constant(folder)
    _add_today(folder)
    dlg = FieldsDialog(str(folder), "Договор", store=store)
    headers = [
        dlg.table.horizontalHeaderItem(c).text()
        for c in range(dlg.table.columnCount())
    ]
    assert headers == ["Поле", "Источник", "Данные", "Значение"]
    assert dlg._rows["ФИО"]["clabel"].text() == "Иван"
    assert dlg._rows["Город"]["result"].text() == "Москва"
    dlg._rows["Город"]["const"].setText("Казань")
    assert dlg._rows["Город"]["result"].text() == "Казань"
    assert "Дата" in dlg._rows
    dlg.close()
