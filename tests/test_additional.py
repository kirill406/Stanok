# -*- coding: utf-8 -*-
"""Renderer edge cases, field dialog data, and fill form type visibility tests."""

import os
import tempfile
import zipfile


import openpyxl
from docx import Document
from lxml import etree

from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
    CycleMapping, AggregationMapping, AggregationFunction,
    create_project,
)
from docxforge.engine import Renderer, format_counter, format_today, compute_aggregation
from docxforge.engine.data_reader import DataReader
from docxforge.engine.template_parser import scan_template

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _make_dirs(tmp):
    os.makedirs(os.path.join(tmp, 'Данные'), exist_ok=True)
    os.makedirs(os.path.join(tmp, 'Шаблоны'), exist_ok=True)


def _read_output_text(path):
    with zipfile.ZipFile(path, 'r') as zf:
        doc = etree.parse(zf.open('word/document.xml'))
        lines = []
        for p in doc.findall('.//{%s}p' % W):
            text = ''
            for r in p.findall('{%s}r' % W):
                for t in r.findall('{%s}t' % W):
                    if t.text:
                        text += t.text
            if text:
                lines.append(text)
        return '\n'.join(lines)


# ============================================================
# DataReader tests
# ============================================================

class TestRendererEdgeCases:
    """Additional renderer tests for edge cases."""

    def test_single_doc_with_table_field_uses_first_row(self):
        """Single doc mode: TABLE field uses first row of data."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['город'])
            ws.append(['Москва'])
            ws.append(['Питер'])
            wb.save(os.path.join(tmp, 'Данные', 'города.xlsx'))

            doc = Document()
            doc.add_paragraph('Город: {{ город }}')
            doc.save(os.path.join(tmp, 'Шаблоны', 't.docx'))

            prj = Project()
            tc = TemplateConfig()
            tc.fields['город'] = FieldMapping(type=FieldType.TABLE, file='города.xlsx', column='город')
            prj.templates['t.docx'] = tc
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('t.docx', {})

            assert len(outputs) == 1
            text = _read_output_text(outputs[0])
            assert 'Москва' in text

    def test_batch_with_constant_stays_same(self):
        """Batch mode: CONSTANT field keeps same value in all docs."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['имя'])
            ws.append(['А'])
            ws.append(['Б'])
            wb.save(os.path.join(tmp, 'Данные', 'data.xlsx'))

            doc = Document()
            doc.add_paragraph('Имя: {{ имя }} | Компания: {{ компания }}')
            doc.save(os.path.join(tmp, 'Шаблоны', 't.docx'))

            prj = Project()
            tc = TemplateConfig()
            tc.fields['имя'] = FieldMapping(type=FieldType.TABLE, file='data.xlsx', column='имя')
            tc.fields['компания'] = FieldMapping(type=FieldType.CONSTANT, value='ООО Ромашка')
            prj.templates['t.docx'] = tc
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('t.docx', {}, batch_table='data.xlsx')

            assert len(outputs) == 2
            t1 = _read_output_text(outputs[0])
            t2 = _read_output_text(outputs[1])
            assert 'ООО Ромашка' in t1
            assert 'ООО Ромашка' in t2
            assert 'Имя: А' in t1
            assert 'Имя: Б' in t2

    def test_batch_produces_correct_number_of_docs(self):
        """Batch mode: number of documents equals number of data rows."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['имя'])
            for i in range(10):
                ws.append(['Человек %d' % (i + 1)])
            wb.save(os.path.join(tmp, 'Данные', 'people.xlsx'))

            doc = Document()
            doc.add_paragraph('Привет, {{ имя }}')
            doc.save(os.path.join(tmp, 'Шаблоны', 't.docx'))

            prj = Project()
            tc = TemplateConfig()
            tc.fields['имя'] = FieldMapping(type=FieldType.TABLE, file='people.xlsx', column='имя')
            prj.templates['t.docx'] = tc
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('t.docx', {}, batch_table='people.xlsx')

            assert len(outputs) == 10

    def test_counter_zero_padded_in_batch(self):
        """Batch: counter with zero-padded format increments correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['x'])
            ws.append(['a'])
            ws.append(['b'])
            ws.append(['c'])
            wb.save(os.path.join(tmp, 'Данные', 'data.xlsx'))

            doc = Document()
            doc.add_paragraph('Документ № {{ doc_number }}')
            doc.save(os.path.join(tmp, 'Шаблоны', 't.docx'))

            prj = Project()
            tc = TemplateConfig()
            tc.fields['doc_number'] = FieldMapping(type=FieldType.COUNTER, start=1, format='0001')
            prj.templates['t.docx'] = tc
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('t.docx', {}, batch_table='data.xlsx')

            texts = [_read_output_text(o) for o in outputs]
            assert 'Документ № 0001' in texts[0]
            assert 'Документ № 0002' in texts[1]
            assert 'Документ № 0003' in texts[2]

    def test_today_field_in_render(self):
        """TODAY field produces current date in document."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)

            doc = Document()
            doc.add_paragraph('Дата: {{ дата }}')
            doc.save(os.path.join(tmp, 'Шаблоны', 't.docx'))

            prj = Project()
            tc = TemplateConfig()
            tc.fields['дата'] = FieldMapping(type=FieldType.TODAY, format='dd.MM.yyyy')
            prj.templates['t.docx'] = tc
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('t.docx', {})

            text = _read_output_text(outputs[0])
            # Should contain a date like dd.MM.yyyy
            import re
            assert re.search(r'\d{2}\.\d{2}\.\d{4}', text), 'Expected date in text: %r' % text

    def test_constant_replaces_placeholder(self):
        """CONSTANT field replaces placeholder in document."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)

            doc = Document()
            doc.add_paragraph('Организация: {{ орг }}')
            doc.save(os.path.join(tmp, 'Шаблоны', 't.docx'))

            prj = Project()
            tc = TemplateConfig()
            tc.fields['орг'] = FieldMapping(type=FieldType.CONSTANT, value='ООО Вектор')
            prj.templates['t.docx'] = tc
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('t.docx', {})

            text = _read_output_text(outputs[0])
            assert text == 'Организация: ООО Вектор'

    def test_no_placeholders_produces_unchanged_doc(self):
        """Template with no placeholders renders without error."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)

            doc = Document()
            doc.add_paragraph('Статический текст')
            doc.save(os.path.join(tmp, 'Шаблоны', 't.docx'))

            prj = Project()
            prj.templates['t.docx'] = TemplateConfig()
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('t.docx', {})

            assert len(outputs) == 1
            text = _read_output_text(outputs[0])
            assert text == 'Статический текст'


# ============================================================
# GUI field_dialog logic tests (non-GUI, just data logic)
# ============================================================

class TestFieldDialogData:
    """Test that field_dialog template data structure is correct."""

    def test_field_templates_have_all_types(self):
        from docxforge.gui.field_dialog import FIELD_TEMPLATES
        types = {t['type'] for t in FIELD_TEMPLATES}
        assert 'константа' in types
        assert 'таблица' in types
        assert 'счётчик' in types
        assert 'сегодня' in types
        assert 'изображение' in types

    def test_field_templates_have_required_keys(self):
        from docxforge.gui.field_dialog import FIELD_TEMPLATES
        required = {'name', 'icon', 'description', 'example', 'type', 'fields'}
        for t in FIELD_TEMPLATES:
            assert required.issubset(set(t.keys())), 'Missing keys in %s' % t['name']

    def test_field_templates_fields_have_widget_key(self):
        from docxforge.gui.field_dialog import FIELD_TEMPLATES
        for t in FIELD_TEMPLATES:
            for f in t['fields']:
                assert 'widget' in f, 'Missing widget in %s' % f['label']
                assert 'key' in f, 'Missing key in %s' % f['label']


# ============================================================
# GUI fill_form type-visibility logic tests
# ============================================================

class TestFillFormTypeVisibility:
    """Test that fill_form FIELD_TYPES list covers all schema types."""

    def test_field_types_match_schema(self):
        from docxforge.gui.fill_form import FIELD_TYPES_ENUM
        from docxforge.engine.schema import FieldType
        # Every FieldType enum value should have a corresponding GUI entry
        for ft in FieldType:
            assert ft in FIELD_TYPES_ENUM.values(), 'FieldType %s not in GUI' % ft

    def test_field_types_enum_complete(self):
        from docxforge.gui.fill_form import FIELD_TYPES, FIELD_TYPES_ENUM
        assert len(FIELD_TYPES) == len(FIELD_TYPES_ENUM)
        for ft_name in FIELD_TYPES:
            assert ft_name in FIELD_TYPES_ENUM

