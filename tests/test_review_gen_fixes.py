# -*- coding: utf-8 -*-
"""Regression tests for specs/001-review/REPORT.md BLOCKER fixes (gen path).

Covers: B5 (schema.create_projects sanitizes + dedups directory_template),
B8 (render_execute: empty SEQUENTIAL source renders nothing, warnings logged),
B9 (generate flat branch copies Данные/, disk-aware dedup, full rollback),
B10 (dead 'all' key + unused raw_placeholders param removed).
"""

import inspect
import logging
import os
import tempfile

import pytest

import docxforge.generate as gen_module
from docxforge.generate import (
    GenerationError,
    _resolve_folder_name_template,
    create_projects_from_template,
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer
from docxforge.engine.schema import (
    BatchSourceConfig,
    FieldMapping,
    FieldType,
    Project,
    RowIterationMode,
    TemplateConfig,
    create_projects,
)


def _make_flat_source(tmp_dir, rows, extra_data_files=()):
    """Minimal flat source project: contract.docx + clients.xlsx."""
    from docx import Document
    from openpyxl import Workbook

    project_dir = os.path.join(tmp_dir, 'flat_source')
    data_dir = os.path.join(project_dir, 'Данные')
    tmpl_dir = os.path.join(project_dir, 'Шаблоны')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tmpl_dir, exist_ok=True)

    doc = Document()
    doc.add_paragraph('Client: {{ client_name }}')
    template_path = os.path.join(tmpl_dir, 'contract.docx')
    doc.save(template_path)

    wb = Workbook()
    ws = wb.active
    ws.append(['client_name'])
    for value in rows:
        ws.append([value])
    ws_path = os.path.join(data_dir, 'clients.xlsx')
    wb.save(ws_path)
    for name in extra_data_files:
        wb2 = Workbook()
        wb2.active.append(['k'])
        wb2.active.append(['v'])
        wb2.save(os.path.join(data_dir, name))

    prj = Project()
    tc = TemplateConfig()
    tc.fields['client_name'] = FieldMapping(
        type=FieldType.TABLE, file='clients.xlsx', column='client_name')
    tc.batch_sources = {
        'clients.xlsx': BatchSourceConfig(
            file='clients.xlsx', mode=RowIterationMode.SEQUENTIAL),
    }
    prj.templates['contract.docx'] = tc
    prj.to_file(os.path.join(project_dir, 'проект.docxforge'))
    return project_dir


def _make_schema_source(tmp_dir, rows, directory_template):
    """Source project for engine-level schema.create_projects."""
    from docx import Document
    from openpyxl import Workbook

    project_dir = os.path.join(tmp_dir, 'schema_source')
    data_dir = os.path.join(project_dir, 'Данные')
    tmpl_dir = os.path.join(project_dir, 'Шаблоны')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tmpl_dir, exist_ok=True)

    doc = Document()
    doc.add_paragraph('Name: {{ name }}')
    doc.save(os.path.join(tmpl_dir, 't.docx'))

    wb = Workbook()
    ws = wb.active
    ws.append(['name'])
    for value in rows:
        ws.append([value])
    wb.save(os.path.join(data_dir, 'data.xlsx'))

    prj = Project()
    tc = TemplateConfig()
    tc.fields['name'] = FieldMapping(
        type=FieldType.TABLE, file='data.xlsx', column='name')
    tc.batch_sources = {
        'data.xlsx': BatchSourceConfig(
            file='data.xlsx', mode=RowIterationMode.SEQUENTIAL),
    }
    tc.directory_template = directory_template
    prj.templates['t.docx'] = tc
    prj.to_file(os.path.join(project_dir, 'проект.docxforge'))
    return project_dir


