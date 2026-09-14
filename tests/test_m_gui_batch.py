# -*- coding: utf-8 -*-
"""Regression tests for 001-review M3, M10, M11, M12 (GUI batch/settings).

M3: single engine row-count (Renderer.count_source_rows) reused by GUI.
M10: batch generation runs in GenerateWorker; cancel stops between jobs.
M11: settings live in ~/.docxforge/, migrated once from package tree.
M12: create-projects saves config only after the row-count dialog;
     engine failure restores the snapshotted config.
"""
import json
import os

import pytest
from openpyxl import load_workbook
from PyQt5.QtWidgets import QMessageBox, QInputDialog
from PyQt5.QtTest import QTest

from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer
from docxforge.gui.fill_form import FillForm
from docxforge.gui.main_window import (
    MainWindow, _migrate_settings, get_settings_path,
)
from docxforge.gui.worker import GenerateWorker


def _project_file(project_dir):
    return os.path.join(project_dir, 'проект.docxforge')


def _read_config_bytes(project_dir):
    with open(_project_file(project_dir), 'rb') as f:
        return f.read()


def _ensure_rows_and_sequential(sample_project):
    """Append rows + flip clients.xlsx source to SEQUENTIAL via widgets."""
    data_path = os.path.join(sample_project, 'Данные', 'clients.xlsx')
    wb = load_workbook(data_path)
    ws = wb.active
    ws.append(['ООО Тест1', '1', 'a'])
    ws.append(['ООО Тест2', '2', 'b'])
    wb.save(data_path)


class TestM3SingleRowCount:
    def test_m3_engine_count_matches_reader(self, sample_project):
        renderer = Renderer(sample_project, DataReader())
        renderer.load_project()
        expected = len(DataReader().read_excel(
            os.path.join(sample_project, 'Данные', 'clients.xlsx')))
        assert expected > 0
        assert renderer.count_source_rows('clients.xlsx') == expected

    def test_m3_dialog_count_uses_engine(self, qtbot, sample_project):
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        assert dlg._get_row_count('clients.xlsx') == \
            dlg.renderer.count_source_rows('clients.xlsx')

    def test_m3_missing_file_counts_zero(self, qtbot, sample_project):
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        assert dlg.renderer.count_source_rows('nope.xlsx') == 0
        assert dlg._get_row_count('nope.xlsx') == 0

    def test_m3_total_docs_uses_count(self, sample_project):
        renderer = Renderer(sample_project, DataReader())
        renderer.load_project()
        total = renderer._compute_total_docs(
            renderer.project.templates['all_fields.docx'], {})
        assert total is None  # no sequential sources in fixture


class TestM11SettingsLocation:
    def test_m11_migrate_moves_valid_file(self, tmp_path):
        legacy = tmp_path / 'old' / 'docxforge_settings.json'
        legacy.parent.mkdir(parents=True)
        payload = {'recent_projects': ['/x'], 'doc_counts': {},
                   'last_templates': {}}
        legacy.write_text(json.dumps(payload), encoding='utf-8')
        new = tmp_path / 'home' / '.docxforge' / 'docxforge_settings.json'
        assert _migrate_settings(str(legacy), str(new)) is True
        assert json.loads(new.read_text(encoding='utf-8')) == payload
        assert not legacy.exists()

    def test_m11_migrate_rejects_invalid_json(self, tmp_path):
        legacy = tmp_path / 's.json'
        legacy.write_text('{broken', encoding='utf-8')
        new = tmp_path / 'n.json'
        assert _migrate_settings(str(legacy), str(new)) is False
        assert legacy.exists()
        assert not new.exists()

    def test_m11_migrate_noop_when_new_exists(self, tmp_path):
        new = tmp_path / 'n.json'
        new.write_text('{}', encoding='utf-8')
        assert _migrate_settings(str(tmp_path / 'missing.json'),
                                 str(new)) is True

    def test_m11_path_under_home(self, tmp_path, monkeypatch):
        monkeypatch.setattr(os.path, 'expanduser',
                            lambda p: str(tmp_path) if p == '~' else p)
        path = get_settings_path()
        assert path.startswith(str(tmp_path))
        assert path.endswith('docxforge_settings.json')


