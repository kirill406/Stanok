# -*- coding: utf-8 -*-
"""Fill form dialog: map template fields to data sources, then render."""

import os
import re
import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QComboBox, QLineEdit, QScrollArea,
                              QWidget, QGroupBox, QCheckBox, QFrame,
                              QRadioButton, QSpinBox, QSizePolicy, QMessageBox, QMenu)
from PyQt5.QtCore import Qt, QTimer, QEvent, QObject
from PyQt5.QtGui import QFont


class _WheelEventFilter(QObject):
    """Event filter to ignore wheel events on comboboxes when not focused."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, QComboBox):
            # Only allow wheel if combobox has focus or popup is open
            if not obj.hasFocus() and not obj.view().isVisible():
                return True  # Ignore wheel event
        return False

from docxforge.engine.template_parser import scan_template
from docxforge.engine.schema import (
    TemplateConfig, FieldType,
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer

from .field_rows import FieldRowsMixin
from .advanced_section import AdvancedSectionMixin
from .batch_section import BatchSectionMixin
from .config_io import ConfigIOMixin
from .config_collector import ConfigCollectorMixin
from ..strings import STRINGS


# Composite path template placeholders (nested employee/project).
# Placeholder names are dynamic: the {{...}} before '/' is the employee
# column, the {{...}} after '/' is the project column, e.g.
# "{{фио_сотрудника}}/{{проект}}". The constants below remain as the
# canonical example; validation accepts any placeholder names.
COMPOSITE_PLACEHOLDER_EMPLOYEE = '{{employee}}'
COMPOSITE_PLACEHOLDER_PROJECT = '{{project_name}}'


class FillFormOpenError(Exception):
    """FillForm cannot open the project config or the template (B3 guard).

    Raised after an error dialog was already shown, so callers
    (e.g. ProjectWindow._open_fill_form) must only abort, not warn again.
    """


class FillForm(FieldRowsMixin, AdvancedSectionMixin, BatchSectionMixin, ConfigIOMixin, ConfigCollectorMixin, QDialog):
    def __init__(self, project_dir: str, template_rel_path: str, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.template_rel_path = template_rel_path
        self.template_path = os.path.join(project_dir, '\u0428\u0430\u0431\u043b\u043e\u043d\u044b', template_rel_path)
        self.data_reader = DataReader()
        self.renderer = Renderer(project_dir, self.data_reader)
        # B3 guards: a corrupt project config (JSONDecodeError) or a broken
        # template (BadZipFile) must show an error dialog instead of escaping
        # the constructor as an unhandled traceback.
        try:
            self.renderer.load_project()
        except Exception as e:
            logging.getLogger(__name__).exception(f'Failed to load project file: {e}')
            QMessageBox.critical(parent, STRINGS['msg_error'],
                                 STRINGS['msg_project_load_error'].format(error=e))
            raise FillFormOpenError('project load failed: %s' % e) from e

        try:
            self.scan_result = scan_template(self.template_path)
        except Exception as e:
            logging.getLogger(__name__).exception(f'Failed to scan template {self.template_path}: {e}')
            QMessageBox.critical(parent, STRINGS['msg_error'],
                                 STRINGS['msg_template_load_error'].format(error=e))
            raise FillFormOpenError('template scan failed: %s' % e) from e
        self.config = self.renderer.project.templates.get(
            template_rel_path, TemplateConfig())
        self.field_widgets = {}
        self.data_files = self._scan_data_files()
        self.columns_cache = {}

        self.setWindowTitle(STRINGS['fill_window_title'].format(template=os.path.basename(self.template_path)))
        self._autosave_enabled = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_project)

        # Wheel event filter to prevent accidental combobox changes
        self._wheel_filter = _WheelEventFilter(self)

        self._build_ui()
        self._populate_fields()
        self._load_existing_config()
        self._load_last_doc_count()
        self._connect_autosave()

        # Open maximized (full screen) - call after UI is built
        self.showMaximized()

    def _scan_data_files(self):
        data_dir = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435')
        if not os.path.exists(data_dir):
            return []
        # Filter out temporary Excel files (e.g., ~$filename.xlsx)
        return sorted([f for f in os.listdir(data_dir) 
                       if f.endswith(('.xlsx', '.xls')) and not f.startswith('~$')])

    def _load_last_doc_count(self):
        """Load last document count from main window settings and apply to spin_total_docs."""
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, '_get_last_doc_count'):
            last_count = main_window._get_last_doc_count(self.project_dir)
            if last_count and last_count > 1:
                self.spin_total_docs.setValue(last_count)
                self.chk_auto_docs.setChecked(False)
                self.spin_total_docs.setVisible(True)

    def _get_columns(self, filename):
        if filename not in self.columns_cache:
            path = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435', filename)
            if os.path.exists(path):
                try:
                    self.columns_cache[filename] = self.data_reader.get_columns(path)
                except Exception as e:
                    logging.getLogger(__name__).exception(f"Error getting columns from {filename}: {e}")
                    self.columns_cache[filename] = []
            else:
                self.columns_cache[filename] = []
        return self.columns_cache[filename]

    def _get_all_fields(self):
        """Return list of all field names in form (for linked-to combos)."""
        return list(self.field_widgets.keys())

    def _insert_field_in_filename_template(self, field_name: str):
        """Insert {{ field_name }} at cursor position in filename template edit."""
        text = self.edit_filename_template.text()
        cursor_pos = self.edit_filename_template.cursorPosition()
        field_template = f"{{{{ {field_name} }}}}"
        new_text = text[:cursor_pos] + field_template + text[cursor_pos:]
        self.edit_filename_template.setText(new_text)
        # Move cursor to after inserted field
        self.edit_filename_template.setCursorPosition(cursor_pos + len(field_template))
        self.edit_filename_template.setFocus()

    def _show_insert_field_menu(self):
        """Show popup menu with available field names for insertion."""
        fields = self._get_all_fields()
        if not fields:
            return

        menu = QMenu(self)
        for field_name in sorted(fields):
            action = menu.addAction(field_name)
            action.triggered.connect(lambda checked, fn=field_name: self._insert_field_in_filename_template(fn))

        # Show menu below the button
        btn = self.btn_insert_field
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        menu.exec_(pos)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 10)
        main_layout.setSpacing(10)

        # Header
        info = QLabel(STRINGS['fill_template_label'].format(template=os.path.basename(self.template_path)))
        info.setFont(QFont('Segoe UI', 11, QFont.Bold))
        main_layout.addWidget(info)

        placeholder_count = (len(self.scan_result['simple']) +
                           len(self.scan_result['today']) +
                           len(self.scan_result['doc_number']) +
                           len(self.scan_result['image']))
        stats = QLabel(
            STRINGS['fill_fields_count'].format(
                total=placeholder_count,
                simple=len(self.scan_result['simple']),
                today=len(self.scan_result['today']),
                counter=len(self.scan_result['doc_number']),
                image=len(self.scan_result['image'])))
        stats.setStyleSheet('color: #666;')
        main_layout.addWidget(stats)

        # Description for field mapping
        desc_label = QLabel(STRINGS['fill_field_description'])
        desc_label.setStyleSheet('color: #444; font-size: 9pt; margin-top: 4px;')
        main_layout.addWidget(desc_label)

        # + Add field button
        add_btn_layout = QHBoxLayout()
        add_btn_layout.addStretch()
        btn_add_field = QPushButton(STRINGS['fill_add_field'])
        btn_add_field.setFont(QFont('Segoe UI', 9))
        btn_add_field.clicked.connect(self._add_field_dialog)
        add_btn_layout.addWidget(btn_add_field)
        main_layout.addLayout(add_btn_layout)

        # Single scroll area for both fields and generation
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(15)

        # --- Fields section ---
        fields_group = QGroupBox(STRINGS['fill_fields_section'])
        fields_layout = QVBoxLayout(fields_group)
        fields_layout.setContentsMargins(10, 10, 10, 10)
        fields_layout.setSpacing(6)

        self.fields_widget = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_widget)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(6)

        fields_layout.addWidget(self.fields_widget)
        scroll_layout.addWidget(fields_group, stretch=1)  # Fields expand first

        # --- Generation section ---
        batch_group = QGroupBox(STRINGS['batch_generation_group'])
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setContentsMargins(10, 10, 10, 10)
        batch_layout.setSpacing(10)

# Filename template row
        self.filename_row = QHBoxLayout()
        self.lbl_filename_template = QLabel(STRINGS['fill_filename_template'])
        self.filename_row.addWidget(self.lbl_filename_template)
        self.edit_filename_template = QLineEdit()
        self.edit_filename_template.setPlaceholderText(STRINGS['fill_filename_placeholder'])
        self.edit_filename_template.setToolTip(STRINGS['fill_filename_tooltip'])
        self.filename_row.addWidget(self.edit_filename_template)
        self.btn_insert_field = QPushButton(STRINGS['fill_insert_field_btn'])
        self.btn_insert_field.setFont(QFont('Segoe UI', 9))
        self.btn_insert_field.clicked.connect(self._show_insert_field_menu)
        self.filename_row.addWidget(self.btn_insert_field)
        batch_layout.addLayout(self.filename_row)

        # Directory template row
        self.directory_row = QHBoxLayout()
        self.lbl_directory_template = QLabel(STRINGS['fill_directory_template'])
        self.directory_row.addWidget(self.lbl_directory_template)
        self.edit_directory_template = QLineEdit()
        self.edit_directory_template.setPlaceholderText(STRINGS['fill_directory_placeholder'])
        self.edit_directory_template.setToolTip(STRINGS['fill_directory_tooltip'])
        self.directory_row.addWidget(self.edit_directory_template)
        batch_layout.addLayout(self.directory_row)

        # Create projects mode row
        create_projects_row = QHBoxLayout()
        self.chk_create_projects = QCheckBox(STRINGS['fill_create_projects_checkbox'])
        self.chk_create_projects.setFont(QFont('Segoe UI', 9))
        self.chk_create_projects.toggled.connect(self._on_create_projects_toggled)
        create_projects_row.addWidget(self.chk_create_projects)
        create_projects_row.addStretch()
        batch_layout.addLayout(create_projects_row)

        # Composite path template row (initially hidden).
        # Single composite field: employee folder / project folder.
        self.folder_name_row = QHBoxLayout()
        self.lbl_folder_name_template = QLabel(STRINGS['fill_composite_template_label'])
        self.folder_name_row.addWidget(self.lbl_folder_name_template)
        self.edit_folder_name_template = QLineEdit()
        self.edit_folder_name_template.setPlaceholderText(STRINGS['fill_composite_template_placeholder'])
        self.edit_folder_name_template.setToolTip(STRINGS['fill_composite_template_tooltip'])
        self.folder_name_row.addWidget(self.edit_folder_name_template)
        batch_layout.addLayout(self.folder_name_row)
        self.folder_name_row.setContentsMargins(0, 0, 0, 0)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel(STRINGS['fill_total_docs']))
        self.spin_total_docs = QSpinBox()
        self.spin_total_docs.setMinimum(1)
        self.spin_total_docs.setMaximum(99999)
        self.spin_total_docs.setValue(1)
        self.spin_total_docs.setFixedWidth(80)
        total_row.addWidget(self.spin_total_docs)
        self.chk_auto_docs = QCheckBox(STRINGS['fill_auto_checkbox'])
        self.chk_auto_docs.setChecked(False)  # Off by default
        self.chk_auto_docs.toggled.connect(self._on_auto_docs_toggled)
        total_row.addWidget(self.chk_auto_docs)
        total_row.addStretch()
        batch_layout.addLayout(total_row)

        self.auto_info_label = QLabel('')
        self.auto_info_label.setStyleSheet('color: #888; font-size: 9pt;')
        batch_layout.addWidget(self.auto_info_label)

        self.batch_sources_container = QWidget()
        self.batch_sources_layout = QVBoxLayout(self.batch_sources_container)
        self.batch_sources_layout.setContentsMargins(0, 0, 0, 0)
        self.batch_sources_layout.setSpacing(4)
        batch_layout.addWidget(self.batch_sources_container)

        self.batch_source_widgets = {}
        self._rebuild_batch_source_rows()

        # Resume info summary (replaces the old global continue checkbox)
        resume_row = QHBoxLayout()
        self.resume_info_label = QLabel('')
        self.resume_info_label.setStyleSheet('color: #888; font-size: 9pt;')
        resume_row.addWidget(self.resume_info_label)
        resume_row.addStretch()
        batch_layout.addLayout(resume_row)

        scroll_layout.addWidget(batch_group)

        self._build_generated_project_section(scroll_layout)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        # Bottom buttons (fixed at bottom)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_validate = QPushButton(STRINGS['fill_validate_btn'])
        btn_validate.clicked.connect(self._validate)
        btn_layout.addWidget(btn_validate)
        self.btn_create = QPushButton(STRINGS['fill_create_btn'])
        self.btn_create.setMinimumWidth(120)
        self.btn_create.clicked.connect(self._create)
        btn_layout.addWidget(self.btn_create)
        main_layout.addLayout(btn_layout)

        # Set initial UI state for create projects mode
        self._set_folder_name_visible(False)

    def _set_folder_name_visible(self, visible: bool):
        """Show/hide folder name template row and toggle filename/directory rows."""
        # Folder name template row
        for i in range(self.folder_name_row.count()):
            widget = self.folder_name_row.itemAt(i).widget()
            if widget:
                widget.setVisible(visible)
        # Filename template row
        for i in range(self.filename_row.count()):
            widget = self.filename_row.itemAt(i).widget()
            if widget:
                widget.setVisible(not visible)
        # Directory template row
        for i in range(self.directory_row.count()):
            widget = self.directory_row.itemAt(i).widget()
            if widget:
                widget.setVisible(not visible)
        # Update button text
        if visible:
            self.btn_create.setText(STRINGS['fill_create_projects_btn'])
        else:
            self.btn_create.setText(STRINGS['fill_create_btn'])

    def _on_create_projects_toggled(self, checked: bool):
        """Handle create projects checkbox toggle."""
        self._set_folder_name_visible(checked)

    def _build_generated_project_section(self, scroll_layout):
        """Build the B1 section «Поля шаблона для генерируемых проектов».

        Lives at the end of the class, away from the B3-owned ``__init__``
        guard hunk. Checkboxes are synced later (fields are populated after
        ``_build_ui``) via ``_sync_generated_field_checks``.
        """
        group = QGroupBox(STRINGS['fill_generated_fields_section'])
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)
        hint = QLabel(STRINGS['fill_generated_fields_hint'])
        hint.setStyleSheet('color: #666; font-size: 9pt;')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.generated_fields_layout = QVBoxLayout()
        self.generated_fields_layout.setContentsMargins(0, 0, 0, 0)
        self.generated_fields_layout.setSpacing(2)
        layout.addLayout(self.generated_fields_layout)
        self.generated_field_checks = {}
        self.generated_fields_empty = QLabel(STRINGS['fill_generated_fields_empty'])
        self.generated_fields_empty.setStyleSheet('color: #888; font-size: 9pt;')
        self.generated_fields_layout.addWidget(self.generated_fields_empty)
        scroll_layout.addWidget(group)

    def _sync_generated_field_checks(self):
        """Ensure one checkbox per template field, preserving check states.

        Called after fields exist (end of ``_load_existing_config``) and on
        every ``_collect_config`` (covers fields added later via the dialog).
        Only adds missing boxes — never rebuilds, so focus is never stolen.
        """
        container = getattr(self, 'generated_fields_layout', None)
        if container is None:
            return
        checks = getattr(self, 'generated_field_checks', None)
        if checks is None:
            self.generated_field_checks = {}
            checks = self.generated_field_checks
        stored = set(getattr(getattr(self, 'config', None),
                             'generated_project_fields', []) or [])
        for name in sorted(self.field_widgets.keys()):
            if name in checks:
                continue
            box = QCheckBox(name)
            box.setChecked(not stored or name in stored)
            box.toggled.connect(self._schedule_save)
            container.addWidget(box)
            checks[name] = box
        if checks and hasattr(self, 'generated_fields_empty'):
            self.generated_fields_empty.setVisible(False)

    @staticmethod
    def validate_composite_template(template):
        """Validate composite path template, return list of error strings.

        Format: ``{{employee_column}}/{{project_column}}`` — the placeholder
        before ``/`` names the employee (grouping) column, the one after
        ``/`` names the project column, e.g. ``{{фио_сотрудника}}/{{проект}}``.
        Names are dynamic (any column names accepted); spaced variants such
        as ``{{ фио }}`` are also accepted.

        Exactly one ``/`` separator is required; traversal (``..``),
        backslashes and Windows-forbidden name chars (``: * ? " < > |``)
        are rejected, as are empty sides after stripping.
        """
        import re
        errors = []
        if not (template or '').strip():
            errors.append(STRINGS['msg_composite_template_required'])
            return errors
        text = template.strip()
        if '/' not in text:
            errors.append(STRINGS['msg_composite_template_required'])
            return errors
        if text.count('/') != 1:
            errors.append(STRINGS['msg_composite_single_separator'])
            return errors
        employee_part, project_part = text.split('/', 1)
        if not employee_part.strip():
            errors.append(STRINGS['msg_composite_employee_required'])
        if not project_part.strip():
            errors.append(STRINGS['msg_composite_project_required'])
        # Path traversal / separator abuse (checked on the whole template
        # so both literals and placeholder names are covered).
        if '..' in text or '\\' in text:
            errors.append(STRINGS['msg_composite_invalid_path'])
        # Forbidden Windows file-name chars in placeholder names or in the
        # literal text around them (the single '/' separator is excluded).
        names = [n.strip() for n in re.findall(r'\{\{\s*([^}]*?)\s*\}\}', text)]
        if any(any(c in ':*?"<>|' for c in name) for name in names if name):
            errors.append(STRINGS['msg_composite_invalid_path'])
        literals = re.sub(r'\{\{\s*[^}]*?\}\}', '', text).replace('/', '')
        if any(c in ':*?"<>|' for c in literals):
            if STRINGS['msg_composite_invalid_path'] not in errors:
                errors.append(STRINGS['msg_composite_invalid_path'])
        # Each side needs a non-empty {{placeholder}} (empty {{ }} rejected).
        placeholder_re = re.compile(r'\{\{\s*([^}]*?)\s*\}\}')
        emp_names = [n.strip() for n in placeholder_re.findall(employee_part)]
        proj_names = [n.strip() for n in placeholder_re.findall(project_part)]
        if not any(emp_names):
            if STRINGS['msg_composite_employee_required'] not in errors:
                errors.append(STRINGS['msg_composite_employee_required'])
        if not any(proj_names):
            if STRINGS['msg_composite_project_required'] not in errors:
                errors.append(STRINGS['msg_composite_project_required'])
        return errors
