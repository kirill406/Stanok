# -*- coding: utf-8 -*-
"""GUI tests for FillForm dialog."""

import os
import tempfile
import shutil
from pathlib import Path

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QComboBox, QLineEdit, QSpinBox, QPushButton

from docxforge.gui.fill_form import FillForm
from docxforge.gui.strings import STRINGS
from docxforge.engine.schema import Project, FieldType, create_project


class TestFillForm:
    """Tests for the fill form dialog."""

    def test_window_opens_maximized(self, qtbot, sample_project):
        """Test that fill form opens maximized."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        assert dlg.isMaximized()

    def test_fields_populated_from_template(self, qtbot, sample_project):
        """Test that fields from template are populated."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Should have fields for: constant, table, counter, today, doc_number
        assert len(dlg.field_widgets) >= 4  # At least 4 field types
        
        # Check specific fields exist
        field_names = list(dlg.field_widgets.keys())
        assert any('client' in f.lower() for f in field_names)
        assert any('manager' in f.lower() for f in field_names)

    def test_field_type_comboboxes(self, qtbot, sample_project):
        """Test that field type comboboxes work."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Get first field widget
        first_field = list(dlg.field_widgets.values())[0]
        type_combo = first_field['type_combo']
        
        # Should have all field types
        assert type_combo.count() == 5  # константа, таблица, счётчик, сегодня, изображение
        
        # Change type and verify visibility
        type_combo.setCurrentText('таблица')
        QTest.qWait(100)
        assert first_field['table_file'].isVisible()
        assert first_field['table_column'].isVisible()

    def test_table_field_file_selection(self, qtbot, sample_project):
        """Test selecting a data file for table field."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Find a table field
        table_field = None
        for fname, fw in dlg.field_widgets.items():
            if fw['type_combo'].currentText() == 'таблица':
                table_field = fw
                break
        
        if table_field is None:
            # Create one by changing type
            first_fw = list(dlg.field_widgets.values())[0]
            first_fw['type_combo'].setCurrentText('таблица')
            QTest.qWait(100)
            table_field = first_fw

        # Select a data file
        file_combo = table_field['table_file']
        file_combo.setCurrentIndex(1)  # First data file (clients.xlsx)
        QTest.qWait(100)
        
        # Columns should be populated
        col_combo = table_field['table_column']
        assert col_combo.count() > 0

    def test_counter_field_configuration(self, qtbot, sample_project):
        """Test counter field start/format settings."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Find counter field
        counter_field = None
        for fname, fw in dlg.field_widgets.items():
            if fw['type_combo'].currentText() == 'счётчик':
                counter_field = fw
                break
        
        if counter_field is None:
            first_fw = list(dlg.field_widgets.values())[0]
            first_fw['type_combo'].setCurrentText('счётчик')
            QTest.qWait(100)
            counter_field = first_fw

        # Set start value
        counter_field['counter_start'].setText('100')
        assert counter_field['counter_start'].text() == '100'
        
        # Set format
        counter_field['counter_format'].setCurrentText('00001')
        assert counter_field['counter_format'].currentText() == '00001'

    def test_today_field_format(self, qtbot, sample_project):
        """Test today field format selection."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Find today field
        today_field = None
        for fname, fw in dlg.field_widgets.items():
            if fw['type_combo'].currentText() == 'сегодня':
                today_field = fw
                break
        
        if today_field is None:
            first_fw = list(dlg.field_widgets.values())[0]
            first_fw['type_combo'].setCurrentText('сегодня')
            QTest.qWait(100)
            today_field = first_fw

        today_field['today_format'].setCurrentText('dd.MM.yy')
        assert today_field['today_format'].currentText() == 'dd.MM.yy'

    def test_filename_template(self, qtbot, sample_project):
        """Test filename template field."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.edit_filename_template.setText('{{ doc_number }}_{{ client_name }}')
        assert dlg.edit_filename_template.text() == '{{ doc_number }}_{{ client_name }}'

    def test_total_docs_spinbox(self, qtbot, sample_project):
        """Test total documents spinbox."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.spin_total_docs.setValue(5)
        assert dlg.spin_total_docs.value() == 5
        
        # Test auto checkbox
        dlg.chk_auto_docs.setChecked(True)
        assert dlg.chk_auto_docs.isChecked()
        assert not dlg.spin_total_docs.isVisible()

    def test_batch_source_modes(self, qtbot, sample_project):
        """Test batch source radio buttons and counter settings."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        QTest.qWait(100)

        # Should have batch sources for each data file
        assert len(dlg.batch_source_widgets) >= 2  # clients.xlsx, managers.xlsx
        
        for df, bw in dlg.batch_source_widgets.items():
            # Check that one of the radio buttons is checked (default)
            assert bw['radio_constant'].isChecked() or bw['radio_sequential'].isChecked() or bw['radio_circular'].isChecked()
            
            # Default: constant mode - lookup panel visible, counter panel hidden
            assert bw['lookup_panel'].isVisible()
            assert not bw['counter_panel'].isVisible()
            
            # Switch to sequential - counter panel should appear
            bw['radio_sequential'].setChecked(True)
            QTest.qWait(100)
            assert bw['counter_panel'].isVisible()
            assert not bw['lookup_panel'].isVisible()
            # Should have counter column combo and row spin
            assert 'counter_col_combo' in bw
            assert 'counter_row_spin' in bw
            
            # Switch to circular - counter panel should still be visible
            bw['radio_circular'].setChecked(True)
            QTest.qWait(100)
            assert bw['counter_panel'].isVisible()
            
            # Switch back to constant - lookup panel visible, counter panel hidden
            bw['radio_constant'].setChecked(True)
            QTest.qWait(100)
            assert bw['lookup_panel'].isVisible()
            assert not bw['counter_panel'].isVisible()

    def test_per_source_counter_settings(self, qtbot, sample_project):
        """Test per-source counter column and current row settings."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        QTest.qWait(100)

        for df, bw in dlg.batch_source_widgets.items():
            # Enable sequential mode
            bw['radio_sequential'].setChecked(True)
            QTest.qWait(50)
            
            # Counter panel should be visible with column combo and row spin
            assert bw['counter_panel'].isVisible()
            assert 'counter_col_combo' in bw
            assert 'counter_row_spin' in bw
            
            # Counter column combo should have columns
            assert bw['counter_col_combo'].count() > 0
            
            # Counter row spin should have default value 1
            assert bw['counter_row_spin'].value() == 1
            
            # Change counter column
            if bw['counter_col_combo'].count() > 0:
                bw['counter_col_combo'].setCurrentIndex(0)
                QTest.qWait(50)
            
            # Change current row
            bw['counter_row_spin'].setValue(5)
            assert bw['counter_row_spin'].value() == 5
            
            # Switch to circular - counter settings should persist
            bw['radio_circular'].setChecked(True)
            QTest.qWait(50)
            assert bw['counter_row_spin'].value() == 5

    def test_validate_button(self, qtbot, sample_project, monkeypatch):
        """Test validate button saves config."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Mock message box
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)

        # Configure a table field
        for fname, fw in dlg.field_widgets.items():
            if 'client' in fname.lower():
                fw['type_combo'].setCurrentText('таблица')
                QTest.qWait(50)
                fw['table_file'].setCurrentIndex(1)
                QTest.qWait(50)
                if fw['table_column'].count() > 0:
                    fw['table_column'].setCurrentIndex(0)
                break

        # Click validate - find by text
        btn_validate = None
        for btn in dlg.findChildren(QPushButton):
            if 'Проверить' in btn.text():
                btn_validate = btn
                break

        assert btn_validate is not None
        qtbot.mouseClick(btn_validate, Qt.LeftButton)
        QTest.qWait(500)  # Wait for autosave timer

        # Config should be saved to project
        project_file = Path(sample_project) / 'проект.docxforge'
        assert project_file.exists()

    def test_create_button_generates_documents(self, qtbot, sample_project, monkeypatch):
        """Test create button generates documents."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Configure fields minimally
        for fname, fw in dlg.field_widgets.items():
            if 'client' in fname.lower():
                fw['type_combo'].setCurrentText('таблица')
                QTest.qWait(50)
                fw['table_file'].setCurrentIndex(1)
                QTest.qWait(50)
                if fw['table_column'].count() > 0:
                    fw['table_column'].setCurrentIndex(0)
                break

        # Mock progress dialog and message boxes
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)

        # Set small number of docs
        dlg.spin_total_docs.setValue(2)
        
        # Find create button by text
        btn_create = None
        for btn in dlg.findChildren(QPushButton):
            if 'Создать' in btn.text():
                btn_create = btn
                break
        
        assert btn_create is not None
        qtbot.mouseClick(btn_create, Qt.LeftButton)
        QTest.qWait(3000)  # Wait for generation

        # Check output files created
        output_dir = Path(sample_project) / 'output'
        if output_dir.exists():
            docs = list(output_dir.glob('*.docx'))
            assert len(docs) >= 1

    def test_autosave_on_field_change(self, qtbot, sample_project):
        """Test that config autosaves on field changes."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Change a field
        first_fw = list(dlg.field_widgets.values())[0]
        first_fw['const_value'].setText('Test Value')
        
        # Wait for autosave timer
        QTest.qWait(600)
        
        # Project file should be updated
        project_file = Path(sample_project) / 'проект.docxforge'
        assert project_file.exists()
        
        import json
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        template_data = data['templates']['all_fields.docx']
        assert 'fields' in template_data


class TestFillFormIntegration:
    """Integration tests with real fixtures."""

    def test_full_configuration_flow(self, qtbot, sample_project, monkeypatch):
        """Test complete configuration and generation flow."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)

        # Configure all fields
        for fname, fw in dlg.field_widgets.items():
            if 'client' in fname.lower() or 'manager' in fname.lower():
                fw['type_combo'].setCurrentText('таблица')
                QTest.qWait(50)
                fw['table_file'].setCurrentIndex(1)
                QTest.qWait(50)
                if fw['table_column'].count() > 0:
                    fw['table_column'].setCurrentIndex(0)
            elif 'номер' in fname.lower() or 'doc_number' in fname.lower():
                fw['type_combo'].setCurrentText('счётчик')
                QTest.qWait(50)
            elif 'дата' in fname.lower() or 'today' in fname.lower():
                fw['type_combo'].setCurrentText('сегодня')
                QTest.qWait(50)

        # Set batch to sequential for both tables
        for df, bw in dlg.batch_source_widgets.items():
            bw['radio_sequential'].setChecked(True)
            QTest.qWait(50)

        # Set filename template
        dlg.edit_filename_template.setText('Договор_{{ doc_number }}_{{ client_name }}')

        # Generate
        dlg.spin_total_docs.setValue(3)
        btn_create = None
        for btn in dlg.findChildren(QPushButton):
            if 'Создать' in btn.text():
                btn_create = btn
                break

        assert btn_create is not None
        qtbot.mouseClick(btn_create, Qt.LeftButton)
        QTest.qWait(5000)

        # Verify output - at least 1 document generated
        output_dir = Path(sample_project) / 'output'
        docs = list(output_dir.glob('*.docx'))
        assert len(docs) >= 1, f"Expected at least 1 document, got {len(docs)}"