class TestM10BatchWorker:
    def test_m10_worker_runs_jobs_off_thread(self, qtbot):
        seen_threads = []
        import threading
        jobs = [('a', lambda: seen_threads.append(threading.current_thread())
                 or 'r1'),
                ('b', lambda: 'r2')]
        worker = GenerateWorker(jobs)
        with qtbot.waitSignal(worker.done, timeout=5000) as blocker:
            worker.start()
        results = blocker.args[0]
        assert [label for label, _out, _err in results] == ['a', 'b']
        assert [out for _l, out, _e in results] == ['r1', 'r2']
        assert all(err is None for _l, _o, err in results)
        assert all(t is not threading.current_thread() for t in seen_threads)

    def test_m10_worker_reports_job_errors(self, qtbot):
        def boom():
            raise RuntimeError('job failed')
        worker = GenerateWorker([('bad', boom)])
        with qtbot.waitSignal(worker.done, timeout=5000) as blocker:
            worker.start()
        [(label, out, err)] = blocker.args[0]
        assert label == 'bad' and out is None and 'job failed' in err

    def test_m10_cancel_before_start_runs_nothing(self, qtbot):
        calls = []
        worker = GenerateWorker([('a', lambda: calls.append(1) or 1)])
        worker.request_cancel()
        with qtbot.waitSignal(worker.done, timeout=5000) as blocker:
            worker.start()
        assert blocker.args[0] == []
        assert calls == []

    def test_m10_cancel_between_jobs(self, qtbot):
        import threading
        gate = threading.Event()
        entered = threading.Event()

        def first():
            entered.set()
            gate.wait(10)
            return 'r1'

        worker = GenerateWorker([('a', first),
                                 ('b', lambda: 'r2'),
                                 ('c', lambda: 'r3')])
        with qtbot.waitSignal(worker.done, timeout=15000) as blocker:
            worker.start()
            assert entered.wait(10)  # job 0 is running in the worker
            worker.request_cancel()  # direct call from GUI thread
            gate.set()
        results = blocker.args[0]
        assert [label for label, _o, _e in results] == ['a']

    def test_m10_batch_success_shows_summary(
            self, qtbot, sample_project, monkeypatch):
        window = MainWindow()
        qtbot.addWidget(window)
        window.recent_projects = [sample_project]
        shown = []
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *a, **k: shown.append(a))
        window._generate_all_recent()
        qtbot.waitUntil(lambda: window._batch_worker is None, timeout=15000)
        assert len(shown) == 1
        assert 'Успешно: 1' in shown[0][2]

    def test_m10_batch_cancel_before_jobs(
            self, qtbot, sample_project, monkeypatch):
        import docxforge.generate as gen_module
        started = []
        real = gen_module.generate_project

        def gated(*args, **kwargs):
            started.append(1)
            return real(*args, **kwargs)

        monkeypatch.setattr(gen_module, 'generate_project', gated)
        window = MainWindow()
        qtbot.addWidget(window)
        window.recent_projects = [sample_project]
        shown = []
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *a, **k: shown.append(a))
        window._generate_all_recent()
        window._batch_worker.request_cancel()
        qtbot.waitUntil(lambda: window._batch_worker is None, timeout=15000)
        assert len(shown) == 1
        assert 'Обработано проектов: 0' in shown[0][2]
        assert started == []


