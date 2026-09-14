# -*- coding: utf-8 -*-
"""Tests for multi-directory selection (gui/dialogs.py + MainWindow hookup)."""
import os

import pytest
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from docxforge.gui.dialogs import (
    configure_multiselect, get_existing_directory_list,
)
from docxforge.gui.main_window import MainWindow


class TestMultiSelectDialog:
    def test_m_configure_sets_directory_multiselect(self, qtbot):
        from PyQt5.QtWidgets import QListView, QTreeView
        dlg = QFileDialog()
        qtbot.addWidget(dlg)
        configure_multiselect(dlg)
        assert dlg.fileMode() == QFileDialog.Directory
        assert dlg.testOption(QFileDialog.DontUseNativeDialog)
        list_view = dlg.findChild(QListView, 'listView')
        tree_view = dlg.findChild(QTreeView, 'treeView')
        for view in (list_view, tree_view):
            if view is not None:
                assert view.selectionMode() == view.MultiSelection

    def test_m_rejected_dialog_returns_empty(
            self, qtbot, monkeypatch):
        monkeypatch.setattr(QFileDialog, 'exec', lambda self: 0)
        assert get_existing_directory_list() == []

    def test_m_add_many_projects(self, qtbot, sample_project, tmp_path,
                                 monkeypatch):
        from docxforge.gui import dialogs as dialogs_module
        window = MainWindow()
        qtbot.addWidget(window)
        before = list(window.recent_projects)
        junk = str(tmp_path / 'not_a_project')
        os.makedirs(junk, exist_ok=True)
        monkeypatch.setattr(dialogs_module, 'get_existing_directory_list',
                            lambda *a, **k: [sample_project, junk])
        shown = []
        monkeypatch.setattr(QMessageBox, 'information',
                            lambda *a, **k: shown.append(a))
        window._add_many_projects()
        assert sample_project in window.recent_projects
        assert len(window.recent_projects) == len(before) + 1
        assert len(shown) == 1
        assert 'not_a_project' in shown[0][2]
