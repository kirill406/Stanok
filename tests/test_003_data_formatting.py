# -*- coding: utf-8 -*-
"""Tests for the Excel → JSON boundary (data_formatting): row iteration
modes (constant / sequential / circular) over one shared selection core,
plus table reads. Field resolution lives in resolve_document_fields
(covered via generation tests); the single mechanism has no simplified
duplicate.
"""
import os

import openpyxl

from docxforge.engine.data_formatting import (
    read_table_rows,
    resolve_source_row,
    resolve_source_row_for_config,
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.schema import (
    BatchSourceConfig,
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