class TestM12SaveAfterDialog:
    def _open_create_mode(self, qtbot, sample_project):
        _ensure_rows_and_sequential(sample_project)
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        bw = dlg.batch_source_widgets['clients.xlsx']
        bw['radio_sequential'].setChecked(True)
        QTest.qWait(50)
        dlg.show()
        dlg.chk_create_projects.setChecked(True)
        QTest.qWait(50)
        dlg.edit_folder_name_template.setText(
            '{{client_name}}/{{client_name}}')
        return dlg

    def test_m12_cancel_dialog_saves_nothing(
            self, qtbot, sample_project, monkeypatch):
        dlg = self._open_create_mode(qtbot, sample_project)
        before = _read_config_bytes(sample_project)
        monkeypatch.setattr(QInputDialog, 'getInt',
                            lambda *a, **k: (1, False))
        warnings = []
        monkeypatch.setattr(QMessageBox, 'warning',
                            lambda *a, **k: warnings.append(a))
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *a, **k: None)
        dlg._create()
        QTest.qWait(200)
        assert _read_config_bytes(sample_project) == before
        assert not os.path.exists(
            os.path.join(sample_project, 'Projects'))

    def test_m12_engine_failure_restores_snapshot(
            self, qtbot, sample_project, monkeypatch):
        import docxforge.generate as gen_module
        dlg = self._open_create_mode(qtbot, sample_project)
        before = _read_config_bytes(sample_project)

        def boom(*args, **kwargs):
            raise RuntimeError('simulated engine failure')

        monkeypatch.setattr(gen_module, 'create_projects_from_template', boom)
        monkeypatch.setattr(QInputDialog, 'getInt',
                            lambda *a, **k: (1, True))
        warnings = []
        monkeypatch.setattr(QMessageBox, 'warning',
                            lambda *a, **k: warnings.append(a))
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *a, **k: None)
        dlg._create()
        QTest.qWait(200)
        assert len(warnings) >= 1
        assert _read_config_bytes(sample_project) == before

    def test_m12_count_uses_engine(self, qtbot, sample_project):
        dlg = self._open_create_mode(qtbot, sample_project)
        config = dlg._collect_config()
        assert dlg._count_primary_rows(config) == \
            dlg.renderer.count_source_rows('clients.xlsx') > 1


def _make_int_column_project(tmp_path):
    """Project whose batch column holds native ints (M6 types)."""
    from docx import Document
    from openpyxl import Workbook

    from docxforge.engine.schema import (
        BatchSourceConfig, FieldMapping, FieldType, Project,
        RowIterationMode, TemplateConfig,
    )
    project_dir = str(tmp_path / 'intproj')
    data_dir = os.path.join(project_dir, 'Данные')
    tmpl_dir = os.path.join(project_dir, 'Шаблоны')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(tmpl_dir, exist_ok=True)
    doc = Document()
    doc.add_paragraph('Name: {{ name }}, Qty: {{ qty }}')
    doc.save(os.path.join(tmpl_dir, 't.docx'))
    wb = Workbook()
    ws = wb.active
    ws.append(['name', 'qty'])
    ws.append(['A', 5])
    ws.append(['B', 10])
    wb.save(os.path.join(data_dir, 'data.xlsx'))
    prj = Project()
    tc = TemplateConfig()
    tc.fields['name'] = FieldMapping(
        type=FieldType.TABLE, file='data.xlsx', column='name')
    tc.fields['qty'] = FieldMapping(
        type=FieldType.TABLE, file='data.xlsx', column='qty')
    tc.batch_sources = {'data.xlsx': BatchSourceConfig(
        file='data.xlsx', mode=RowIterationMode.CONSTANT)}
    prj.templates['t.docx'] = tc
    prj.to_file(os.path.join(project_dir, 'проект.docxforge'))
    return project_dir


class TestM6GuiDropdownTypes:
    """M6 follow-up: native cell types must not crash Qt combos.

    Regression for: TypeError "index 0 has type 'int' but 'str' is
    expected" in on_lcc when a batch column holds ints.
    """

    def test_m6_int_lookup_column_fills_str_values(
            self, qtbot, tmp_path):
        project_dir = _make_int_column_project(tmp_path)
        dlg = FillForm(project_dir, 't.docx')
        qtbot.addWidget(dlg)
        bw = dlg.batch_source_widgets['data.xlsx']
        # Would raise TypeError inside the slot before the fix.
        bw['lookup_col_combo'].setCurrentText('qty')
        QTest.qWait(100)
        lvc = bw['lookup_val_combo']
        assert lvc.count() == 2
        assert [lvc.itemText(i) for i in range(lvc.count())] == ['5', '10']

    def test_m6_int_counter_column_fills_str_values(
            self, qtbot, tmp_path):
        project_dir = _make_int_column_project(tmp_path)
        dlg = FillForm(project_dir, 't.docx')
        qtbot.addWidget(dlg)
        bw = dlg.batch_source_widgets['data.xlsx']
        bw['counter_col_combo'].setCurrentText('qty')
        QTest.qWait(100)
        ccv = bw['counter_val_combo']
        assert ccv.count() == 2
        assert [ccv.itemText(i) for i in range(ccv.count())] == ['5', '10']
        assert bw['counter_row_spin'].maximum() == 2
