# -*- coding: utf-8 -*-
"""Additional tests: data reader, schema, counter formatting, today formatting,
aggregations, template parser, edge cases, and GUI field-dialog logic."""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
from docx import Document
from lxml import etree

from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
    CycleMapping, AggregationMapping, AggregationFunction,
    create_project,
)
from docxforge.engine.renderer import Renderer, format_counter, format_today, compute_aggregation
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

class TestDataReader:
    """Tests for DataReader: reading Excel, getting columns, distinct values."""

    def test_read_excel_basic(self):
        with tempfile.TemporaryDirectory() as tmp:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['имя', 'возраст'])
            ws.append(['Анна', '25'])
            ws.append(['Борис', '30'])
            path = os.path.join(tmp, 'data.xlsx')
            wb.save(path)

            reader = DataReader()
            rows = reader.read_excel(path)
            assert len(rows) == 2
            assert rows[0]['имя'] == 'Анна'
            assert rows[0]['возраст'] == '25'
            assert rows[1]['имя'] == 'Борис'

    def test_read_excel_skips_empty_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['имя'])
            ws.append(['Анна'])
            ws.append([])  # empty row
            ws.append(['Борис'])
            path = os.path.join(tmp, 'data.xlsx')
            wb.save(path)

            reader = DataReader()
            rows = reader.read_excel(path)
            assert len(rows) == 2
            assert rows[0]['имя'] == 'Анна'
            assert rows[1]['имя'] == 'Борис'

    def test_read_excel_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            wb = openpyxl.Workbook()
            ws = wb.active
            # No data at all
            path = os.path.join(tmp, 'empty.xlsx')
            wb.save(path)

            reader = DataReader()
            rows = reader.read_excel(path)
            assert rows == []

    def test_get_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['название', 'ИНН', 'адрес'])
            ws.append(['ООО Альфа', '111', 'ул. 1'])
            path = os.path.join(tmp, 'data.xlsx')
            wb.save(path)

            reader = DataReader()
            cols = reader.get_columns(path)
            assert cols == ['название', 'ИНН', 'адрес']

    def test_get_distinct_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['город'])
            ws.append(['Москва'])
            ws.append(['Питер'])
            ws.append(['Москва'])
            path = os.path.join(tmp, 'data.xlsx')
            wb.save(path)

            reader = DataReader()
            vals = reader.get_distinct_values(path, 'город')
            assert vals == ['Москва', 'Питер']

    def test_read_excel_numeric_values_become_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['число'])
            ws.append([42])
            ws.append([3.14])
            path = os.path.join(tmp, 'data.xlsx')
            wb.save(path)

            reader = DataReader()
            rows = reader.read_excel(path)
            assert rows[0]['число'] == '42'
            assert rows[1]['число'] == '3.14'


# ============================================================
# Schema tests
# ============================================================

class TestSchema:
    """Tests for schema: round-trip save/load, field types."""

    def test_project_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Project()
            tc = TemplateConfig()
            tc.fields['имя'] = FieldMapping(type=FieldType.CONSTANT, value='Тест')
            tc.fields['клиент'] = FieldMapping(type=FieldType.TABLE, file='клиенты.xlsx', column='название')
            tc.fields['doc_number'] = FieldMapping(type=FieldType.COUNTER, start=5, format='001')
            tc.fields['дата'] = FieldMapping(type=FieldType.TODAY, format='dd.MM.yyyy')
            tc.fields['печать'] = FieldMapping(type=FieldType.IMAGE, value='seal.png')
            tc.cycles.append(CycleMapping(table='спецификация.xlsx', columns={'товар': 'наименование'}))
            tc.aggregations['итого'] = AggregationMapping(
                function=AggregationFunction.SUM, table='спецификация.xlsx', column='цена')
            prj.templates['contract.docx'] = tc

            path = os.path.join(tmp, 'проект.docxforge')
            prj.to_file(path)
            prj2 = Project.from_file(path)

            assert len(prj2.templates) == 1
            tc2 = prj2.templates['contract.docx']
            assert tc2.fields['имя'].type == FieldType.CONSTANT
            assert tc2.fields['имя'].value == 'Тест'
            assert tc2.fields['клиент'].type == FieldType.TABLE
            assert tc2.fields['клиент'].file == 'клиенты.xlsx'
            assert tc2.fields['doc_number'].start == 5
            assert tc2.fields['doc_number'].format == '001'
            assert tc2.fields['дата'].type == FieldType.TODAY
            assert tc2.fields['печать'].type == FieldType.IMAGE
            assert len(tc2.cycles) == 1
            assert len(tc2.aggregations) == 1

    def test_create_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj_file = create_project(os.path.join(tmp, 'myproject'))
            assert os.path.exists(proj_file)
            prj = Project.from_file(proj_file)
            assert prj.version == 1
            assert len(prj.templates) == 0

    def test_multiply_aggregation_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Project()
            tc = TemplateConfig()
            tc.aggregations['с_ндс'] = AggregationMapping(
                function=AggregationFunction.SUM_MULTIPLY,
                table='spec.xlsx', column='цена', multiplier=1.2)
            prj.templates['t.docx'] = tc
            path = os.path.join(tmp, 'проект.docxforge')
            prj.to_file(path)
            prj2 = Project.from_file(path)
            agg = prj2.templates['t.docx'].aggregations['с_ндс']
            assert agg.function == AggregationFunction.SUM_MULTIPLY
            assert agg.multiplier == 1.2


