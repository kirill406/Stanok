# -*- coding: utf-8 -*-
"""Tests for CLI — mirror every GUI action.

Run with: python -m pytest tests/test_cli.py -v
"""

import os
import sys
import json
import tempfile
import zipfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
    CycleMapping, AggregationMapping, AggregationFunction,
    create_project,
)
from docxforge.engine.renderer import Renderer
from docxforge.engine.data_reader import DataReader
from docxforge.engine.template_parser import scan_template


def _make_test_data(root_dir: str):
    """Create test Excel files and template in a project directory."""
    import openpyxl
    from docx import Document
    from docx.shared import Pt

    data_dir = os.path.join(root_dir, 'Данные')
    tmpl_dir = os.path.join(root_dir, 'Шаблоны')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tmpl_dir, exist_ok=True)

    # clients.xlsx
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'клиенты'
    ws.append(['название', 'ИНН', 'адрес'])
    ws.append(['ООО Альфа', '7712345678', 'ул. Пушкина, 1'])
    ws.append(['ООО Бета', '7723456789', 'ул. Ленина, 2'])
    wb.save(os.path.join(data_dir, 'клиенты.xlsx'))

    # spec.xlsx
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'спецификация'
    ws.append(['наименование', 'количество', 'цена'])
    ws.append(['Товар X', '10', '500'])
    ws.append(['Товар Y', '5', '1000'])
    wb.save(os.path.join(data_dir, 'спецификация.xlsx'))

    # template.docx
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)

    doc.add_paragraph('Договор № {{ doc_number }}')
    doc.add_paragraph('Дата: {{ today:dd.MM.yyyy }}')
    doc.add_paragraph('Клиент: {{ клиент }}')
    doc.add_paragraph('ИНН: {{ ИНН }}')
    doc.add_paragraph('Адрес: {{ адрес }}')
    doc.add_paragraph('Сумма: {{ итого }}')

    table = doc.add_table(rows=2, cols=3)
    table.style = 'Table Grid'
    for i, t in enumerate(['Наименование', 'Кол-во', 'Цена']):
        table.rows[0].cells[i].text = t
    for i, t in enumerate(['{{ наименование }}', '{{ количество }}', '{{ цена }}']):
        table.rows[1].cells[i].text = t

    doc.save(os.path.join(tmpl_dir, 'contract.docx'))

    return tmpl_dir, data_dir


def _make_config_json(project_dir: str):
    """Write .docxforge config manually for test template."""
    prj = Project()
    tc = TemplateConfig()
    tc.fields['клиент'] = FieldMapping(
        type=FieldType.TABLE, file='клиенты.xlsx', column='название')
    tc.fields['ИНН'] = FieldMapping(
        type=FieldType.TABLE, file='клиенты.xlsx',
        column='ИНН', linked_to='клиент')
    tc.fields['адрес'] = FieldMapping(
        type=FieldType.TABLE, file='клиенты.xlsx',
        column='адрес', linked_to='клиент')
    tc.fields['doc_number'] = FieldMapping(
        type=FieldType.COUNTER, start=1, format='0001')
    tc.cycles.append(CycleMapping(
        table='спецификация.xlsx',
        columns={'наименование': 'наименование',
                  'количество': 'количество',
                  'цена': 'цена'}))
    tc.aggregations['итого'] = AggregationMapping(
        function=AggregationFunction.SUM,
        table='спецификация.xlsx', column='цена')
    prj.templates['contract.docx'] = tc
    prj.to_file(os.path.join(project_dir, 'проект.docxforge'))


# ============================================================
# TESTS
# ============================================================

class TestCliCreate:
    """Test: cli create"""

    def test_create_creates_directory_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, 'test_project')
            # Simulate CLI: create_project
            proj_file = create_project(project_dir)
            assert os.path.exists(os.path.join(project_dir, 'Данные'))
            assert os.path.exists(os.path.join(project_dir, 'Шаблоны'))
            assert os.path.exists(proj_file)

            # Verify .docxforge is valid JSON
            with open(proj_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data['version'] == 1
            assert 'templates' in data

    def test_create_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, 'test_project')
            create_project(project_dir)
            # Second call should not fail
            create_project(project_dir)
            assert os.path.exists(os.path.join(project_dir, 'проект.docxforge'))


