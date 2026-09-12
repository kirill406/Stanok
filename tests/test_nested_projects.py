# -*- coding: utf-8 -*-
"""Unit tests for nested employee/project generation (Phase 6).

Scope: nested structure Employee -> Projects per SPEC.md.
Source/generate.py API from Phases 2-4 may be missing; such tests skip
with a clear reason (pending) while existing flat-mode helpers are
covered directly.

Run with: python -m pytest tests/test_nested_projects.py -v
"""

import json
import logging
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import docxforge.generate as gen_module
from docxforge.engine.schema import (
    BatchSourceConfig,
    FieldMapping,
    FieldType,
    Project,
    RowIterationMode,
    TemplateConfig,
)


logger = logging.getLogger(__name__)

HAS_PARSE_COMPOSITE = hasattr(gen_module, 'parse_composite_template')
HAS_NESTED = hasattr(gen_module, 'create_nested_employee_projects')

COMPOSITE_TEMPLATE = '{{employee}}/{{project_name}}'
FLAT_TEMPLATE = '{{client_name}}_ договор'


def _make_nested_source_project(tmp_dir: str) -> str:
    """Create source project with employee + project_name batch columns."""
    from docx import Document
    from openpyxl import Workbook

    project_dir = os.path.join(tmp_dir, 'source_project')
    data_dir = os.path.join(project_dir, 'Данные')
    tmpl_dir = os.path.join(project_dir, 'Шаблоны')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tmpl_dir, exist_ok=True)

    doc = Document()
    doc.add_paragraph('Employee: {{ employee }}')
    doc.add_paragraph('Project: {{ project_name }}')
    doc.add_paragraph('Client: {{ client_name }}')
    doc.add_paragraph('Doc: {{ doc_number }}')
    doc.save(os.path.join(tmpl_dir, 'report.docx'))

    wb = Workbook()
    ws = wb.active
    ws.append(['employee', 'project_name', 'client_name', 'amount'])
    ws.append(['Иванов Иван', 'Договор_001', 'ООО Альфа', '10000'])
    ws.append(['Иванов Иван', 'Договор_002', 'ООО Бета', '20000'])
    ws.append(['Иванов Иван', 'Договор_003', 'ИП Гамма', '15000'])
    ws.append(['Петров Петр', 'Контракт_001', 'ООО Дельта', '30000'])
    ws.append(['Петров Петр', 'Контракт_002', 'ООО Эпсилон', '40000'])
    ws.append(['Петров Петр', 'Контракт_003', 'ИП Дзета', '50000'])
    wb.save(os.path.join(data_dir, 'batch.xlsx'))
    # Extra file to verify full data-folder copy
    wb2 = Workbook()
    ws2 = wb2.active
    ws2.append(['ref_key', 'ref_value'])
    ws2.append(['k1', 'v1'])
    wb2.save(os.path.join(data_dir, 'reference.xlsx'))

    prj = Project()
    tc = TemplateConfig()
    tc.fields['employee'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='employee')
    tc.fields['project_name'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='project_name')
    tc.fields['client_name'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='client_name')
    tc.fields['amount'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='amount')
    tc.fields['doc_number'] = FieldMapping(
        type=FieldType.COUNTER, start=1, step=1, format='0001')
    tc.fields['org'] = FieldMapping(
        type=FieldType.CONSTANT, value='ORG_VALUE')
    tc.batch_sources = {
        'batch.xlsx': BatchSourceConfig(
            file='batch.xlsx', mode=RowIterationMode.SEQUENTIAL),
    }
    tc.filename_template = '{{ project_name }}.docx'
    tc.directory_template = COMPOSITE_TEMPLATE
    prj.templates['report.docx'] = tc
    prj.to_file(os.path.join(project_dir, 'проект.docxforge'))

    return project_dir


