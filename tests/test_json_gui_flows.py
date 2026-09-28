# -*- coding: utf-8 -*-
"""JSON-layer GUI flows (003): GUI <-> AJ, GUI -> PJ.

- AJ (Application JSON) is isolated per test via monkeypatched SETTINGS_FILE.
- PJ: FillForm-collected config serializes to a project file and back.

Run with: python -m pytest tests/test_json_gui_flows.py -q
"""

import json
import os

import pytest

from docxforge.generate import resolve_project_file

pytestmark = pytest.mark.gui


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Redirect the global AJ file to tmp (never touch the real Home)."""
    import docxforge.gui.main_window as main_window

    fake = str(tmp_path / 'fake_settings.json')
    monkeypatch.setattr(main_window, 'SETTINGS_FILE', fake)
    return fake


def test_gui_writes_and_reads_aj(qtbot, isolated_settings, tmp_path):
    """GUI -> AJ -> GUI: recent survives through the AJ file."""
    from docxforge.gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    proj = str(tmp_path / 'proj')
    os.makedirs(proj, exist_ok=True)
    window._add_recent(proj)

    with open(isolated_settings, encoding='utf-8') as f:
        aj = json.load(f)
    assert proj in aj.get('recent_projects', [])

    window2 = MainWindow()
    qtbot.addWidget(window2)
    assert proj in window2.recent_projects


def test_gui_collects_config_into_pj(qtbot, sample_project, tmp_path):
    """GUI -> PJ: collected fields persist to a project file and back."""
    from docxforge.engine.schema import Project
    from docxforge.gui.fill_form import FillForm

    dlg = FillForm(sample_project, 'all_fields.docx')
    qtbot.addWidget(dlg)
    config = dlg._collect_config()
    assert config.fields, 'expected collected fields'

    pj_path = str(tmp_path / 'collected.docxforge')
    project = Project.from_file(resolve_project_file(sample_project))
    project.templates['all_fields.docx'] = config
    project.to_file(pj_path)

    reloaded = Project.from_file(pj_path).templates['all_fields.docx']
    assert set(reloaded.fields) == set(config.fields)
    for name, fm in config.fields.items():
        assert reloaded.fields[name].type == fm.type
        assert reloaded.fields[name].value == fm.value