# ============================================================
# Formatter tests
# ============================================================

class TestFormatCounter:
    """Tests for counter formatting."""

    def test_zero_padded_format(self):
        assert format_counter(1, '0001') == '0001'
        assert format_counter(42, '001') == '042'
        assert format_counter(123, '00001') == '00123'

    def test_plain_format(self):
        assert format_counter(1, '1') == '1'
        assert format_counter(42, '1') == '42'

    def test_start_value(self):
        assert format_counter(100, '1') == '100'
        assert format_counter(100, '0001') == '0100'


class TestFormatToday:
    """Tests for date formatting."""

    def test_default_format(self):
        from datetime import datetime
        dt = datetime(2026, 9, 4, 14, 30, 0)
        result = format_today('dd.MM.yyyy', dt)
        assert result == '04.09.2026'

    def test_with_time(self):
        from datetime import datetime
        dt = datetime(2026, 9, 4, 14, 30, 0)
        result = format_today('dd.MM.yyyy HH:mm', dt)
        assert result == '04.09.2026 14:30'

    def test_year_only(self):
        from datetime import datetime
        dt = datetime(2026, 9, 4)
        result = format_today('yyyy', dt)
        assert result == '2026'

    def test_day_only(self):
        from datetime import datetime
        dt = datetime(2026, 9, 4)
        result = format_today('dd', dt)
        assert result == '04'

    def test_month_name_ru(self):
        from datetime import datetime
        dt = datetime(2026, 1, 15)
        result = format_today('dd MM:название_месяца yyyy', dt)
        assert 'января' in result
        assert '2026' in result


# ============================================================
# Aggregation tests
# ============================================================

class TestAggregation:
    """Tests for compute_aggregation function."""

    def test_sum(self):
        agg = AggregationMapping(function=AggregationFunction.SUM, table='x', column='цена')
        data = [{'цена': '100'}, {'цена': '200'}, {'цена': '300'}]
        assert compute_aggregation(agg, data) == '600'

    def test_count(self):
        agg = AggregationMapping(function=AggregationFunction.COUNT, table='x', column='цена')
        data = [{'цена': '100'}, {'цена': '200'}, {'цена': '300'}]
        assert compute_aggregation(agg, data) == '3'

    def test_max(self):
        agg = AggregationMapping(function=AggregationFunction.MAX, table='x', column='цена')
        data = [{'цена': '100'}, {'цена': '500'}, {'цена': '200'}]
        assert compute_aggregation(agg, data) == '500'

    def test_min(self):
        agg = AggregationMapping(function=AggregationFunction.MIN, table='x', column='цена')
        data = [{'цена': '100'}, {'цена': '50'}, {'цена': '200'}]
        assert compute_aggregation(agg, data) == '50'

    def test_sum_multiply(self):
        agg = AggregationMapping(
            function=AggregationFunction.SUM_MULTIPLY,
            table='x', column='цена', multiplier=1.2)
        data = [{'цена': '100'}, {'цена': '200'}]
        assert compute_aggregation(agg, data) == '360'

    def test_empty_data(self):
        agg = AggregationMapping(function=AggregationFunction.SUM, table='x', column='цена')
        assert compute_aggregation(agg, []) == '0'

    def test_comma_decimal(self):
        agg = AggregationMapping(function=AggregationFunction.SUM, table='x', column='цена')
        data = [{'цена': '100,50'}, {'цена': '200,25'}]
        result = compute_aggregation(agg, data)
        # Comma decimal → 100.50 + 200.25 = 300.75 → formatted as '300,75'
        assert result == '300,75'

    def test_sum_with_spaces(self):
        agg = AggregationMapping(function=AggregationFunction.SUM, table='x', column='цена')
        data = [{'цена': '1 000'}, {'цена': '2 000'}]
        result = compute_aggregation(agg, data)
        # Should handle spaces as thousand separators
        assert result == '3000'


# ============================================================
# Template parser tests
# ============================================================

class TestTemplateParser:
    """Tests for scan_template: classification of placeholder types."""

    def test_scan_simple(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.add_paragraph('Hello {{ имя }}')
            path = os.path.join(tmp, 't.docx')
            doc.save(path)
            result = scan_template(path)
            assert 'имя' in result['simple']

    def test_scan_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.add_paragraph('Date: {{ today:dd.MM.yyyy }}')
            path = os.path.join(tmp, 't.docx')
            doc.save(path)
            result = scan_template(path)
            assert 'today:dd.MM.yyyy' in result['today']

    def test_scan_doc_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.add_paragraph('No: {{ doc_number }}')
            path = os.path.join(tmp, 't.docx')
            doc.save(path)
            result = scan_template(path)
            assert 'doc_number' in result['doc_number']

    def test_scan_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.add_paragraph('Logo: {{ image:логотип }}')
            path = os.path.join(tmp, 't.docx')
            doc.save(path)
            result = scan_template(path)
            assert 'логотип' in result['image']

    def test_scan_multiple_same_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.add_paragraph('{{ имя }} и ещё {{ имя }}')
            path = os.path.join(tmp, 't.docx')
            doc.save(path)
            result = scan_template(path)
            # Should not duplicate
            assert result['simple'].count('имя') <= 1


# ============================================================
# Renderer edge cases
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