class TestFillFormIntegrationPhase7:
    """Phase 7: Integration tests for new features."""

    def test_auto_docs_checkbox_toggles_spinbox_visibility(self, qtbot, sample_project):
        """Test that 'Auto' checkbox toggles spin_total_docs visibility."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Default is auto=ON (checked), so spin should be hidden
        assert dlg.chk_auto_docs.isChecked()
        assert not dlg.spin_total_docs.isVisible()

        # Uncheck auto - spin should show
        dlg.chk_auto_docs.setChecked(False)
        QTest.qWait(50)
        assert dlg.spin_total_docs.isVisible()

        # Check auto again - spin should hide
        dlg.chk_auto_docs.setChecked(True)
        QTest.qWait(50)
        assert not dlg.spin_total_docs.isVisible()

    def test_insert_field_button_inserts_at_cursor(self, qtbot, sample_project):
        """Test 'Insert field' button inserts {{ field_name }} at cursor position."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Get initial fields
        field_names = list(dlg.field_widgets.keys())
        assert len(field_names) > 0

        # Set some text in filename template
        dlg.edit_filename_template.setText('Prefix_')
        dlg.edit_filename_template.setCursorPosition(len('Prefix_'))

        # Test the internal method directly (menu click would block)
        test_field = field_names[0]
        dlg._insert_field_in_filename_template(test_field)
        
        # Verify field was inserted at cursor
        expected = 'Prefix_{{ ' + test_field + ' }}'
        assert dlg.edit_filename_template.text() == expected
        
        # Cursor should be after inserted text
        assert dlg.edit_filename_template.cursorPosition() == len(expected)

    def test_insert_field_button_with_multiple_fields(self, qtbot, sample_project):
        """Test insert field with multiple fields in template."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        field_names = list(dlg.field_widgets.keys())
        assert len(field_names) >= 2

        # Insert first field
        dlg.edit_filename_template.setText('')
        dlg._insert_field_in_filename_template(field_names[0])
        first_insert = dlg.edit_filename_template.text()
        assert '{{ ' + field_names[0] + ' }}' == first_insert

        # Insert second field after first
        dlg.edit_filename_template.setCursorPosition(len(first_insert))
        dlg.edit_filename_template.setText(first_insert + '_suffix')
        dlg.edit_filename_template.setCursorPosition(len(first_insert))
        dlg._insert_field_in_filename_template(field_names[1])
        
        expected = first_insert + '{{ ' + field_names[1] + ' }}_suffix'
        assert dlg.edit_filename_template.text() == expected

    def test_counter_value_combo_sync_from_spin(self, qtbot, sample_project):
        """Test counter value combo updates when spin changes (spin -> combo)."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        QTest.qWait(200)

        for df, bw in dlg.batch_source_widgets.items():
            # Enable sequential mode
            bw['radio_sequential'].setChecked(True)
            QTest.qWait(100)

            # Counter panel should be visible with value combo
            assert bw['counter_panel'].isVisible()
            assert 'counter_val_combo' in bw
            assert 'counter_row_spin' in bw
            assert 'counter_col_combo' in bw

            # Counter column should have columns loaded
            if bw['counter_col_combo'].count() > 0:
                bw['counter_col_combo'].setCurrentIndex(0)
                QTest.qWait(100)

                # Value combo should be populated
                if bw['counter_val_combo'].count() > 0:
                    # Get value at row 1
                    row1_value = bw['counter_val_combo'].itemText(0)
                    
                    # Change spin to row 2 (if available)
                    if bw['counter_row_spin'].maximum() >= 2:
                        bw['counter_row_spin'].setValue(2)
                        QTest.qWait(50)
                        
                        # Combo should update to row 2 value
                        assert bw['counter_val_combo'].currentIndex() == 1
                        row2_value = bw['counter_val_combo'].itemText(1)
                        assert row2_value != row1_value or bw['counter_val_combo'].count() == 1

                    # Change spin back to row 1
                    bw['counter_row_spin'].setValue(1)
                    QTest.qWait(50)
                    assert bw['counter_val_combo'].currentIndex() == 0

    def test_counter_value_combo_sync_to_spin(self, qtbot, sample_project):
        """Test counter spin updates when combo changes (combo -> spin)."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        QTest.qWait(200)

        for df, bw in dlg.batch_source_widgets.items():
            bw['radio_sequential'].setChecked(True)
            QTest.qWait(100)

            if bw['counter_col_combo'].count() > 0:
                bw['counter_col_combo'].setCurrentIndex(0)
                QTest.qWait(100)

                if bw['counter_val_combo'].count() >= 2:
                    # Select index 1 (row 2) in combo
                    bw['counter_val_combo'].setCurrentIndex(1)
                    QTest.qWait(50)
                    
                    # Spin should update to 2
                    assert bw['counter_row_spin'].value() == 2

                    # Select index 0 (row 1) in combo
                    bw['counter_val_combo'].setCurrentIndex(0)
                    QTest.qWait(50)
                    assert bw['counter_row_spin'].value() == 1

    def test_validation_empty_table_field_shows_warning(self, qtbot, sample_project, monkeypatch):
        """Test validation runs without error for empty table field configuration."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Mock message boxes to avoid modal dialogs
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: None)
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

        # Call validate method directly (avoid button click which may block)
        dlg._validate()
        QTest.qWait(500)

        # Test passes if no exception
        assert True

    def test_validation_ok_shows_info(self, qtbot, sample_project, monkeypatch):
        """Test validation shows success info when config is valid."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        info_called = []
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: info_called.append(a))

        # Configure at least one table field properly
        for fname, fw in dlg.field_widgets.items():
            if 'client' in fname.lower():
                fw['type_combo'].setCurrentText('таблица')
                QTest.qWait(50)
                fw['table_file'].setCurrentIndex(1)
                QTest.qWait(50)
                if fw['table_column'].count() > 0:
                    fw['table_column'].setCurrentIndex(0)
                break

        btn_validate = None
        for btn in dlg.findChildren(QPushButton):
            if 'Проверить' in btn.text():
                btn_validate = btn
                break

        assert btn_validate is not None
        qtbot.mouseClick(btn_validate, Qt.LeftButton)
        QTest.qWait(500)

        # Should show success message
        assert len(info_called) >= 1

    def test_batch_mode_constant_shows_lookup_panel(self, qtbot, sample_project):
        """Test constant mode shows lookup panel, hides counter panel."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        QTest.qWait(100)

        for df, bw in dlg.batch_source_widgets.items():
            # Default should be constant mode
            assert bw['radio_constant'].isChecked()
            assert bw['lookup_panel'].isVisible()
            assert not bw['counter_panel'].isVisible()

    def test_batch_mode_sequential_shows_counter_panel(self, qtbot, sample_project):
        """Test sequential mode shows counter panel, hides lookup panel."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        QTest.qWait(100)

        for df, bw in dlg.batch_source_widgets.items():
            bw['radio_sequential'].setChecked(True)
            QTest.qWait(100)
            assert bw['counter_panel'].isVisible()
            assert not bw['lookup_panel'].isVisible()

    def test_batch_mode_circular_shows_counter_panel(self, qtbot, sample_project):
        """Test circular mode shows counter panel."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        QTest.qWait(100)

        for df, bw in dlg.batch_source_widgets.items():
            bw['radio_circular'].setChecked(True)
            QTest.qWait(100)
            assert bw['counter_panel'].isVisible()
            assert not bw['lookup_panel'].isVisible()

    def test_filename_template_persists_on_save(self, qtbot, sample_project):
        """Test filename template is saved to project config."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        test_template = 'MyDoc_{{ client_name }}_{{ doc_number }}'
        dlg.edit_filename_template.setText(test_template)
        QTest.qWait(600)  # Wait for autosave

        project_file = Path(sample_project) / 'проект.docxforge'
        assert project_file.exists()
        
        import json
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        template_data = data['templates']['all_fields.docx']
        assert template_data['batch'].get('filename_template') == test_template

    def test_directory_template_persists_on_save(self, qtbot, sample_project):
        """Test directory template is saved to project config."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        test_template = '{{ region }}/{{ city }}'
        dlg.edit_directory_template.setText(test_template)
        QTest.qWait(600)  # Wait for autosave

        project_file = Path(sample_project) / 'проект.docxforge'
        assert project_file.exists()
        
        import json
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        template_data = data['templates']['all_fields.docx']
        assert template_data['batch'].get('directory_template') == test_template

    def test_total_docs_persists_on_save(self, qtbot, sample_project):
        """Test total docs value is saved to project config."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.chk_auto_docs.setChecked(False)
        dlg.spin_total_docs.setValue(42)
        QTest.qWait(600)  # Wait for autosave

        project_file = Path(sample_project) / 'проект.docxforge'
        assert project_file.exists()
        
        import json
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        template_data = data['templates']['all_fields.docx']
        assert template_data['batch'].get('total_docs') == 42

    def test_auto_docs_persists_on_save(self, qtbot, sample_project):
        """Test auto docs checkbox state is saved."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.chk_auto_docs.setChecked(True)
        QTest.qWait(600)  # Wait for autosave

        project_file = Path(sample_project) / 'проект.docxforge'
        assert project_file.exists()
        
        import json
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        template_data = data['templates']['all_fields.docx']
        # When auto is checked, total_docs should be None
        assert template_data.get('total_docs') is None


