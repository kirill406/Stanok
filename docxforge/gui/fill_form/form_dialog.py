# -*- coding: utf-8 -*-
"""Fill form dialog: map template fields to data sources, then render."""

import os
import re
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QComboBox, QLineEdit, QScrollArea,
                              QWidget, QGroupBox, QCheckBox, QFrame,
                              QRadioButton, QSpinBox, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QFont


class _WheelEventFilter:
    """Event filter to ignore wheel events on comboboxes when not focused."""
    def __init__(self, parent):
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

from .constants import FIELD_TYPES, FIELD_TYPES_ENUM
from .field_rows import FieldRowsMixin
from .advanced_section import AdvancedSectionMixin
from .batch_section import BatchSectionMixin
from .config_io import ConfigIOMixin
from .config_collector import ConfigCollectorMixin
from ..strings import STRINGS


class FillForm(FieldRowsMixin, AdvancedSectionMixin, BatchSectionMixin, ConfigIOMixin, ConfigCollectorMixin, QDialog):
    def __init__(self, project_dir: str, template_rel_path: str, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.template_rel_path = template_rel_path
        self.template_path = os.path.join(project_dir, '\u0428\u0430\u0431\u043b\u043e\u043d\u044b', template_rel_path)
        self.data_reader = DataReader()
        self.renderer = Renderer(project_dir, self.data_reader)
        self.renderer.load_project()

        self.scan_result = scan_template(self.template_path)
        self.config = self.renderer.project.templates.get(
            template_rel_path, TemplateConfig())
        self.field_widgets = {}
        self.data_files = self._scan_data_files()
        self.columns_cache = {}

        self.setWindowTitle(STRINGS['fill_window_title'].format(template=os.path.basename(self.template_path)))
        # Open maximized (full screen)
        self.showMaximized()
        self._autosave_enabled = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_project)

        # Wheel event filter to prevent accidental combobox changes
        self._wheel_filter = _WheelEventFilter(self)

        self._build_ui()
        self._populate_fields()
        self._load_existing_config()
        self._connect_autosave()

    def _scan_data_files(self):
        data_dir = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435')
        if not os.path.exists(data_dir):
            return []
        # Filter out temporary Excel files (e.g., ~$filename.xlsx)
        return sorted([f for f in os.listdir(data_dir) 
                       if f.endswith(('.xlsx', '.xls')) and not f.startswith('~$')])

    def _get_columns(self, filename):
        if filename not in self.columns_cache:
            path = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435', filename)
            if os.path.exists(path):
                try:
                    self.columns_cache[filename] = self.data_reader.get_columns(path)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Error getting columns from {filename}: {e}")
                    self.columns_cache[filename] = []
            else:
                self.columns_cache[filename] = []
        return self.columns_cache[filename]

    def _get_all_fields(self):
        """Return list of all field names in form (for linked-to combos)."""
        return list(self.field_widgets.keys())

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
        fields_group = QGroupBox('\u041f\u043e\u043b\u044f \u0448\u0430\u0431\u043b\u043e\u043d\u0430')
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
        filename_row = QHBoxLayout()
        filename_row.addWidget(QLabel(STRINGS['fill_filename_template']))
        self.edit_filename_template = QLineEdit()
        self.edit_filename_template.setPlaceholderText(STRINGS['fill_filename_placeholder'])
        self.edit_filename_template.setToolTip(STRINGS['fill_filename_tooltip'])
        filename_row.addWidget(self.edit_filename_template)
        batch_layout.addLayout(filename_row)

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

        resume_row = QHBoxLayout()
        self.chk_continue = QCheckBox(STRINGS['fill_continue_checkbox'])
        self.chk_continue.setChecked(True)
        resume_row.addWidget(self.chk_continue)
        self.resume_info_label = QLabel('')
        self.resume_info_label.setStyleSheet('color: #888; font-size: 9pt;')
        resume_row.addWidget(self.resume_info_label)
        resume_row.addStretch()
        batch_layout.addLayout(resume_row)

        scroll_layout.addWidget(batch_group)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        # Bottom buttons (fixed at bottom)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_validate = QPushButton(STRINGS['fill_validate_btn'])
        btn_validate.clicked.connect(self._validate)
        btn_layout.addWidget(btn_validate)
        btn_create = QPushButton(STRINGS['fill_create_btn'])
        btn_create.setMinimumWidth(120)
        btn_create.clicked.connect(self._create)
        btn_layout.addWidget(btn_create)
        main_layout.addLayout(btn_layout)
