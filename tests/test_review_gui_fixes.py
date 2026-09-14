# -*- coding: utf-8 -*-
"""Regression tests for 001-review findings B1 and M13.

B1: loading a saved config with cycles/aggregations must not raise
    AttributeError, and _collect_config must preserve them (advanced
    section UI is not built in the dialog).
M13: validate_composite_template must reject multi-slash, traversal and
    empty-part templates.
"""

import os

import pytest
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtTest import QTest

from docxforge.gui.fill_form import FillForm
from docxforge.gui.strings import STRINGS
from docxforge.engine.schema import (
    AggregationFunction,
    AggregationMapping,
    CycleMapping,
    Project,
)


def _inject_cycles(dlg):
    """Put cycles/aggregations into the dialog config (as if loaded)."""
    dlg.config.cycles.append(
        CycleMapping(table='data.xlsx', columns={'field': 'column'}))
    dlg.config.aggregations['total'] = AggregationMapping(
        function=AggregationFunction.SUM, table='data.xlsx', column='price')


class TestReviewB1CyclesLoad:
    """B1: config with cycles/aggregations loads without AttributeError."""

    def test_load_existing_config_with_cycles_no_crash(self, qtbot, sample_project):
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        _inject_cycles(dlg)
        # Previously raised AttributeError via _add_cycle_row/_add_aggr_row.
        dlg._load_existing_config()
        assert len(dlg.config.cycles) == 1
        assert 'total' in dlg.config.aggregations

    def test_collect_config_preserves_cycles(self, qtbot, sample_project):
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        _inject_cycles(dlg)
        collected = dlg._collect_config()
        assert len(collected.cycles) == 1
        assert collected.cycles[0].table == 'data.xlsx'
        assert collected.cycles[0].columns == {'field': 'column'}
        assert 'total' in collected.aggregations
        assert collected.aggregations['total'].function == AggregationFunction.SUM

    def test_cycles_roundtrip_save_reload_reopen(self, qtbot, sample_project):
        """Full flow: save config with cycles, reopen dialog, no crash."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        _inject_cycles(dlg)
        collected = dlg._collect_config()
        dlg.renderer.project.templates['all_fields.docx'] = collected
        dlg.renderer.save_project()

        project_file = os.path.join(sample_project, 'проект.docxforge')
        project = Project.from_file(project_file)
        assert len(project.templates['all_fields.docx'].cycles) == 1
        assert 'total' in project.templates['all_fields.docx'].aggregations

        # Reopen: __init__ -> _load_existing_config runs with cycles on disk.
        dlg2 = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg2)
        assert len(dlg2.config.cycles) == 1
        assert 'total' in dlg2.config.aggregations


class TestReviewM13CompositeValidation:
    """M13: hardened composite template validation."""

    @pytest.mark.parametrize('template', [
        '{{employee}}/{{project_name}}',
        '{{ employee }} / {{ project_name }}',
        '{{фио_сотрудника}}/{{проект}}',
        'prefix_{{a}}/{{b}}',
    ])
    def test_validate_composite_valid_accepted(self, template):
        assert FillForm.validate_composite_template(template) == []

    @pytest.mark.parametrize('template', [
        '',
        '   ',
        '{{employee}}',
        '{{project_name}}',
        'plain/word',          # no placeholders
        '{{a}}/{{b}}/{{c}}',   # multi-slash
        'a/b/c',
        '/',
        '{{a}}/',
        '/{{b}}',
        '{{a}}/ ',
        ' /{{b}}',
        '{{ }}/{{b}}',         # empty placeholder name
        '{{a}}/{{ }}',
        '../{{b}}',            # traversal
        '{{a}}/../{{b}}',
        '{{a}}/..',
        '{{a}}\\{{b}}',        # backslash
        '{{a}}:{{b}}',         # forbidden chars (no separator either)
        '{{a}}/{{b:c}}',
        '{{a}}/*',
        '?/{{b}}',
        '{{a}}/"q"',
        '{{a}}/<b>',
    ])
    def test_validate_composite_invalid_rejected(self, template):
        assert len(FillForm.validate_composite_template(template)) >= 1

    def test_validate_composite_none_rejected(self):
        assert len(FillForm.validate_composite_template(None)) >= 1

    def test_create_blocks_traversal_template(self, qtbot, sample_project, monkeypatch):
        """Traversal template blocks creation with a warning, no Projects/."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.chk_create_projects.setChecked(True)
        QTest.qWait(50)
        dlg.edit_folder_name_template.setText('{{a}}/../{{b}}')

        warnings = []
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: warnings.append(a))
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

        dlg._create()
        QTest.qWait(200)

        assert len(warnings) >= 1
        assert not os.path.exists(os.path.join(sample_project, 'Projects'))
