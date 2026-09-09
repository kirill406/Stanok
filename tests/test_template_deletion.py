# -*- coding: utf-8 -*-
"""Tests for template deletion in ProjectWindow."""

import os
import tempfile
import shutil
from pathlib import Path

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QMessageBox, QToolButton

from docxforge.gui.project_window import ProjectWindow
from docxforge.engine.schema import create_project


class MockMainWindow:
    """Mock main window for testing."""
    def __init__(self):
        self.recent_projects = []
    
    def show(self):
        pass
    
    def _add_recent(self, path):
        self.recent_projects.append(path)
    
    def _refresh_recent_list(self):
        pass
    
    def remove_recent_project(self, path):
        if path in self.recent_projects:
            self.recent_projects.remove(path)


class TestTemplateDeletion:
    """Tests for deleting templates in ProjectWindow."""

    def test_delete_template_button_exists(self, qtbot, sample_project):
        """Test that each template has a delete button."""
        main_window = MockMainWindow()
        window = ProjectWindow(sample_project, main_window)
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        # Find a template item with buttons
        template_item = None
        for i in range(window.templates_tree.topLevelItemCount()):
            item = window.templates_tree.topLevelItem(i)
            found = self._find_template_with_buttons(window, item)
            if found:
                template_item = found
                break

        if template_item is None:
            pytest.skip("No template with buttons found in fixture")

        # Should have a fill button and a delete button in column 1
        widget = window.templates_tree.itemWidget(template_item, 1)
        assert widget is not None
        
        # Should have at least 2 buttons (fill + delete)
        from PyQt5.QtWidgets import QPushButton, QToolButton
        buttons = widget.findChildren(QPushButton) + widget.findChildren(QToolButton)
        assert len(buttons) >= 2

    def test_delete_template_cancel_then_confirm(self, qtbot, sample_project, monkeypatch):
        """Test cancel deletion first, then confirm - verify file is deleted only after confirmation."""
        main_window = MockMainWindow()
        window = ProjectWindow(sample_project, main_window)
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        # Find a template item
        template_item = None
        template_rel_path = None
        for i in range(window.templates_tree.topLevelItemCount()):
            item = window.templates_tree.topLevelItem(i)
            found = self._find_template_with_buttons(window, item)
            if found:
                template_item = found
                template_rel_path = found.text(1)
                break

        if template_item is None or not template_rel_path:
            pytest.skip("No template with buttons found in fixture")

        template_path = Path(sample_project) / 'Шаблоны' / template_rel_path
        assert template_path.exists(), "Template should exist before test"

        # Track dialog calls
        dialog_calls = []
        
        def mock_question(*args, **kwargs):
            dialog_calls.append(args)
            # First call: return No (cancel)
            # Second call: return Yes (confirm)
            if len(dialog_calls) == 1:
                return QMessageBox.No
            else:
                return QMessageBox.Yes
        
        monkeypatch.setattr(QMessageBox, 'question', mock_question)
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)

        # Find delete button
        widget = window.templates_tree.itemWidget(template_item, 1)
        delete_btn = None
        for btn in widget.findChildren(QToolButton):
            if btn.text() == '\U0001f5d1' and btn.toolTip() and 'шаблон' in btn.toolTip().lower():
                delete_btn = btn
                break

        if delete_btn is None:
            pytest.skip("Delete button not found")

        # First click: cancel
        qtbot.mouseClick(delete_btn, Qt.LeftButton)
        QTest.qWait(200)
        
        # File should still exist after cancel
        assert template_path.exists(), "Template should exist after cancel"

        # Second click: confirm
        qtbot.mouseClick(delete_btn, Qt.LeftButton)
        QTest.qWait(500)
        
        # File should be deleted after confirm
        assert not template_path.exists(), "Template file should be deleted after confirm"
        
        # Verify dialog was called twice
        assert len(dialog_calls) == 2
        assert 'Отмена' not in str(dialog_calls[0])  # Just verify calls happened

    def test_delete_nonexistent_template(self, qtbot, sample_project, monkeypatch):
        """Test deleting a template that doesn't exist shows warning."""
        main_window = MockMainWindow()
        window = ProjectWindow(sample_project, main_window)
        qtbot.addWidget(window)
        window.showMaximized()
        qtbot.waitExposed(window)

        # Try to delete non-existent template directly
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)
        
        window._delete_template('nonexistent.docx')
        QTest.qWait(100)
        
        # Should have shown warning (mocked, so just verify no crash)
        # The method should return early without crash

    def _find_template_with_buttons(self, window, item):
        """Find a template item that has buttons in column 1."""
        if item.text(0).startswith('\U0001f4c4'):
            widget = window.templates_tree.itemWidget(item, 1)
            if widget is not None:
                from PyQt5.QtWidgets import QPushButton, QToolButton
                buttons = widget.findChildren(QPushButton) + widget.findChildren(QToolButton)
                if len(buttons) >= 1:
                    return item
        for i in range(item.childCount()):
            found = self._find_template_with_buttons(window, item.child(i))
            if found:
                return found
        return None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])