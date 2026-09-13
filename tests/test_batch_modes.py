# -*- coding: utf-8 -*-
"""Tests for BatchMode, BatchSourceConfig, and renderer batch modes."""

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


class TestBatchSourceConfig:

    def test_batch_mode_enum_values(self):
        assert RowIterationMode.CONSTANT.value == "constant"
        assert RowIterationMode.SEQUENTIAL.value == "sequential"
        assert RowIterationMode.SEQUENTIAL.value == "sequential"
        assert RowIterationMode.CIRCULAR.value == "circular"

    def test_batch_source_config_defaults(self):
        bsc = BatchSourceConfig()
        assert bsc.file == ""
        assert bsc.mode == RowIterationMode.CONSTANT

    def test_batch_source_config_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Project()
            tc = TemplateConfig()
            tc.batch_sources["clients.xlsx"] = BatchSourceConfig(
                file="clients.xlsx", mode=RowIterationMode.SEQUENTIAL)
            tc.batch_sources["staff.xlsx"] = BatchSourceConfig(
                file="staff.xlsx", mode=RowIterationMode.SEQUENTIAL)
            tc.batch_sources["cities.xlsx"] = BatchSourceConfig(
                file="cities.xlsx", mode=RowIterationMode.CIRCULAR)
            tc.total_docs = 50
            prj.templates["t.docx"] = tc
            path = os.path.join(tmp, "proj.docxforge")
            prj.to_file(path)
            prj2 = Project.from_file(path)
            tc2 = prj2.templates["t.docx"]
            assert len(tc2.batch_sources) == 3
            assert tc2.batch_sources["clients.xlsx"].mode == RowIterationMode.SEQUENTIAL
            assert tc2.batch_sources["staff.xlsx"].mode == RowIterationMode.SEQUENTIAL
            assert tc2.batch_sources["cities.xlsx"].mode == RowIterationMode.CIRCULAR
            assert tc2.total_docs == 50

    def test_total_docs_default_none(self):
        tc = TemplateConfig()
        assert tc.total_docs is None

    def test_batch_config_no_max_docs_when_not_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Project()
            tc = TemplateConfig()
            prj.templates["t.docx"] = tc
            path = os.path.join(tmp, "proj.docxforge")
            prj.to_file(path)
            prj2 = Project.from_file(path)
            assert prj2.templates["t.docx"].total_docs is None


class TestRendererBatchModes:

    def test_batch_single_uses_first_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name"])
            ws.append(["Anna"])
            ws.append(["Boris"])
            ws.append(["Vera"])
            wb.save(os.path.join(tmp, "Данные", "people.xlsx"))
            doc = Document()
            doc.add_paragraph("Name: {{ name }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))
            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))
            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            bsc = BatchSourceConfig(file="people.xlsx", mode=RowIterationMode.CONSTANT)
            outputs = renderer.render("t.docx", {},
                batch_table="people.xlsx",
                batch_configs={"people.xlsx": bsc})
            assert len(outputs) == 1
            text = _read_output_text(outputs[0])
            assert "Anna" in text

    def test_batch_n_rows_limits_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name"])
            ws.append(["Anna"])
            ws.append(["Boris"])
            ws.append(["Vera"])
            wb.save(os.path.join(tmp, "Данные", "people.xlsx"))
            doc = Document()
            doc.add_paragraph("Name: {{ name }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))
            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))
            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            bsc = BatchSourceConfig(file="people.xlsx", mode=RowIterationMode.SEQUENTIAL)
            outputs = renderer.render("t.docx", {},
                batch_table="people.xlsx",
                batch_configs={"people.xlsx": bsc},
                max_docs=2)
            assert len(outputs) == 2
            texts = [_read_output_text(o) for o in outputs]
            assert "Anna" in texts[0]
            assert "Boris" in texts[1]

    def test_batch_circular_repeats_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name"])
            ws.append(["A"])
            ws.append(["B"])
            wb.save(os.path.join(tmp, "Данные", "data.xlsx"))
            doc = Document()
            doc.add_paragraph("Name: {{ name }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))
            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="data.xlsx", column="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))
            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            bsc = BatchSourceConfig(file="data.xlsx", mode=RowIterationMode.CIRCULAR)
            outputs = renderer.render("t.docx", {},
                batch_table="data.xlsx",
                batch_configs={"data.xlsx": bsc},
                max_docs=5)
            assert len(outputs) == 5
            texts = [_read_output_text(o) for o in outputs]
            assert "A" in texts[0]
            assert "B" in texts[1]
            assert "A" in texts[2]
            assert "B" in texts[3]
            assert "A" in texts[4]

    def test_max_docs_limits_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name"])
            for i in range(10):
                ws.append(["Person %d" % (i + 1)])
            wb.save(os.path.join(tmp, "Данные", "people.xlsx"))
            doc = Document()
            doc.add_paragraph("Hello, {{ name }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))
            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="people.xlsx", column="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))
            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render("t.docx", {},
                batch_table="people.xlsx",
                max_docs=3)
            assert len(outputs) == 3

    def test_batch_all_rows_same_as_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name"])
            ws.append(["X"])
            ws.append(["Y"])
            wb.save(os.path.join(tmp, "Данные", "data.xlsx"))
            doc = Document()
            doc.add_paragraph("Name: {{ name }}")
            doc.save(os.path.join(tmp, "Шаблоны", "t.docx"))
            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.TABLE, file="data.xlsx", column="name")
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, "проект.docxforge"))
            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            bsc = BatchSourceConfig(file="data.xlsx", mode=RowIterationMode.SEQUENTIAL)
            outputs_new = renderer.render("t.docx", {},
                batch_table="data.xlsx",
                batch_configs={"data.xlsx": bsc})
            outputs_legacy = renderer.render("t.docx", {},
                batch_table="data.xlsx")
            assert len(outputs_new) == len(outputs_legacy) == 2
