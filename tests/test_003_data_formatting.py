# -*- coding: utf-8 -*-
"""Tests for 003-json Phase 2: the Excel → JSON boundary (data_formatting).

Covers native cell-type coercion, row iteration modes (constant /
sequential / circular), field resolution into Filling JSON values,
counter math, resume advance (B6) and broken cells. The legacy
Excel-direct path is not touched here (Strangler: new module aside).
"""
import os
from datetime import datetime

import openpyxl

from docxforge.engine.data_formatting import (
    advance_resume,
    read_table_rows,
    resolve_fields,
    resolve_source_row,
    resolve_source_row_for_config,
    value_to_str,
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.schema import (
    BatchSourceConfig,
    FieldMapping,
    FieldType,
    ResumeState,
    RowIterationMode,
)


def _write_xlsx(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)


class TestDataFormattingValueToStr:
    def test_data_formatting_int_to_str(self):
        assert value_to_str(42) == '42'

    def test_data_formatting_integral_float_to_str(self):
        assert value_to_str(10000.0) == '10000'

    def test_data_formatting_fraction_float_to_str(self):
        assert value_to_str(3.14) == '3.14'

    def test_data_formatting_bool_to_str(self):
        assert value_to_str(True) == 'True'
        assert value_to_str(False) == 'False'

    def test_data_formatting_none_to_empty(self):
        assert value_to_str(None) == ''

    def test_data_formatting_str_stripped(self):
        assert value_to_str('  padded  ') == 'padded'

    def test_data_formatting_broken_cell_to_empty(self):
        class Broken:
            def __str__(self):
                raise RuntimeError('boom')
        assert value_to_str(Broken()) == ''


class TestDataFormattingReadTable:
    def test_data_formatting_read_table_native_types(self, tmp_path):
        path = str(tmp_path / 'data.xlsx')
        _write_xlsx(path, [
            ['name', 'qty', 'price', 'ok'],
            ['Ivan', 7, 10000.0, True],
            ['Petr', 3, 2.5, False],
        ])
        rows = read_table_rows(DataReader(), path)
        assert len(rows) == 2
        assert rows[0]['name'] == 'Ivan'
        assert rows[0]['qty'] == 7
        assert rows[0]['price'] == 10000
        assert rows[0]['ok'] is True
        assert rows[1]['price'] == 2.5

    def test_data_formatting_read_table_missing_file_empty(self, tmp_path):
        rows = read_table_rows(DataReader(), str(tmp_path / 'nope.xlsx'))
        assert rows == []

    def test_data_formatting_read_table_corrupt_file_empty(self, tmp_path):
        path = str(tmp_path / 'broken.xlsx')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('not an excel file')
        assert read_table_rows(DataReader(), path) == []


class TestDataFormattingRowModes:
    ROWS = [{'name': 'a'}, {'name': 'b'}, {'name': 'c'}]

    def test_data_formatting_constant_returns_first_row(self):
        assert resolve_source_row(self.ROWS, RowIterationMode.CONSTANT) == {'name': 'a'}

    def test_data_formatting_constant_lookup_hit(self):
        row = resolve_source_row(
            self.ROWS, RowIterationMode.CONSTANT,
            lookup_column='name', lookup_value='b')
        assert row == {'name': 'b'}

    def test_data_formatting_constant_lookup_miss_none(self):
        assert resolve_source_row(
            self.ROWS, RowIterationMode.CONSTANT,
            lookup_column='name', lookup_value='zzz') is None

    def test_data_formatting_sequential_in_order(self):
        assert resolve_source_row(self.ROWS, RowIterationMode.SEQUENTIAL, 0) == {'name': 'a'}
        assert resolve_source_row(self.ROWS, RowIterationMode.SEQUENTIAL, 2) == {'name': 'c'}

    def test_data_formatting_sequential_exhausted_none(self):
        assert resolve_source_row(self.ROWS, RowIterationMode.SEQUENTIAL, 3) is None

    def test_data_formatting_sequential_resume_offset(self):
        assert resolve_source_row(
            self.ROWS, RowIterationMode.SEQUENTIAL, 0, start_offset=1) == {'name': 'b'}

    def test_data_formatting_circular_wraps(self):
        assert resolve_source_row(self.ROWS, RowIterationMode.CIRCULAR, 3) == {'name': 'a'}
        assert resolve_source_row(self.ROWS, RowIterationMode.CIRCULAR, 4) == {'name': 'b'}

    def test_data_formatting_circular_resume_offset(self):
        assert resolve_source_row(
            self.ROWS, RowIterationMode.CIRCULAR, 0, start_offset=2) == {'name': 'c'}

    def test_data_formatting_empty_rows_none(self):
        assert resolve_source_row([], RowIterationMode.SEQUENTIAL, 0) is None
        assert resolve_source_row([], RowIterationMode.CONSTANT) is None

    def test_data_formatting_unknown_mode_none(self):
        assert resolve_source_row(self.ROWS, 'bogus-mode', 0) is None

    def test_data_formatting_string_mode_coerced(self):
        assert resolve_source_row(self.ROWS, 'sequential', 1) == {'name': 'b'}


class TestDataFormattingRowForConfig:
    ROWS = [{'name': 'a'}, {'name': 'b'}, {'name': 'c'}]

    def test_data_formatting_config_resume_continues(self):
        config = BatchSourceConfig(file='d.xlsx', mode=RowIterationMode.SEQUENTIAL)
        resume = ResumeState(last_counter_value=0,
                             sources={'d.xlsx': 2},
                             continue_from_last=True)
        assert resolve_source_row_for_config(self.ROWS, config, 0, resume) == {'name': 'c'}

    def test_data_formatting_config_resume_disabled_ignores_offset(self):
        config = BatchSourceConfig(file='d.xlsx', mode=RowIterationMode.SEQUENTIAL)
        resume = ResumeState(last_counter_value=0,
                             sources={'d.xlsx': 2},
                             continue_from_last=False)
        assert resolve_source_row_for_config(self.ROWS, config, 0, resume) == {'name': 'a'}

    def test_data_formatting_config_broken_offset_falls_back(self):
        config = BatchSourceConfig(file='d.xlsx', mode=RowIterationMode.SEQUENTIAL)
        resume = ResumeState(last_counter_value=0,
                             sources={'d.xlsx': 'bogus'},
                             continue_from_last=True)
        assert resolve_source_row_for_config(self.ROWS, config, 0, resume) == {'name': 'a'}


class TestDataFormattingResolveFields:
    def test_data_formatting_resolve_constant(self):
        fields = {'org': FieldMapping(type=FieldType.CONSTANT, value='Roma')}
        assert resolve_fields(fields, None) == {'org': 'Roma'}

    def test_data_formatting_resolve_table_native_types(self):
        fields = {
            'qty': FieldMapping(type=FieldType.TABLE, file='d.xlsx', column='qty'),
            'price': FieldMapping(type=FieldType.TABLE, file='d.xlsx', column='price'),
            'ok': FieldMapping(type=FieldType.TABLE, file='d.xlsx', column='ok'),
            'missing': FieldMapping(type=FieldType.TABLE, file='d.xlsx', column='nope'),
        }
        row = {'qty': 7, 'price': 10000.0, 'ok': True}
        resolved = resolve_fields(fields, row)
        assert resolved['qty'] == '7'
        assert resolved['price'] == '10000'
        assert resolved['ok'] == 'True'
        assert resolved['missing'] == ''

    def test_data_formatting_resolve_table_no_row_empty(self):
        fields = {'a': FieldMapping(type=FieldType.TABLE, file='d.xlsx', column='a')}
        assert resolve_fields(fields, None) == {'a': ''}

    def test_data_formatting_resolve_counter(self):
        fields = {'n': FieldMapping(type=FieldType.COUNTER, start=1, format='0001')}
        assert resolve_fields(fields, None, doc_index=0, counter_base=0) == {'n': '0001'}
        assert resolve_fields(fields, None, doc_index=4, counter_base=10) == {'n': '0015'}

    def test_data_formatting_resolve_today(self):
        fields = {'d': FieldMapping(type=FieldType.TODAY, format='dd.MM.yyyy')}
        now = datetime(2024, 5, 6, 12, 30)
        assert resolve_fields(fields, None, now=now) == {'d': '06.05.2024'}

    def test_data_formatting_resolve_image_keeps_path(self):
        fields = {'logo': FieldMapping(type=FieldType.IMAGE, value='img/logo.png')}
        assert resolve_fields(fields, None) == {'logo': 'img/logo.png'}

    def test_data_formatting_resolve_all_values_are_strings(self, tmp_path):
        path = str(tmp_path / 'data.xlsx')
        _write_xlsx(path, [
            ['name', 'qty', 'ok'],
            ['Ivan', 5, True],
        ])
        rows = read_table_rows(DataReader(), path)
        fields = {
            'org': FieldMapping(type=FieldType.CONSTANT, value='Roma'),
            'name': FieldMapping(type=FieldType.TABLE, file='data.xlsx', column='name'),
            'qty': FieldMapping(type=FieldType.TABLE, file='data.xlsx', column='qty'),
            'n': FieldMapping(type=FieldType.COUNTER, start=1, format='0001'),
        }
        filling = {
            'template': 'contract.docx',
            'dist': os.path.join('out', 'Ivan_0001.docx'),
            'fields': resolve_fields(fields, rows[0]),
        }
        assert filling['fields'] == {
            'org': 'Roma', 'name': 'Ivan', 'qty': '5', 'n': '0001'}
        assert all(isinstance(v, str) for v in filling['fields'].values())
        assert '{{' not in str(filling['fields'])


class TestDataFormattingAdvanceResume:
    def test_data_formatting_advance_resume_continues(self):
        resume = ResumeState(last_counter_value=5, continue_from_last=True)
        assert advance_resume(resume, 3) == 8
        assert resume.last_counter_value == 8

    def test_data_formatting_advance_resume_restarts(self):
        resume = ResumeState(last_counter_value=5, continue_from_last=False)
        assert advance_resume(resume, 3) == 3
        assert resume.last_counter_value == 3

    def test_data_formatting_advance_resume_noop(self):
        resume = ResumeState(last_counter_value=5, continue_from_last=True)
        assert advance_resume(resume, 0) == 5
        assert advance_resume(resume, -2) == 5
        assert resume.last_counter_value == 5

    def test_data_formatting_advance_resume_matches_schema_math(self):
        from docxforge.engine.schema import advance_counter_after_creation
        for last, flag, created in [(0, True, 4), (7, True, 2), (7, False, 2)]:
            mine = ResumeState(last_counter_value=last, continue_from_last=flag)
            ref = ResumeState(last_counter_value=last, continue_from_last=flag)
            assert advance_resume(mine, created) == advance_counter_after_creation(ref, created)