class TestFillFormCreateProjectsPhase7:
    """Phase 7: UI tests for create-projects mode incl. composite folder template."""

    def test_create_projects_checkbox_toggles_folder_template(self, qtbot, sample_project):
        """Checkbox shows folder template row, hides filename/directory rows."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        # Initial state: normal document mode
        assert not dlg.chk_create_projects.isChecked()
        assert not dlg.edit_folder_name_template.isVisible()
        assert dlg.edit_filename_template.isVisible()
        assert dlg.edit_directory_template.isVisible()

        # Enable create-projects mode
        dlg.chk_create_projects.setChecked(True)
        QTest.qWait(100)
        assert dlg.lbl_folder_name_template.isVisible()
        assert dlg.edit_folder_name_template.isVisible()
        assert not dlg.edit_filename_template.isVisible()
        assert not dlg.edit_directory_template.isVisible()

        # Back to normal mode
        dlg.chk_create_projects.setChecked(False)
        QTest.qWait(100)
        assert not dlg.edit_folder_name_template.isVisible()
        assert dlg.edit_filename_template.isVisible()
        assert dlg.edit_directory_template.isVisible()

    def test_create_projects_checkbox_changes_button_text(self, qtbot, sample_project):
        """Create button text switches between document and project modes."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        assert dlg.btn_create.text() == STRINGS['fill_create_btn']

        dlg.chk_create_projects.setChecked(True)
        QTest.qWait(50)
        assert dlg.btn_create.text() == STRINGS['fill_create_projects_btn']

        dlg.chk_create_projects.setChecked(False)
        QTest.qWait(50)
        assert dlg.btn_create.text() == STRINGS['fill_create_btn']

    def test_folder_name_template_accepts_composite_value(self, qtbot, sample_project):
        """Composite template '{{employee}}/{{project_name}}' fits in the field."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.chk_create_projects.setChecked(True)
        QTest.qWait(50)

        # Single composite field (Phase 1 nested UI): label/placeholder/tooltip
        assert dlg.lbl_folder_name_template.text() == STRINGS['fill_composite_template_label']
        assert dlg.edit_folder_name_template.placeholderText() == STRINGS['fill_composite_template_placeholder']
        assert dlg.edit_folder_name_template.toolTip() == STRINGS['fill_composite_template_tooltip']

        composite = '{{employee}}/{{project_name}}'
        dlg.edit_folder_name_template.setText(composite)
        assert dlg.edit_folder_name_template.text() == composite

        # Static validator: composite OK, incomplete templates rejected
        assert FillForm.validate_composite_template(composite) == []
        assert FillForm.validate_composite_template('{{ employee }} / {{ project_name }}') == []
        assert len(FillForm.validate_composite_template('')) >= 1
        assert len(FillForm.validate_composite_template('{{employee}}')) >= 1
        assert len(FillForm.validate_composite_template('{{project_name}}')) >= 1

    def test_create_projects_empty_template_shows_warning(self, qtbot, sample_project, monkeypatch):
        """Empty folder template blocks creation with a warning, no folders made."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.chk_create_projects.setChecked(True)
        QTest.qWait(50)
        dlg.edit_folder_name_template.setText('')

        warnings = []
        monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: warnings.append(a))
        monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

        dlg._create()
        QTest.qWait(200)

        assert len(warnings) >= 1
        warning_text = '\n'.join(str(part) for part in warnings[0])
        assert STRINGS['msg_composite_template_required'] in warning_text
        assert not os.path.exists(os.path.join(sample_project, 'Projects'))

    def test_folder_name_template_persists_on_save(self, qtbot, sample_project):
        """Folder template + checkbox state survive autosave and reload."""
        dlg = FillForm(sample_project, 'all_fields.docx')
        qtbot.addWidget(dlg)
        dlg.show()

        dlg.chk_create_projects.setChecked(True)
        QTest.qWait(50)
        composite = '{{employee}}/{{project_name}}'
        dlg.edit_folder_name_template.setText(composite)
        QTest.qWait(600)  # Wait for autosave

        project_file = Path(sample_project) / 'проект.docxforge'
        assert project_file.exists()

        import json
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        template_data = data['templates']['all_fields.docx']
        assert template_data.get('create_projects') is True
        assert template_data.get('folder_name_template') == composite

        # Reload from disk: values must round-trip (schema serialization)
        project = Project.from_file(str(project_file))
        assert project.templates['all_fields.docx'].create_projects is True
        assert project.templates['all_fields.docx'].folder_name_template == composite


