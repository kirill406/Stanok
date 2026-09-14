# -*- coding: utf-8 -*-
"""M16 negatives: corrupt docx/xlsx, nested rollback, template-path cache."""
import logging
import os
import shutil
import tempfile

import pytest
from docx import Document
from openpyxl import Workbook

import docxforge.generate as gen_module
from docxforge.generate import GenerationError, create_nested_employee_projects
from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer
from docxforge.engine.schema import (
    BatchSourceConfig, FieldMapping, FieldType, Project, RowIterationMode,
    TemplateConfig,
)


def _project_with(template_bytes=None, rows=(('E1', 'P1'), ('E2', 'P2'))):
    tmp = tempfile.mkdtemp()
    data_dir = os.path.join(tmp, 'Данные')
    tmpl_dir = os.path.join(tmp, 'Шаблоны')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tmpl_dir, exist_ok=True)
    if template_bytes is None:
        doc = Document()
        doc.add_paragraph('Hi {{employee}}')
        doc.save(os.path.join(tmpl_dir, 't.docx'))
    else:
        with open(os.path.join(tmpl_dir, 't.docx'), 'wb') as f:
            f.write(template_bytes)
    wb = Workbook()
    ws = wb.active
    ws.append(['employee', 'project'])
    for emp, proj in rows:
        ws.append([emp, proj])
    wb.save(os.path.join(data_dir, 'batch.xlsx'))
    prj = Project()
    tc = TemplateConfig()
    tc.fields['employee'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='employee')
    tc.fields['project'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='project')
    tc.batch_sources = {'batch.xlsx': BatchSourceConfig(
        file='batch.xlsx', mode=RowIterationMode.SEQUENTIAL)}
    prj.templates['t.docx'] = tc
    prj.to_file(os.path.join(tmp, 'проект.docxforge'))
    return tmp


class TestM16CorruptInputs:
    def test_m16_corrupt_xlsx_yields_empty_with_error(self, caplog):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, 'broken.xlsx')
        with open(path, 'wb') as f:
            f.write(b'not a zip at all')
        with caplog.at_level(logging.ERROR,
                             logger='docxforge.engine.data_reader'):
            assert DataReader().read_excel(path) == []
        assert caplog.records

    def test_m16_corrupt_docx_render_raises_clear_error(self):
        tmp = _project_with(template_bytes=b'not a zip at all')
        renderer = Renderer(tmp, DataReader())
        renderer.load_project()
        with pytest.raises(Exception):
            renderer.render('t.docx', {})

    def test_m16_corrupt_docx_scan_raises(self):
        from docxforge.engine.template_parser import scan_template
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, 'broken.docx')
        with open(path, 'wb') as f:
            f.write(b'garbage')
        with pytest.raises(Exception):
            scan_template(path)


class TestM16NestedRollback:
    def test_m16_nested_failure_removes_partial_projects(self, monkeypatch):
        tmp = _project_with()
        real_copytree = shutil.copytree
        calls = {'n': 0}

        def flaky_copytree(src, dst, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] >= 2:
                raise OSError('simulated copy failure')
            return real_copytree(src, dst, *args, **kwargs)

        monkeypatch.setattr(shutil, 'copytree', flaky_copytree)
        # generate module uses shutil.copytree via `shutil.` attribute
        monkeypatch.setattr(gen_module.shutil, 'copytree', flaky_copytree)
        with pytest.raises(GenerationError):
            create_nested_employee_projects(
                tmp, 't.docx', '{{employee}}/{{project}}')
        projects_dir = os.path.join(tmp, 'Projects')
        leftover = os.listdir(projects_dir) if os.path.exists(
            projects_dir) else []
        assert leftover == []


class TestM17TemplatePathCache:
    def test_m17_get_template_path_cached(self, tmp_path=None):
        tmp = _project_with()
        renderer = Renderer(tmp, DataReader())
        first = renderer.get_template_path('t.docx')
        assert os.path.exists(first)
        assert renderer._template_path_cache.get('t.docx') == first
        assert renderer.get_template_path('t.docx') == first