class TestReviewB5SchemaDirectoryTemplate:
    def test_review_schema_template_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_schema_source(tmp, ['Отчёт: 2024?*'], '{{ name }}')
            out = os.path.join(tmp, 'out')
            created = create_projects(src, out, 't.docx', 'data.xlsx')
            assert len(created) == 1
            leaf = os.path.basename(created[0])
            assert leaf == 'Отчёт_ 2024__'
            for ch in '<>:"/\\|?*':
                assert ch not in leaf

    def test_review_schema_template_unique_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_schema_source(tmp, ['Same', 'Same'], '{{ name }}')
            out = os.path.join(tmp, 'out')
            created = create_projects(src, out, 't.docx', 'data.xlsx')
            assert len(created) == 2
            assert created[0] != created[1]
            assert os.path.basename(created[1]) == 'Same_1'
            # First project kept its own row value (not overwritten).
            first = Project.from_file(
                os.path.join(created[0], 'проект.docxforge'))
            assert first.templates['t.docx'].fields['name'].value == 'Same'

    def test_review_schema_template_whitespace_tolerant(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_schema_source(tmp, ['Value'], '{{  name  }}')
            out = os.path.join(tmp, 'out')
            created = create_projects(src, out, 't.docx', 'data.xlsx')
            assert os.path.basename(created[0]) == 'Value'

    def test_review_schema_template_nested_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            from openpyxl import Workbook
            src = _make_schema_source(tmp, ['X'], '{{ name }}/sub')
            # extend data with second column for nesting check
            wb = Workbook()
            ws = wb.active
            ws.append(['name'])
            ws.append(['Top'])
            wb.save(os.path.join(src, 'Данные', 'data.xlsx'))
            out = os.path.join(tmp, 'out')
            created = create_projects(src, out, 't.docx', 'data.xlsx')
            rel = os.path.relpath(created[0], out).replace('\\', '/')
            assert rel == 'Top/sub'

    def test_review_schema_template_disk_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_schema_source(tmp, ['Dup'], '{{ name }}')
            out = os.path.join(tmp, 'out')
            os.makedirs(os.path.join(out, 'Dup'))
            created = create_projects(src, out, 't.docx', 'data.xlsx')
            assert os.path.basename(created[0]) == 'Dup_1'


class TestReviewB8EmptySequentialRendersNothing:
    def _render(self, tmp, rows):
        from docx import Document
        from openpyxl import Workbook

        data_dir = os.path.join(tmp, 'Данные')
        tmpl_dir = os.path.join(tmp, 'Шаблоны')
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(tmpl_dir, exist_ok=True)
        doc = Document()
        doc.add_paragraph('Name: {{ name }}')
        doc.save(os.path.join(tmpl_dir, 't.docx'))
        wb = Workbook()
        ws = wb.active
        ws.append(['name'])
        for value in rows:
            ws.append([value])
        wb.save(os.path.join(data_dir, 'data.xlsx'))
        prj = Project()
        tc = TemplateConfig()
        tc.fields['name'] = FieldMapping(
            type=FieldType.TABLE, file='data.xlsx', column='name')
        tc.batch_sources = {
            'data.xlsx': BatchSourceConfig(
                file='data.xlsx', mode=RowIterationMode.SEQUENTIAL),
        }
        prj.templates['t.docx'] = tc
        prj.to_file(os.path.join(tmp, 'проект.docxforge'))
        renderer = Renderer(tmp, DataReader())
        renderer.load_project()
        return renderer

    def test_review_empty_sequential_no_garbage_doc(self, caplog):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = self._render(tmp, [])
            with caplog.at_level(logging.WARNING,
                                 logger='docxforge.engine.render_execute'):
                outputs = renderer.render('t.docx', {})
            assert outputs == []
            assert any('не имеет данных' in (r.getMessage() or '')
                       for r in caplog.records)

    def test_review_nonempty_sequential_still_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = self._render(tmp, ['Alice'])
            outputs = renderer.render('t.docx', {})
            assert len(outputs) == 1
            assert os.path.exists(outputs[0])

    def test_review_generate_project_reports_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = self._render(tmp, [])  # noqa: F841 (project on disk)
            from docxforge.generate import generate_project
            with pytest.raises(GenerationError, match='No documents generated'):
                generate_project(tmp)


class TestReviewB9FlatBranch:
    def test_review_flat_copies_data_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_flat_source(tmp, ['ООО Альфа', 'ООО Бета'],
                                    extra_data_files=('reference.xlsx',))
            projects_dir, created = create_projects_from_template(
                src, 'contract.docx', '{{client_name}}')
            assert created == 2
            src_files = sorted(os.listdir(os.path.join(src, 'Данные')))
            assert len(src_files) == 2
            for proj in os.listdir(projects_dir):
                proj_dir = os.path.join(projects_dir, proj)
                if not os.path.isdir(proj_dir):
                    continue
                assert os.path.isdir(os.path.join(proj_dir, 'Данные'))
                assert os.path.isdir(os.path.join(proj_dir, 'Результат'))
                assert sorted(os.listdir(
                    os.path.join(proj_dir, 'Данные'))) == src_files
                for fname in src_files:
                    with open(os.path.join(src, 'Данные', fname), 'rb') as f:
                        expected = f.read()
                    with open(os.path.join(proj_dir, 'Данные', fname),
                              'rb') as f:
                        assert f.read() == expected

    def test_review_flat_disk_collision_gets_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_flat_source(tmp, ['ООО Альфа', 'ООО Бета'])
            projects_dir = os.path.join(src, 'Projects')
            os.makedirs(os.path.join(projects_dir, 'ООО Альфа'),
                        exist_ok=True)
            out_dir, created = create_projects_from_template(
                src, 'contract.docx', '{{client_name}}')
            assert out_dir == projects_dir
            assert created == 2
            generated = sorted(d for d in os.listdir(projects_dir)
                               if os.path.isdir(os.path.join(projects_dir, d)))
            assert 'ООО Альфа' in generated  # pre-existing, untouched
            assert 'ООО Альфа_1' in generated
            assert 'ООО Бета' in generated

    def test_review_flat_rollback_removes_all_on_failure(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_flat_source(tmp, ['ООО Альфа', 'ООО Бета'])
            calls = {'n': 0}
            real_copy = gen_module._copy_template_files

            def flaky_copy(src_template, dst_dir):
                calls['n'] += 1
                if calls['n'] >= 2:
                    raise OSError('simulated copy failure')
                return real_copy(src_template, dst_dir)

            monkeypatch.setattr(gen_module, '_copy_template_files', flaky_copy)
            with pytest.raises(GenerationError, match='Failed to copy'):
                create_projects_from_template(
                    src, 'contract.docx', '{{client_name}}')
            projects_dir = os.path.join(src, 'Projects')
            leftover = [d for d in os.listdir(projects_dir)
                        if os.path.isdir(os.path.join(projects_dir, d))]
            assert leftover == []

    def test_review_flat_duplicate_names_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _make_flat_source(tmp, ['Same', 'Same'])
            projects_dir, created = create_projects_from_template(
                src, 'contract.docx', '{{client_name}}')
            assert created == 2
            generated = sorted(d for d in os.listdir(projects_dir)
                               if os.path.isdir(os.path.join(projects_dir, d)))
            assert generated == ['Same', 'Same_1']


class TestReviewB10DeadCodeRemoved:
    def test_review_resolve_signature_without_raw_placeholders(self):
        params = list(inspect.signature(
            _resolve_folder_name_template).parameters)
        assert params == ['template', 'row_data', 'config']
        tc = TemplateConfig()
        tc.fields['client_name'] = FieldMapping(
            type=FieldType.TABLE, file='clients.xlsx', column='client_name')
        row = {'client_name': 'ООО Альфа'}
        assert _resolve_folder_name_template(
            '{{ client_name }}_договор', row, tc) == 'ООО Альфа_договор'

    def test_review_no_dead_scan_all_key(self):
        assert not hasattr(gen_module, 'scan_template')
        import pathlib
        source = pathlib.Path(gen_module.__file__).read_text(encoding='utf-8')
        assert "get('all'" not in source
        assert 'raw_placeholders' not in source