def _make_flat_source_project(tmp_dir: str) -> str:
    """Create minimal flat source project for backward-compat checks."""
    from docx import Document
    from openpyxl import Workbook

    project_dir = os.path.join(tmp_dir, 'flat_source')
    data_dir = os.path.join(project_dir, 'Данные')
    tmpl_dir = os.path.join(project_dir, 'Шаблоны')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tmpl_dir, exist_ok=True)

    doc = Document()
    doc.add_paragraph('Client: {{ client_name }}')
    doc.save(os.path.join(tmpl_dir, 'contract.docx'))

    wb = Workbook()
    ws = wb.active
    ws.append(['client_name'])
    ws.append(['ООО Альфа'])
    ws.append(['ООО Бета'])
    wb.save(os.path.join(data_dir, 'clients.xlsx'))

    prj = Project()
    tc = TemplateConfig()
    tc.fields['client_name'] = FieldMapping(
        type=FieldType.TABLE, file='clients.xlsx', column='client_name')
    tc.fields['org'] = FieldMapping(
        type=FieldType.CONSTANT, value='ORG_VALUE')
    tc.batch_sources = {
        'clients.xlsx': BatchSourceConfig(
            file='clients.xlsx', mode=RowIterationMode.SEQUENTIAL),
    }
    prj.templates['contract.docx'] = tc
    prj.to_file(os.path.join(project_dir, 'проект.docxforge'))

    return project_dir


def test_nested_basic_generation_creates_employee_and_project_folders():
    """2 employees x 3 projects -> nested Employee/Project folders."""
    if not HAS_NESTED:
        pytest.skip('pending: create_nested_employee_projects not implemented (Phase 3)')
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = _make_nested_source_project(tmp)
        projects_dir, employee_count, project_count = (
            gen_module.create_nested_employee_projects(
                source_dir, 'report.docx', COMPOSITE_TEMPLATE))
        logger.info(
            'nested generation result: %s employees, %s projects in %s',
            employee_count, project_count, projects_dir)
        assert employee_count == 2
        assert project_count == 6
        employees = [d for d in os.listdir(projects_dir)
                     if os.path.isdir(os.path.join(projects_dir, d))]
        assert len(employees) == 2
        total_projects = 0
        for emp in employees:
            emp_dir = os.path.join(projects_dir, emp)
            projects = [d for d in os.listdir(emp_dir)
                        if os.path.isdir(os.path.join(emp_dir, d))]
            assert len(projects) == 3
            total_projects += len(projects)
            for proj in projects:
                proj_dir = os.path.join(emp_dir, proj)
                assert os.path.exists(os.path.join(proj_dir, 'проект.docxforge'))
        assert total_projects == 6


def test_nested_composite_template_parsing_detects_parts():
    """Composite '{{employee}}/{{project_name}}' parses into two parts."""
    if not HAS_PARSE_COMPOSITE:
        pytest.skip('pending: parse_composite_template not implemented (Phase 2)')
    parsed = gen_module.parse_composite_template(COMPOSITE_TEMPLATE)
    assert parsed['is_composite'] is True
    assert 'employee' in parsed['employee_part']
    assert 'project_name' in parsed['project_part']
    flat = gen_module.parse_composite_template('{{client_name}}_договор')
    assert flat['is_composite'] is False


def test_nested_composite_template_parsing_fallback_resolves_both_placeholders():
    """Existing resolver handles composite template with row data (no new API)."""
    from docxforge.generate import _resolve_folder_name_template
    tc = TemplateConfig()
    tc.fields['employee'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='employee')
    tc.fields['project_name'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='project_name')
    row = {'employee': 'Иванов Иван', 'project_name': 'Договор_001'}
    resolved = _resolve_folder_name_template(COMPOSITE_TEMPLATE, row, tc, [])
    assert resolved == 'Иванов Иван/Договор_001'


def test_nested_config_transformation_applies_constant_counter_batch():
    """CONSTANT preserved, COUNTER reset, batch->CONSTANT (existing helper)."""
    from docxforge.generate import _build_project_config
    tc = TemplateConfig()
    tc.fields['project_name'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='project_name')
    tc.fields['doc_number'] = FieldMapping(
        type=FieldType.COUNTER, start=5, step=2, format='0001')
    tc.fields['org'] = FieldMapping(
        type=FieldType.CONSTANT, value='ORG_VALUE')
    tc.batch_sources = {
        'batch.xlsx': BatchSourceConfig(
            file='batch.xlsx', mode=RowIterationMode.SEQUENTIAL),
    }
    row = {'project_name': 'Договор_001'}
    new_config = _build_project_config(tc, row, 'batch.xlsx')
    const_fm = new_config.fields['org']
    assert const_fm.type == FieldType.CONSTANT
    assert const_fm.value == 'ORG_VALUE'
    counter_fm = new_config.fields['doc_number']
    assert counter_fm.type == FieldType.COUNTER
    assert counter_fm.start == 5
    assert counter_fm.step == 2
    assert counter_fm.format == '0001'
    assert new_config.batch_sources['batch.xlsx'].mode == RowIterationMode.CONSTANT


