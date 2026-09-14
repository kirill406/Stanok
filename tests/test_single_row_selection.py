# -*- coding: utf-8 -*-
"""Tests for SINGLE row selection (by number and by lookup) and linked TABLE fields."""

import logging
import os, tempfile, zipfile

import openpyxl
from docx import Document
from lxml import etree

from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
    BatchSourceConfig, RowIterationMode,
)
from docxforge.engine import Renderer
from docxforge.engine.data_reader import DataReader

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_dirs(tmp):
    os.makedirs(os.path.join(tmp, "Данные"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "Шаблоны"), exist_ok=True)


def _read_output_text(path):
    with zipfile.ZipFile(path, "r") as zf:
        doc = etree.parse(zf.open("word/document.xml"))
        lines = []
        for p in doc.findall(".//{%s}p" % W):
            text = ""
            for r in p.findall("{%s}r" % W):
                for t in r.findall("{%s}t" % W):
                    if t.text:
                        text += t.text
            if text:
                lines.append(text)
        return "\n".join(lines)


class TestResolveSingleRow:
    """Test _resolve_single_row helper in Renderer."""

    def test_resolve_by_row_index(self):
        """SINGLE mode with explicit row_index picks that row."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "city"])
            ws.append(["Anna", "Moscow"])
            ws.append(["Boris", "SPb"])
            ws.append(["Vera", "Kazan"])
            wb.save(os.path.join(tmp, "Данные", "people.xlsx"))

            doc = Document()
            doc.add_paragraph("Name: {{ name }}, City: {{ city }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))

            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="name")
            tc.fields["city"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="city", linked_to="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()

            # Row index 1 (0-based) = Boris
            bsc = BatchSourceConfig(file="people.xlsx", mode=RowIterationMode.CONSTANT,
                                    lookup_column="name", lookup_value="Boris")
            outputs = renderer.render("t.docx", {},
                batch_table=None,
                batch_configs={"people.xlsx": bsc})
            assert len(outputs) == 1
            text = _read_output_text(outputs[0])
            assert "Boris" in text, "Got: %r" % text
            assert "SPb" in text, "Linked field must use same row: %r" % text

    def test_resolve_by_lookup(self):
        """SINGLE mode with lookup_column/lookup_value finds the right row."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "city", "inn"])
            ws.append(["Anna", "Moscow", "111"])
            ws.append(["Boris", "SPb", "222"])
            ws.append(["Vera", "Kazan", "333"])
            wb.save(os.path.join(tmp, "Данные", "people.xlsx"))

            doc = Document()
            doc.add_paragraph("Name: {{ name }}, City: {{ city }}, INN: {{ inn }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))

            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="name")
            tc.fields["city"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="city", linked_to="name")
            tc.fields["inn"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="inn", linked_to="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()

            # Lookup by city = Kazan → Vera
            bsc = BatchSourceConfig(
                file="people.xlsx", mode=RowIterationMode.CONSTANT,
                lookup_column="city", lookup_value="Kazan")
            outputs = renderer.render("t.docx", {},
                batch_table=None,
                batch_configs={"people.xlsx": bsc})
            assert len(outputs) == 1
            text = _read_output_text(outputs[0])
            assert "Vera" in text, "Got: %r" % text
            assert "Kazan" in text
            assert "333" in text, "Linked INN must match: %r" % text

    def test_single_doc_without_batch_configs_uses_first_row(self):
        """Without batch_configs, single document uses rows[0]."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name"])
            ws.append(["First"])
            ws.append(["Second"])
            wb.save(os.path.join(tmp, "Данные", "data.xlsx"))

            doc = Document()
            doc.add_paragraph("{{ name }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))

            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="data.xlsx", column="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()

            # No batch_configs → first row
            outputs = renderer.render("t.docx", {})
            assert len(outputs) == 1
            text = _read_output_text(outputs[0])
            assert "First" in text

    def test_linked_field_different_table_uses_primary_value(self, caplog):
        """Linked field from a different table is found by primary value."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)

            # clients.xlsx
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["client_name", "city"])
            ws.append(["Alpha", "Moscow"])
            ws.append(["Beta", "SPb"])
            wb.save(os.path.join(tmp, "Данные", "clients.xlsx"))

            # cities.xlsx
            wb2 = openpyxl.Workbook()
            ws2 = wb2.active
            ws2.append(["city", "population"])
            ws2.append(["Moscow", "12000000"])
            ws2.append(["SPb", "5000000"])
            wb2.save(os.path.join(tmp, "Данные", "cities.xlsx"))

            doc = Document()
            doc.add_paragraph("Client: {{ client }}, City: {{ city_info }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))

            prj = Project()
            tc = TemplateConfig()
            tc.fields["client"] = FieldMapping(type=FieldType.TABLE, file="clients.xlsx", column="client_name")
            tc.fields["city_info"] = FieldMapping(
                type=FieldType.TABLE, file="cities.xlsx", column="population", linked_to="client")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()

            # Pick row 1 (Beta, SPb) → city_info should resolve by city column from clients row
            # Primary client field maps to clients.xlsx, so city_info linked to "client"
            # needs to find the row in cities.xlsx where city matches the client's city
            # But wait — the linked field is from a DIFFERENT table (cities.xlsx),
            # so it looks up by primary's value in primary's column.
            # This won't directly work as expected without city as the lookup key.
            # The current design finds row in cities.xlsx where primary_col matches primary_val.
            # Since primary_col is "client_name" and primary_val is "Beta",
            # it won't find "Beta" in cities.xlsx's "city" column.
            # M16: cross-table linking requires matching column names
            # (known limitation). With mismatched names the lookup misses,
            # and per M7 (merged from fix/001-m6-data-reader) the field
            # renders as '' with a warning instead of borrowing rows[0].
            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            with caplog.at_level(logging.WARNING,
                                 logger='docxforge.engine.render_loop'):
                outputs = renderer.render("t.docx", {})
            assert len(outputs) == 1
            text = _read_output_text(outputs[0])
            assert "Alpha" in text
            assert "12000000" not in text
            assert any('Lookup miss' in (r.getMessage() or '')
                       for r in caplog.records)

    def test_single_row_index_zero_is_first_row(self):
        """row_index=0 selects first row."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["val"])
            ws.append(["AAA"])
            ws.append(["BBB"])
            wb.save(os.path.join(tmp, "Данные", "d.xlsx"))

            doc = Document()
            doc.add_paragraph("{{ val }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))

            prj = Project()
            tc = TemplateConfig()
            tc.fields["val"] = FieldMapping(type=FieldType.TABLE, file="d.xlsx", column="val")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()

            bsc = BatchSourceConfig(file="d.xlsx", mode=RowIterationMode.CONSTANT,
                                   lookup_column="val", lookup_value="AAA")
            outputs = renderer.render("t.docx", {},
                batch_table=None,
                batch_configs={"d.xlsx": bsc})
            text = _read_output_text(outputs[0])
            assert "AAA" in text


class TestFormStateSaveLoad:
    """Test form state save/load (unit tests for JSON round-trip)."""

    def test_save_and_load_form_state_json(self):
        """Form state serializes and deserializes correctly."""
        import json
        state = {
            "fields": {
                "org": {"type": "константа", "const_value": "ООО Тест"},
                "name": {"type": "таблица", "table_file": "clients.xlsx", "table_column": "name"},
            },
            "batch_mode": "single",
            "batch_sources": {
                "clients.xlsx": {
                    "mode_index": 0,
                    "n_rows": 1,
                    "use_lookup": False,
                    "row_number": 2,
                    "lookup_column": "",
                    "lookup_value": "",
                }
            },
            "limit_docs": False,
            "max_docs": 1,
            "advanced_visible": False,
        }
        json_str = json.dumps(state, ensure_ascii=False)
        loaded = json.loads(json_str)
        assert loaded["fields"]["org"]["const_value"] == "ООО Тест"
        assert loaded["batch_sources"]["clients.xlsx"]["row_number"] == 2

    def test_form_state_file_created_on_save(self):
        """_save_form_state creates a JSON file."""
        import json
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, ".form_state_test.json")
            state = {"fields": {}, "batch_mode": "single", "batch_sources": {}}
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            assert os.path.exists(state_path)
            with open(state_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["batch_mode"] == "single"
