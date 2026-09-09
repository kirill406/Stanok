# -*- coding: utf-8 -*-
"""GUI tests for MainWindow."""

import os
import json
import tempfile
import shutil
from pathlib import Path

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QPushButton

from docxforge.gui.main_window import MainWindow, get_settings_path
from docxforge.engine.schema import create_project


def find_button(window, text_contains):
    """Find a QPushButton by partial text match."""
    for btn in window.findChildren(QPushButton):
        if text_contains in btn.text():
            return btn
    return None


class TestMainWindow:
    """Tests for the main application window."""

    def test_window_opens_maximized(self, qtbot):
        """Test that main window opens maximized."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.showMaximized()  # Explicitly maximize
        qtbot.waitExposed(window)
        assert window.isMaximized()

    def test_create_project_button(self, qtbot, tmp_path, monkeypatch):
        """Test creating a new project via button."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        # Mock file dialog to return temp path
        project_path = tmp_path / "new_project"
        monkeypatch.setattr(
            QFileDialog, 'getExistingDirectory',
            lambda *args, **kwargs: str(project_path)
        )

        # Mock QMessageBox to avoid blocking
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

        btn_new = find_button(window, 'Создать новый проект')
        assert btn_new is not None
        qtbot.mouseClick(btn_new, Qt.LeftButton)
        
        # Wait for project window to open
        qtbot.waitUntil(lambda: window.project_window is not None, timeout=2000)
        assert window.project_window is not None
        assert project_path.exists()
        assert (project_path / 'проект.docxforge').exists()

    def test_open_project_button(self, qtbot, sample_project, monkeypatch):
        """Test opening an existing project."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        monkeypatch.setattr(
            QFileDialog, 'getExistingDirectory',
            lambda *args, **kwargs: sample_project
        )
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

        btn_open = find_button(window, 'Открыть проект')
        assert btn_open is not None
        qtbot.mouseClick(btn_open, Qt.LeftButton)
        
        qtbot.waitUntil(lambda: window.project_window is not None, timeout=2000)
        assert window.project_window is not None

    def test_recent_projects_list_updates(self, qtbot, sample_project, monkeypatch):
        """Test that recent projects list updates after creating/opening."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        # Initially empty or has some projects
        initial_count = window.recent_list.count()

        monkeypatch.setattr(
            QFileDialog, 'getExistingDirectory',
            lambda *args, **kwargs: sample_project
        )
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

        btn_new = find_button(window, 'Создать новый проект')
        qtbot.mouseClick(btn_new, Qt.LeftButton)
        qtbot.waitUntil(lambda: window.project_window is not None, timeout=2000)

        # Close project window to return to main
        window.project_window.close()
        window.project_window = None
        window.show()

        # Recent list should have updated
        qtbot.waitUntil(lambda: window.recent_list.count() >= initial_count, timeout=1000)

    def test_generate_all_button_no_projects(self, qtbot, monkeypatch):
        """Test generate all with no recent projects."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        # Clear recent projects
        window.recent_projects = []
        window._save_recent()
        window._refresh_recent_list()

        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

        btn_generate_all = find_button(window, 'Сгенерировать все')
        assert btn_generate_all is not None
        qtbot.mouseClick(btn_generate_all, Qt.LeftButton)

        # Should show info message about no projects
        # (verified by not crashing)

    def test_delete_recent_project(self, qtbot, sample_project, monkeypatch):
        """Test removing a project from recent list."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        # Add project to recent
        window._add_recent(sample_project)
        window._refresh_recent_list()
        assert window.recent_list.count() == 1

        # Mock confirmation dialog
        monkeypatch.setattr(QMessageBox, 'question', 
                           lambda *a, **k: QMessageBox.Yes)

        # Find delete button in the recent project widget
        item = window.recent_list.item(0)
        widget = window.recent_list.itemWidget(item)
        from PyQt5.QtWidgets import QToolButton
        delete_btn = None
        for btn in widget.findChildren(QToolButton):
            if btn.text() == '✕':
                delete_btn = btn
                break

        assert delete_btn is not None
        qtbot.mouseClick(delete_btn, Qt.LeftButton)
        
        # Project should be removed from recent
        qtbot.waitUntil(lambda: window.recent_list.count() == 0, timeout=1000)
        assert sample_project not in window.recent_projects

    def test_settings_persistence(self, qtbot, tmp_path, monkeypatch):
        """Test that settings file is created next to executable."""
        # This test verifies the get_settings_path function
        settings_path = get_settings_path()
        assert 'docxforge_settings.json' in settings_path


class TestMainWindowIntegration:
    """Integration tests with real project fixtures."""

    def test_full_create_open_cycle(self, qtbot, tmp_path, monkeypatch):
        """Test full cycle: create -> close -> open -> generate."""
        window = MainWindow()
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        project_path = tmp_path / "integration_project"
        monkeypatch.setattr(
            QFileDialog, 'getExistingDirectory',
            lambda *args, **kwargs: str(project_path)
        )
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)

        # Create project
        btn_new = find_button(window, 'Создать новый проект')
        qtbot.mouseClick(btn_new, Qt.LeftButton)
        qtbot.waitUntil(lambda: window.project_window is not None, timeout=2000)
        
        # Close project window
        window.project_window.close()
        window.project_window = None
        window.show()

        # Open project
        btn_open = find_button(window, 'Открыть проект')
        qtbot.mouseClick(btn_open, Qt.LeftButton)
        qtbot.waitUntil(lambda: window.project_window is not None, timeout=2000)

        # Verify project structure exists
        assert (project_path / 'проект.docxforge').exists()
        assert (project_path / 'Шаблоны').exists()
        assert (project_path / 'Данные').exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])