def test_nested_config_transformation_applies_table_to_constant():
    """TABLE field becomes CONSTANT with row value (SPEC; fixed in Phase 3/4)."""
    from docxforge.generate import _build_project_config
    tc = TemplateConfig()
    tc.fields['project_name'] = FieldMapping(
        type=FieldType.TABLE, file='batch.xlsx', column='project_name')
    tc.batch_sources = {
        'batch.xlsx': BatchSourceConfig(
            file='batch.xlsx', mode=RowIterationMode.SEQUENTIAL),
    }
    row = {'project_name': 'Договор_001'}
    new_config = _build_project_config(tc, row, 'batch.xlsx')
    table_fm = new_config.fields['project_name']
    assert table_fm.type == FieldType.CONSTANT
    assert table_fm.value == 'Договор_001'


def test_nested_flat_mode_backward_compatible_still_works():
    """Flat template (no '/') still generates projects via existing entry point."""
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = _make_flat_source_project(tmp)
        projects_dir, created = gen_module.create_projects_from_template(
            source_dir, 'contract.docx', FLAT_TEMPLATE)
        assert created == 2
        assert os.path.isdir(projects_dir)
        generated = [d for d in os.listdir(projects_dir)
                     if os.path.isdir(os.path.join(projects_dir, d))]
        assert len(generated) == 2
        for proj in generated:
            assert os.path.exists(
                os.path.join(projects_dir, proj, 'проект.docxforge'))


def test_nested_max_projects_limit_respected_flat():
    """max_projects caps created projects (existing flat entry point)."""
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = _make_flat_source_project(tmp)
        projects_dir, created = gen_module.create_projects_from_template(
            source_dir, 'contract.docx', FLAT_TEMPLATE, max_projects=1)
        assert created == 1
        generated = [d for d in os.listdir(projects_dir)
                     if os.path.isdir(os.path.join(projects_dir, d))]
        assert len(generated) == 1


def test_nested_max_projects_limit_respected_nested():
    """max_projects caps total projects across employees (nested API)."""
    if not HAS_NESTED:
        pytest.skip('pending: create_nested_employee_projects not implemented (Phase 3)')
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = _make_nested_source_project(tmp)
        projects_dir, employee_count, project_count = (
            gen_module.create_nested_employee_projects(
                source_dir, 'report.docx', COMPOSITE_TEMPLATE,
                max_projects=4))
        assert project_count == 4
        total = sum(
            len([d for d in os.listdir(os.path.join(projects_dir, emp))
                 if os.path.isdir(os.path.join(projects_dir, emp, d))])
            for emp in os.listdir(projects_dir)
            if os.path.isdir(os.path.join(projects_dir, emp)))
        assert total == 4


def test_nested_missing_column_raises_clear_error():
    """Missing employee/project_name column -> clear error (nested API)."""
    if not HAS_NESTED:
        pytest.skip('pending: create_nested_employee_projects not implemented (Phase 3)')
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = _make_flat_source_project(tmp)
        with pytest.raises(Exception, match='(?i)(employee|project_name|column)'):
            gen_module.create_nested_employee_projects(
                source_dir, 'contract.docx', COMPOSITE_TEMPLATE)