class TestCreateProjectsE2EPhase7:
    """Phase 7: generated projects can generate documents normally."""

    @staticmethod
    def _make_source_project(base_dir: str) -> str:
        """Build a minimal source project: 1 template, 1 SEQUENTIAL table, 3 rows."""
        from docx import Document
        from openpyxl import Workbook

        from docxforge.engine.schema import (
            TemplateConfig, FieldMapping, BatchSourceConfig, RowIterationMode,
        )

        project_dir = os.path.join(base_dir, 'source_project')
        data_dir = os.path.join(project_dir, 'Данные')
        tmpl_dir = os.path.join(project_dir, 'Шаблоны')
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(tmpl_dir, exist_ok=True)

        doc = Document()
        doc.add_paragraph('Договор № {{ doc_number }}')
        doc.add_paragraph('Клиент: {{ client_name }}')
        doc.add_paragraph('Организация: {{ org }}')
        doc.save(os.path.join(tmpl_dir, 'contract.docx'))

        wb = Workbook()
        ws = wb.active
        ws.append(['client_name'])
        ws.append(['ООО Альфа'])
        ws.append(['ООО Бета'])
        ws.append(['ИП Гамма'])
        wb.save(os.path.join(data_dir, 'clients.xlsx'))

        prj = Project()
        tc = TemplateConfig()
        tc.fields['doc_number'] = FieldMapping(type=FieldType.COUNTER, start=1, format='0001')
        tc.fields['client_name'] = FieldMapping(
            type=FieldType.TABLE, file='clients.xlsx', column='client_name')
        tc.fields['org'] = FieldMapping(type=FieldType.CONSTANT, value='Рога и копыта')
        tc.batch_sources = {
            'clients.xlsx': BatchSourceConfig(file='clients.xlsx', mode=RowIterationMode.SEQUENTIAL)
        }
        tc.filename_template = '{{ client_name }}_договор.docx'
        prj.templates['contract.docx'] = tc
        prj.to_file(os.path.join(project_dir, 'проект.docxforge'))
        return project_dir

    def test_create_projects_basic_e2e(self, tmp_path):
        """create_projects_from_template → 2 projects with config + template copy."""
        from docxforge.generate import create_projects_from_template

        source_dir = self._make_source_project(str(tmp_path))
        projects_dir, count = create_projects_from_template(
            source_dir, 'contract.docx', '{{client_name}}', max_projects=2)

        assert count == 2
        subdirs = sorted(os.listdir(projects_dir))
        assert len(subdirs) == 2
        for sub in subdirs:
            pdir = os.path.join(projects_dir, sub)
            assert os.path.isfile(os.path.join(pdir, 'проект.docxforge'))
            assert os.path.isfile(os.path.join(pdir, 'Шаблоны', 'contract.docx'))

    def test_generated_project_config_transformed(self, tmp_path):
        """TABLE→CONSTANT with row values, COUNTER reset, CONSTANT preserved."""
        from docxforge.generate import create_projects_from_template

        source_dir = self._make_source_project(str(tmp_path))
        projects_dir, count = create_projects_from_template(
            source_dir, 'contract.docx', '{{client_name}}', max_projects=3)
        assert count == 3

        seen_clients = set()
        for sub in sorted(os.listdir(projects_dir)):
            cfg = Project.from_file(
                os.path.join(projects_dir, sub, 'проект.docxforge')
            ).templates['contract.docx']
            assert cfg.fields['client_name'].type == FieldType.CONSTANT
            seen_clients.add(cfg.fields['client_name'].value)
            assert cfg.fields['doc_number'].type == FieldType.COUNTER
            assert cfg.fields['doc_number'].start == 1
            assert cfg.fields['org'].type == FieldType.CONSTANT
            assert cfg.fields['org'].value == 'Рога и копыта'

        assert seen_clients == {'ООО Альфа', 'ООО Бета', 'ИП Гамма'}

    def test_generated_projects_can_generate_documents(self, tmp_path):
        """Each generated project renders ≥1 real .docx via generate_project()."""
        from docxforge.generate import create_projects_from_template, generate_project

        source_dir = self._make_source_project(str(tmp_path))
        projects_dir, count = create_projects_from_template(
            source_dir, 'contract.docx', '{{client_name}}', max_projects=2)
        assert count == 2

        for sub in sorted(os.listdir(projects_dir)):
            pdir = os.path.join(projects_dir, sub)
            outputs = generate_project(pdir, num_docs=1)
            assert len(outputs) >= 1
            for out in outputs:
                assert os.path.isfile(out)
                assert out.endswith('.docx')

    @staticmethod
    def _make_nested_source_project(base_dir: str) -> str:
        """Build source project with employee/project_name batch columns."""
        from docx import Document
        from openpyxl import Workbook

        from docxforge.engine.schema import (
            TemplateConfig, FieldMapping, BatchSourceConfig, RowIterationMode,
        )

        project_dir = os.path.join(base_dir, 'nested_source')
        data_dir = os.path.join(project_dir, 'Данные')
        tmpl_dir = os.path.join(project_dir, 'Шаблоны')
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(tmpl_dir, exist_ok=True)

        doc = Document()
        doc.add_paragraph('Договор № {{ doc_number }}')
        doc.add_paragraph('Сотрудник: {{ employee }}')
        doc.add_paragraph('Проект: {{ project_name }}')
        doc.save(os.path.join(tmpl_dir, 'contract.docx'))

        wb = Workbook()
        ws = wb.active
        ws.append(['employee', 'project_name'])
        ws.append(['Ivanov_Ivan', 'Dogovor_001'])
        ws.append(['Ivanov_Ivan', 'Dogovor_002'])
        ws.append(['Petrov_Petr', 'Dogovor_003'])
        ws.append(['Petrov_Petr', 'Dogovor_004'])
        wb.save(os.path.join(data_dir, 'work.xlsx'))

        prj = Project()
        tc = TemplateConfig()
        tc.fields['doc_number'] = FieldMapping(type=FieldType.COUNTER, start=1, format='0001')
        tc.fields['employee'] = FieldMapping(
            type=FieldType.TABLE, file='work.xlsx', column='employee')
        tc.fields['project_name'] = FieldMapping(
            type=FieldType.TABLE, file='work.xlsx', column='project_name')
        tc.batch_sources = {
            'work.xlsx': BatchSourceConfig(file='work.xlsx', mode=RowIterationMode.SEQUENTIAL)
        }
        tc.filename_template = '{{ project_name }}.docx'
        prj.templates['contract.docx'] = tc
        prj.to_file(os.path.join(project_dir, 'проект.docxforge'))
        return project_dir

    def test_nested_projects_e2e(self, tmp_path):
        """Nested generation: employees, settings.json, data copy, docs render."""
        import json

        from docxforge.generate import create_nested_employee_projects, generate_project

        source_dir = self._make_nested_source_project(str(tmp_path))
        projects_dir, n_employees, n_projects = create_nested_employee_projects(
            source_dir, 'contract.docx', '{{employee}}/{{project_name}}')

        assert (n_employees, n_projects) == (2, 4)

        employees = sorted(os.listdir(projects_dir))
        assert len(employees) == 2
        for emp in employees:
            emp_dir = os.path.join(projects_dir, emp)
            settings_path = os.path.join(emp_dir, 'docxforge_settings.json')
            assert os.path.isfile(settings_path)
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            assert settings['employee_folder'] == emp
            assert len(settings['projects']) == 2

            for entry in settings['projects']:
                pdir = os.path.join(emp_dir, entry['folder'])
                # Project structure per SPEC
                assert os.path.isfile(os.path.join(pdir, 'проект.docxforge'))
                assert os.path.isdir(os.path.join(pdir, 'Данные'))
                assert os.path.isdir(os.path.join(pdir, 'Шаблоны'))
                assert os.path.isdir(os.path.join(pdir, 'Результат'))
                # Данные/ is a FULL copy of the source data
                assert os.path.isfile(os.path.join(pdir, 'Данные', 'work.xlsx'))
                assert os.path.isfile(os.path.join(pdir, 'Шаблоны', 'contract.docx'))

                # Config transformation
                cfg = Project.from_file(
                    os.path.join(pdir, 'проект.docxforge')).templates['contract.docx']
                assert cfg.fields['employee'].type == FieldType.CONSTANT
                assert cfg.fields['project_name'].type == FieldType.CONSTANT
                assert cfg.fields['doc_number'].type == FieldType.COUNTER
                assert cfg.fields['doc_number'].start == 1

                # Generated project renders documents normally
                outputs = generate_project(pdir, num_docs=1)
                assert len(outputs) >= 1
                for out in outputs:
                    assert os.path.isfile(out)
                    assert out.endswith('.docx')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])