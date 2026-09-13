# -*- coding: utf-8 -*-
"""Unit tests for formatting functions and template parser."""

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