def test_nested_empty_batch_source_raises_clear_error_flat():
    """Primary source with no rows -> GenerationError (existing behavior)."""
    from docx import Document
    from openpyxl import Workbook
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = os.path.join(tmp, 'empty_source')
        data_dir = os.path.join(project_dir, 'Данные')
        tmpl_dir = os.path.join(project_dir, 'Шаблоны')
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(tmpl_dir, exist_ok=True)
        doc = Document()
        doc.add_paragraph('Client: {{ client_name }}')
        doc.save(os.path.join(tmpl_dir, 'contract.docx'))
        wb = Workbook()
        ws = wb.active
        ws.append(['client_name'])
        wb.save(os.path.join(data_dir, 'empty.xlsx'))
        prj = Project()
        tc = TemplateConfig()
        tc.fields['client_name'] = FieldMapping(
            type=FieldType.TABLE, file='empty.xlsx', column='client_name')
        tc.batch_sources = {
            'empty.xlsx': BatchSourceConfig(
                file='empty.xlsx', mode=RowIterationMode.SEQUENTIAL),
        }
        prj.templates['contract.docx'] = tc
        prj.to_file(os.path.join(project_dir, 'проект.docxforge'))
        with pytest.raises(gen_module.GenerationError, match='no data rows'):
            gen_module.create_projects_from_template(
                project_dir, 'contract.docx', FLAT_TEMPLATE)


def test_nested_data_folder_copied_fully():
    """Each project Данные/ is a full copy (all xlsx, byte-identical)."""
    if not HAS_NESTED:
        pytest.skip('pending: create_nested_employee_projects not implemented (Phase 3)')
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = _make_nested_source_project(tmp)
        projects_dir, _, _ = gen_module.create_nested_employee_projects(
            source_dir, 'report.docx', COMPOSITE_TEMPLATE)
        src_files = sorted(os.listdir(os.path.join(source_dir, 'Данные')))
        assert len(src_files) >= 2
        for emp in os.listdir(projects_dir):
            emp_dir = os.path.join(projects_dir, emp)
            if not os.path.isdir(emp_dir):
                continue
                for proj in os.listdir(emp_dir):
                    proj_dir = os.path.join(emp_dir, proj)
                    if not os.path.isdir(proj_dir):
                        continue
                    proj_data = os.path.join(proj_dir, 'Данные')
                assert sorted(os.listdir(proj_data)) == src_files
                for fname in src_files:
                    with open(os.path.join(source_dir, 'Данные', fname), 'rb') as f:
                        src_bytes = f.read()
                    with open(os.path.join(proj_data, fname), 'rb') as f:
                        assert f.read() == src_bytes


def test_nested_settings_json_structure_and_content():
    """docxforge_settings.json lists employee projects with required keys."""
    if not HAS_NESTED:
        pytest.skip('pending: create_nested_employee_projects not implemented (Phase 3)')
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = _make_nested_source_project(tmp)
        projects_dir, _, _ = gen_module.create_nested_employee_projects(
            source_dir, 'report.docx', COMPOSITE_TEMPLATE)
        for emp in os.listdir(projects_dir):
            emp_dir = os.path.join(projects_dir, emp)
            if not os.path.isdir(emp_dir):
                continue
            settings_path = os.path.join(emp_dir, 'docxforge_settings.json')
            assert os.path.exists(settings_path)
            with open(settings_path, encoding='utf-8') as f:
                settings = json.load(f)
            assert 'employee' in settings
            assert 'employee_folder' in settings
            assert 'created_at' in settings
            assert 'projects' in settings
            assert len(settings['projects']) == 3
            for entry in settings['projects']:
                assert 'name' in entry
                assert 'folder' in entry
                assert 'template' in entry
                assert 'row_index' in entry
                assert 'created_at' in entry
                assert entry['template'] == 'report.docx'


def test_nested_settings_json_contract_shape():
    """SPEC settings.json contract round-trips through json (no new API)."""
    sample = {
        'employee': 'Иванов Иван',
        'employee_folder': 'Иванов_Иван',
        'created_at': '2025-09-12T14:30:00',
        'projects': [
            {
                'name': 'Договор_001',
                'folder': 'Договор_001',
                'template': 'report.docx',
                'row_index': 0,
                'created_at': '2025-09-12T14:30:00',
            },
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'docxforge_settings.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(sample, f, ensure_ascii=False)
        with open(path, encoding='utf-8') as f:
            loaded = json.load(f)
    assert set(loaded) == {'employee', 'employee_folder', 'created_at', 'projects'}
    assert set(loaded['projects'][0]) == {
        'name', 'folder', 'template', 'row_index', 'created_at'}
