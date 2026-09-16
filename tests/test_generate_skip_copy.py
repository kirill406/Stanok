# -*- coding: utf-8 -*-
"""Regression tests for 002 B4 «skip copy» (excluded tables).

Excluded tables are not copied into the Данные/ folder of generated
projects; the rest are copied as before. Copy flags live in
``docxforge.generate`` (new functions only); the per-table checkbox lives
in ``BatchSourceRow`` (batch_section.py).

Run with: python -m pytest tests/test_generate_skip_copy.py -v
"""

import os

import pytest

from docxforge.engine.schema import BatchSourceConfig, RowIterationMode
from docxforge.generate import copy_data_tree, get_skip_copy_tables
from docxforge.gui.strings import STRINGS


def _make_data_dir(base, files):
    src = os.path.join(base, 'Данные')
    os.makedirs(src, exist_ok=True)
    for name, content in files.items():
        with open(os.path.join(src, name), 'w', encoding='utf-8') as f:
            f.write(content)
    return src


def test_generate_skip_copy_excluded_not_copied(tmp_path):
    """Excluded tables are missing in dst, the rest are copied."""
    src = _make_data_dir(str(tmp_path), {
        'clients.xlsx': 'clients-data',
        'orders.xlsx': 'orders-data',
        'archive.xlsx': 'archive-data',
    })
    dst = os.path.join(str(tmp_path), 'out', 'Данные')
    copy_data_tree(src, dst, exclude_names={'orders.xlsx'})
    assert sorted(os.listdir(dst)) == ['archive.xlsx', 'clients.xlsx']


def test_generate_skip_copy_rest_copied_as_before(tmp_path):
    """Without excludes the copy matches the source byte-for-byte."""
    payload = {'a.xlsx': 'aaa', 'b.xlsx': 'bbb'}
    src = _make_data_dir(str(tmp_path), payload)
    dst = os.path.join(str(tmp_path), 'out', 'Данные')
    copy_data_tree(src, dst)
    assert sorted(os.listdir(dst)) == ['a.xlsx', 'b.xlsx']
    for name, content in payload.items():
        with open(os.path.join(dst, name), encoding='utf-8') as f:
            assert f.read() == content


def test_generate_skip_copy_flags_from_batch_sources():
    """Only sources flagged skip_copy are reported (getattr-based)."""
    keep = BatchSourceConfig(file='clients.xlsx',
                             mode=RowIterationMode.SEQUENTIAL)
    skip = BatchSourceConfig(file='orders.xlsx',
                             mode=RowIterationMode.SEQUENTIAL)
    skip.skip_copy = True
    skipped = get_skip_copy_tables({'clients.xlsx': keep,
                                    'orders.xlsx': skip})
    assert skipped == {'orders.xlsx'}
    assert get_skip_copy_tables({}) == set()
    assert get_skip_copy_tables(None) == set()


@pytest.mark.gui
def test_batch_skip_copy_checkbox_per_table(qtbot, sample_project):
    """Every batch table row has an unchecked «skip copy» checkbox."""
    from docxforge.gui.fill_form import FillForm
    dlg = FillForm(sample_project, 'all_fields.docx')
    qtbot.addWidget(dlg)
    assert dlg.batch_source_widgets, 'expected at least one batch table row'
    for df, widgets in dlg.batch_source_widgets.items():
        checkbox = widgets.get('chk_skip_copy')
        assert checkbox is not None, f'no skip-copy checkbox for {df}'
        assert checkbox.text() == STRINGS['batch_skip_copy']
        assert not checkbox.isChecked()
