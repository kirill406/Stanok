# -*- coding: utf-8 -*-
"""Functional tests for document generation using generate_project()."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Tuple, List

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


def read_docx_paragraphs(path: Path):
    """Extract paragraphs with formatting info from a .docx file."""
    doc = Document(path)
    paragraphs = []
    for p in doc.paragraphs:
        runs = []
        for r in p.runs:
            runs.append({
                'text': r.text,
                'bold': r.bold,
                'italic': r.italic,
                'underline': r.underline,
            })
        paragraphs.append({
            'text': p.text,
            'style': p.style.name if p.style else None,
            'runs': runs,
        })
    return paragraphs


def read_docx_tables(path: Path):
    """Extract table data from a .docx file."""
    doc = Document(path)
    tables = []
    for table in doc.tables:
        rows = []
        for row in table.rows:
            rows.append([cell.text for cell in row.cells])
        tables.append(rows)
    return tables


def compare_docx(generated_path: Path, expected_path: Path) -> Tuple[bool, List[str]]:
    """Compare two .docx files semantically.
    
    Returns:
        (is_equal, list_of_differences)
    """
    differences = []
    
    # Compare paragraphs
    gen_paragraphs = read_docx_paragraphs(generated_path)
    exp_paragraphs = read_docx_paragraphs(expected_path)
    
    if len(gen_paragraphs) != len(exp_paragraphs):
        differences.append(f'Paragraph count mismatch: generated={len(gen_paragraphs)}, expected={len(exp_paragraphs)}')
    
    for i, (gen_p, exp_p) in enumerate(zip(gen_paragraphs, exp_paragraphs)):
        if gen_p['text'] != exp_p['text']:
            differences.append(f'Paragraph {i} text mismatch: generated="{gen_p["text"]}", expected="{exp_p["text"]}"')
        if gen_p['style'] != exp_p['style']:
            differences.append(f'Paragraph {i} style mismatch: generated="{gen_p["style"]}", expected="{exp_p["style"]}"')
        
        # Compare runs (formatting)
        if len(gen_p['runs']) != len(exp_p['runs']):
            differences.append(f'Paragraph {i} run count mismatch: generated={len(gen_p["runs"])}, expected={len(exp_p["runs"])}')
        else:
            for j, (gen_r, exp_r) in enumerate(zip(gen_p['runs'], exp_p['runs'])):
                if gen_r['text'] != exp_r['text']:
                    differences.append(f'Paragraph {i}, run {j} text mismatch: generated="{gen_r["text"]}", expected="{exp_r["text"]}"')
                if gen_r['bold'] != exp_r['bold']:
                    differences.append(f'Paragraph {i}, run {j} bold mismatch: generated={gen_r["bold"]}, expected={exp_r["bold"]}')
                if gen_r['italic'] != exp_r['italic']:
                    differences.append(f'Paragraph {i}, run {j} italic mismatch: generated={gen_r["italic"]}, expected={exp_r["italic"]}')
                if gen_r['underline'] != exp_r['underline']:
                    differences.append(f'Paragraph {i}, run {j} underline mismatch: generated={gen_r["underline"]}, expected={exp_r["underline"]}')
    
    # Compare tables
    gen_tables = read_docx_tables(generated_path)
    exp_tables = read_docx_tables(expected_path)
    
    if len(gen_tables) != len(exp_tables):
        differences.append(f'Table count mismatch: generated={len(gen_tables)}, expected={len(exp_tables)}')
    
    for i, (gen_t, exp_t) in enumerate(zip(gen_tables, exp_tables)):
        if len(gen_t) != len(exp_t):
            differences.append(f'Table {i} row count mismatch: generated={len(gen_t)}, expected={len(exp_t)}')
        else:
            for r, (gen_row, exp_row) in enumerate(zip(gen_t, exp_t)):
                if gen_row != exp_row:
                    differences.append(f'Table {i}, row {r} mismatch: generated={gen_row}, expected={exp_row}')
    
    return len(differences) == 0, differences


class TestAllBasicFields:
    """Single comprehensive test for all basic field types."""

    def test_all_basic_fields_generate_correctly(self, tmp_path):
        """Test generation with constant, table, counter, today fields."""
        project = copy_fixture('all_basic_fields', tmp_path)
        
        # Generate 2 documents
        outputs = generate_project(str(project), num_docs=2)
        
        assert len(outputs) == 2
        for out in outputs:
            assert os.path.exists(out)
            assert os.path.getsize(out) > 0

        # Compare first document with expected reference
        expected_0001 = FIXTURES_DIR / 'all_basic_fields' / 'expected_0001.docx'
        assert expected_0001.exists(), f'Expected reference not found: {expected_0001}'
        
        is_equal, differences = compare_docx(Path(outputs[0]), expected_0001)
        assert is_equal, f'Document 1 does not match expected_0001:\n' + '\n'.join(differences)

        # Compare second document with expected reference
        expected_0002 = FIXTURES_DIR / 'all_basic_fields' / 'expected_0002.docx'
        assert expected_0002.exists(), f'Expected reference not found: {expected_0002}'
        
        is_equal, differences = compare_docx(Path(outputs[1]), expected_0002)
        assert is_equal, f'Document 2 does not match expected_0002:\n' + '\n'.join(differences)

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