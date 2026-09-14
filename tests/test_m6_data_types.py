# -*- coding: utf-8 -*-
"""Regression tests for 001-review M6 and M7.

M6: DataReader preserves native cell types (dates/numbers/bool) and
    distinguishes a missing file (FileNotFoundError) from a corrupt
    file (error log + []).
M7: rows[0] fallbacks become '' + warning (render_loop field values,
    renderer CONSTANT lookup miss / unknown mode).
"""
import logging
import os
import tempfile
from datetime import datetime

import openpyxl
import pytest

from docxforge.engine.data_reader import DataReader, _coerce_cell
from docxforge.engine.render_loop import resolve_field_values
from docxforge.engine.renderer import Renderer
from docxforge.engine.schema import (
    BatchSourceConfig, FieldMapping, FieldType, RowIterationMode,
    TemplateConfig,
)


def _write_xlsx(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)


class TestM6CellTypes:
    def test_m6_coerce_scalar_types(self):
        assert _coerce_cell(None) == ''
        assert _coerce_cell(True) is True
        assert _coerce_cell(False) is False
        assert _coerce_cell(42) == 42
        assert _coerce_cell(10000.0) == 10000
        assert isinstance(_coerce_cell(10000.0), int)
        assert _coerce_cell(3.14) == 3.14
        assert _coerce_cell('  padded  ') == 'padded'

    def test_m6_coerce_datetime_native(self):
        stamp = datetime(2024, 5, 6, 12, 30)
        assert _coerce_cell(stamp) is stamp

    def test_m6_read_excel_preserves_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'types.xlsx')
            _write_xlsx(path, [
                ['when', 'qty', 'price', 'ok', 'name'],
                [datetime(2024, 5, 6), 7, 10000.0, True, '  spaced  '],
            ])
            rows = DataReader().read_excel(path)
            assert len(rows) == 1
            assert rows[0]['when'] == datetime(2024, 5, 6)
            assert rows[0]['qty'] == 7
            assert isinstance(rows[0]['qty'], int)
            assert rows[0]['price'] == 10000
            assert isinstance(rows[0]['price'], int)
            assert rows[0]['ok'] is True
            assert rows[0]['name'] == 'spaced'


class TestM6MissingVsCorrupt:
    def test_m6_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(FileNotFoundError):
                DataReader().read_excel(os.path.join(tmp, 'nope.xlsx'))

    def test_m6_missing_columns_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(FileNotFoundError):
                DataReader().get_columns(os.path.join(tmp, 'nope.xlsx'))

    def test_m6_corrupt_file_returns_empty_with_error(self, caplog):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'broken.xlsx')
            with open(path, 'wb') as f:
                f.write(b'this is not a zip file')
            with caplog.at_level(logging.ERROR,
                                 logger='docxforge.engine.data_reader'):
                rows = DataReader().read_excel(path)
            assert rows == []
            assert any('Error reading' in (r.getMessage() or '')
                       for r in caplog.records)


class TestM7NoRowsZeroFallback:
    def _config(self):
        tc = TemplateConfig()
        tc.fields['name'] = FieldMapping(
            type=FieldType.TABLE, file='d.xlsx', column='name')
        return tc

    def test_m7_missing_column_gives_empty_with_warning(self, caplog):
        from docxforge.engine.schema import ResumeState
        tc = self._config()
        with caplog.at_level(logging.WARNING,
                             logger='docxforge.engine.render_loop'):
            effective, _images = resolve_field_values(
                tc, [], 0, {}, {'d.xlsx': [{'other': 'v'}]}, {},
                ResumeState(), datetime.now(), {})
        assert effective['name'] == ''
        assert any('name' in (r.getMessage() or '') for r in caplog.records)

    def test_m7_present_value_still_resolves(self):
        from docxforge.engine.schema import ResumeState
        tc = self._config()
        effective, _images = resolve_field_values(
            tc, [], 0, {'d.xlsx': {'name': 'Ann'}},
            {'d.xlsx': [{'name': 'First'}]}, {}, ResumeState(),
            datetime.now(), {})
        assert effective['name'] == 'Ann'

    def test_m7_constant_lookup_miss_selects_no_row(self, caplog):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = Renderer(tmp, DataReader())
            bsc = BatchSourceConfig(file='d.xlsx',
                                    mode=RowIterationMode.CONSTANT,
                                    lookup_column='id', lookup_value='zzz')
            rows = [{'id': 'aaa', 'name': 'Ann'}]
            with caplog.at_level(logging.WARNING,
                                 logger='docxforge.engine.renderer'):
                assert renderer._resolve_constant_row(
                    'd.xlsx', {'d.xlsx': bsc}, rows) is None
            assert any('zzz' in (r.getMessage() or '')
                       for r in caplog.records)

    def test_m7_constant_lookup_hit_selects_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = Renderer(tmp, DataReader())
            bsc = BatchSourceConfig(file='d.xlsx',
                                    mode=RowIterationMode.CONSTANT,
                                    lookup_column='id', lookup_value='aaa')
            rows = [{'id': 'aaa', 'name': 'Ann'}]
            assert renderer._resolve_constant_row(
                'd.xlsx', {'d.xlsx': bsc}, rows) == rows[0]
