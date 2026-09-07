# -*- coding: utf-8 -*-
"""Functional tests for document generation using generate_project()."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from docx import Document

from docxforge.generate import generate_project, GenerationError

FIXTURES_DIR = Path(__file__).parent / 'documents'


def copy_fixture(fixture_name: str, tmp_path: Path) -> Path:
    """Copy a test fixture to a temporary directory."""
    src = FIXTURES_DIR / fixture_name
    dst = tmp_path / fixture_name
    shutil.copytree(src, dst)
    return dst


def read_docx_text(path: Path) -> str:
    """Extract all text from a .docx file."""
    doc = Document(path)
    return '\n'.join(p.text for p in doc.paragraphs)


class TestAllBasicFields:
    """Single comprehensive test for all basic field types."""

    def test_all_basic_fields_generate_correctly(self, tmp_path):
        """Test generation with constant, table, counter, today fields."""
        project = copy_fixture('all_basic_fields', tmp_path)
        
        # Generate 3 documents (10 rows in clients.xlsx, but we limit to 3)
        outputs = generate_project(str(project), num_docs=3)
        
        assert len(outputs) == 3
        for out in outputs:
            assert os.path.exists(out)
            assert os.path.getsize(out) > 0

        # Check first document
        text = read_docx_text(Path(outputs[0]))
        assert 'Документ: Договор поставки' in text  # constant
        assert 'Номер: 0001' in text  # counter starts at 1
        assert 'Клиент: Клиент 1' in text  # table from clients.xlsx row 1
        assert 'Сумма: 10000 руб.' in text  # table from clients.xlsx row 1
        assert 'Менеджер: Менеджер 1' in text  # table from managers.xlsx row 1
        assert 'Статус: Новый' in text  # constant
        # today field should have current date in dd.MM.yyyy format
        import re
        assert re.search(r'Дата: \d{2}\.\d{2}\.\d{4}', text)

        # Check second document
        text = read_docx_text(Path(outputs[1]))
        assert 'Номер: 0002' in text  # counter increments
        assert 'Клиент: Клиент 2' in text  # table from clients.xlsx row 2
        assert 'Сумма: 20000 руб.' in text
        assert 'Менеджер: Менеджер 2' in text  # table from managers.xlsx row 2

        # Check third document
        text = read_docx_text(Path(outputs[2]))
        assert 'Номер: 0003' in text
        assert 'Клиент: Клиент 3' in text
        assert 'Сумма: 30000 руб.' in text
        assert 'Менеджер: Менеджер 3' in text

    def test_counter_resume_between_calls(self, tmp_path):
        """Test that counter resumes correctly between generate calls."""
        project = copy_fixture('all_basic_fields', tmp_path)
        
        # First batch: 2 docs
        outputs1 = generate_project(str(project), num_docs=2)
        assert len(outputs1) == 2
        text1 = read_docx_text(Path(outputs1[0]))
        text2 = read_docx_text(Path(outputs1[1]))
        assert 'Номер: 0001' in text1
        assert 'Номер: 0002' in text2

        # Second batch: should continue from 0003
        outputs2 = generate_project(str(project), num_docs=2)
        assert len(outputs2) == 2
        text3 = read_docx_text(Path(outputs2[0]))
        text4 = read_docx_text(Path(outputs2[1]))
        assert 'Номер: 0003' in text3
        assert 'Номер: 0004' in text4

    def test_generate_all_rows_when_no_limit(self, tmp_path):
        """Test that all rows are generated when no num_docs limit specified."""
        project = copy_fixture('all_basic_fields', tmp_path)
        # 10 rows in clients.xlsx, no num_docs limit -> should generate 10
        outputs = generate_project(str(project))
        assert len(outputs) == 10

    def test_custom_output_directory(self, tmp_path):
        """Test custom output directory."""
        project = copy_fixture('all_basic_fields', tmp_path)
        custom_out = tmp_path / 'custom_output'
        outputs = generate_project(str(project), num_docs=2, output_dir=str(custom_out))
        
        assert len(outputs) == 2
        assert all(Path(o).parent == custom_out for o in outputs)
        assert not (project / 'output').exists()


class TestErrors:
    """Error handling."""

    def test_missing_project_file(self, tmp_path):
        with pytest.raises(GenerationError, match='Project file not found'):
            generate_project(str(tmp_path / 'nonexistent'))

    def test_missing_template_file(self, tmp_path):
        project = copy_fixture('all_basic_fields', tmp_path)
        (project / 'Шаблоны' / 'all_fields.docx').unlink()
        with pytest.raises(GenerationError, match='Template file not found'):
            generate_project(str(project))

    def test_template_not_configured(self, tmp_path):
        project = copy_fixture('all_basic_fields', tmp_path)
        with pytest.raises(GenerationError, match='Template not configured'):
            generate_project(str(project), template_name='missing.docx')

    def test_no_templates_configured(self, tmp_path):
        project = copy_fixture('all_basic_fields', tmp_path)
        import json
        config_file = project / 'проект.docxforge'
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        config['templates'] = {}
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f)
        with pytest.raises(GenerationError, match='No templates configured'):
            generate_project(str(project))


class TestCliWrapper:
    """Test CLI-friendly wrapper."""

    def test_generate_cli_returns_outputs(self, tmp_path, capsys):
        project = copy_fixture('all_basic_fields', tmp_path)
        from docxforge.generate import generate_cli

        outputs = generate_cli(str(project), count=2)

        assert len(outputs) == 2
        captured = capsys.readouterr()
        assert 'Generated: 2 document(s)' in captured.out


if __name__ == '__main__':
    pytest.main([__file__, '-v'])