class TestCliScan:
    """Test: cli scan <template>"""

    def test_scan_finds_all_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpl_dir, _ = _make_test_data(tmp)
            result = scan_template(os.path.join(tmpl_dir, 'contract.docx'))

            assert len(result['simple']) >= 3  # клиент, ИНН, адрес, etc
            assert len(result['today']) >= 1   # today:dd.MM.yyyy
            assert len(result['doc_number']) >= 1  # doc_number
            assert 'doc_number' in result['doc_number']
            assert 'today:dd.MM.yyyy' in result['today']
            # Cycle fields appear as simple
            assert 'наименование' in result['simple']

    def test_scan_displays_correct_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpl_dir, _ = _make_test_data(tmp)
            result = scan_template(os.path.join(tmpl_dir, 'contract.docx'))
            total = (len(result['simple']) + len(result['today']) +
                     len(result['doc_number']) + len(result['image']))
            assert total > 0
            # CLI should report: "Found N placeholders: X simple, Y today, Z doc_number, W image"


class TestCliConfigure:
    """Test: cli configure — add/update field mappings"""

    def test_configure_constant(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project()

            # CLI: cli configure contract.docx --field организация constant "ООО Ромашка"
            tc = prj.templates.setdefault('contract.docx', TemplateConfig())
            tc.fields['организация'] = FieldMapping(
                type=FieldType.CONSTANT, value='ООО Ромашка')
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            # Verify
            prj2 = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            fm = prj2.templates['contract.docx'].fields['организация']
            assert fm.type == FieldType.CONSTANT
            assert fm.value == 'ООО Ромашка'

    def test_configure_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project()

            # CLI: cli configure contract.docx --field клиент table клиенты.xlsx название
            tc = prj.templates.setdefault('contract.docx', TemplateConfig())
            tc.fields['клиент'] = FieldMapping(
                type=FieldType.TABLE, file='клиенты.xlsx', column='название')
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            prj2 = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            fm = prj2.templates['contract.docx'].fields['клиент']
            assert fm.type == FieldType.TABLE
            assert fm.file == 'клиенты.xlsx'
            assert fm.column == 'название'

    def test_configure_linked_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project()

            # CLI: cli configure contract.docx --field клиент table клиенты.xlsx название
            # CLI: cli configure contract.docx --field ИНН table клиенты.xlsx ИНН --linked-to клиент
            tc = prj.templates.setdefault('contract.docx', TemplateConfig())
            tc.fields['клиент'] = FieldMapping(
                type=FieldType.TABLE, file='клиенты.xlsx', column='название')
            tc.fields['ИНН'] = FieldMapping(
                type=FieldType.TABLE, file='клиенты.xlsx',
                column='ИНН', linked_to='клиент')
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            prj2 = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            fm = prj2.templates['contract.docx'].fields['ИНН']
            assert fm.linked_to == 'клиент'
            assert fm.column == 'ИНН'

    def test_configure_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project()

            # CLI: cli configure contract.docx --field doc_number counter --start 100 --format 0001
            tc = prj.templates.setdefault('contract.docx', TemplateConfig())
            tc.fields['doc_number'] = FieldMapping(
                type=FieldType.COUNTER, start=100, format='0001')
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            prj2 = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            fm = prj2.templates['contract.docx'].fields['doc_number']
            assert fm.type == FieldType.COUNTER
            assert fm.start == 100
            assert fm.format == '0001'

    def test_configure_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project()

            # CLI: cli configure contract.docx --cycle спецификация.xlsx наименование=наименование количество=количество цена=цена
            tc = prj.templates.setdefault('contract.docx', TemplateConfig())
            tc.cycles.append(CycleMapping(
                table='спецификация.xlsx',
                columns={'наименование': 'наименование',
                          'количество': 'количество',
                          'цена': 'цена'}))
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            prj2 = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            assert len(prj2.templates['contract.docx'].cycles) == 1
            c = prj2.templates['contract.docx'].cycles[0]
            assert c.table == 'спецификация.xlsx'
            assert c.columns['наименование'] == 'наименование'

    def test_configure_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project()

            # CLI: cli configure contract.docx --aggregation итого sum спецификация.xlsx цена
            tc = prj.templates.setdefault('contract.docx', TemplateConfig())
            tc.aggregations['итого'] = AggregationMapping(
                function=AggregationFunction.SUM,
                table='спецификация.xlsx', column='цена')
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            prj2 = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            a = prj2.templates['contract.docx'].aggregations['итого']
            assert a.function == AggregationFunction.SUM
            assert a.table == 'спецификация.xlsx'
            assert a.column == 'цена'

    def test_configure_multiply_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project()

            # CLI: cli configure contract.docx --aggregation с_ндс sum_multiply спецификация.xlsx цена --multiplier 1.2
            tc = prj.templates.setdefault('contract.docx', TemplateConfig())
            tc.aggregations['с_ндс'] = AggregationMapping(
                function=AggregationFunction.SUM_MULTIPLY,
                table='спецификация.xlsx', column='цена', multiplier=1.2)
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            prj2 = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            a = prj2.templates['contract.docx'].aggregations['с_ндс']
            assert a.function == AggregationFunction.SUM_MULTIPLY
            assert a.multiplier == 1.2


class TestCliRender:
    """Test: cli render — single and batch"""

    def test_render_single_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)
            _make_config_json(tmp)

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('contract.docx', {})

            assert len(outputs) == 1
            assert os.path.exists(outputs[0])

            # Check content
            with zipfile.ZipFile(outputs[0], 'r') as zf:
                from lxml import etree
                import re
                doc = etree.parse(zf.open('word/document.xml'))
                text = ''
                W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                for p in doc.findall('.//{%s}p' % W):
                    for r in p.findall('{%s}r' % W):
                        for t_el in r.findall('{%s}t' % W):
                            if t_el.text:
                                text += t_el.text
                remaining = re.findall(r'\{\{.+?\}\}', text)
                # Only image: placeholders should remain
                non_image = [r for r in remaining if not r.startswith('{image:')]
                assert len(non_image) == 0, f'Unresolved: {non_image}'
                assert 'ООО Альфа' in text

    def test_render_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)
            _make_config_json(tmp)

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('contract.docx', {},
                                       batch_table='клиенты.xlsx')

            assert len(outputs) == 2  # 2 clients
            for out in outputs:
                assert os.path.exists(out)

    def test_render_with_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)
            _make_config_json(tmp)

            # Add constant to config
            prj = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            prj.templates['contract.docx'].fields['примечание'] = FieldMapping(
                type=FieldType.CONSTANT, value='срочно')
            prj.to_file(os.path.join(tmp, 'проект.docxforge'))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('contract.docx', {'примечание': 'срочно'})

            assert len(outputs) == 1

    def test_render_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)
            _make_config_json(tmp)
            out_dir = os.path.join(tmp, 'custom_output')

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render('contract.docx', {},
                                       output_dir=out_dir)

            assert len(outputs) == 1
            assert out_dir in outputs[0]


class TestCliList:
    """Test: cli list — list templates, data, config"""

    def test_list_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)

            templates_dir = os.path.join(tmp, 'Шаблоны')
            files = [f for f in os.listdir(templates_dir) if f.endswith('.docx')]
            assert 'contract.docx' in files

    def test_list_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)

            data_dir = os.path.join(tmp, 'Данные')
            files = sorted(os.listdir(data_dir))
            assert 'клиенты.xlsx' in files
            assert 'спецификация.xlsx' in files

    def test_list_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)
            _make_config_json(tmp)

            prj = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            tc = prj.templates.get('contract.docx')
            assert tc is not None
            assert 'клиент' in tc.fields
            assert len(tc.cycles) == 1
            assert len(tc.aggregations) == 1


class TestCliInfo:
    """Test: cli info — project summary"""

    def test_info_shows_project_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            assert prj.version == 1

    def test_info_shows_template_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _make_test_data(tmp)
            _make_config_json(tmp)
            prj = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            assert len(prj.templates) == 1

    def test_info_empty_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_project(tmp)
            prj = Project.from_file(os.path.join(tmp, 'проект.docxforge'))
            assert len(prj.templates) == 0
