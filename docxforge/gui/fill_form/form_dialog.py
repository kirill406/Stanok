# -*- coding: utf-8 -*-
"""Fill form dialog: map template fields to data sources, then render."""

import os
import re
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QComboBox, QLineEdit, QScrollArea,
                              QWidget, QGroupBox, QCheckBox, QFrame,
                              QRadioButton, QSpinBox, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

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

        self.setWindowTitle('\u0417\u0430\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435: %s' % os.path.basename(self.template_path))
        self.resize(750, 620)
        self._autosave_enabled = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save_project)

        self._build_ui()
        self._populate_fields()
        self._load_existing_config()
        self._connect_autosave()

    def _scan_data_files(self):
        data_dir = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435')
        if not os.path.exists(data_dir):
            return []
        return sorted([f for f in os.listdir(data_dir) if f.endswith(('.xlsx', '.xls'))])

    def _get_columns(self, filename):
        if filename not in self.columns_cache:
            path = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435', filename)
            if os.path.exists(path):
                self.columns_cache[filename] = self.data_reader.get_columns(path)
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
        info = QLabel('\u0428\u0430\u0431\u043b\u043e\u043d: %s' % os.path.basename(self.template_path))
        info.setFont(QFont('Segoe UI', 11, QFont.Bold))
        main_layout.addWidget(info)

        placeholder_count = (len(self.scan_result['simple']) +
                           len(self.scan_result['today']) +
                           len(self.scan_result['doc_number']) +
                           len(self.scan_result['image']))
        stats = QLabel(
            '\u041f\u043e\u043b\u0435\u0439 \u0432 \u0448\u0430\u0431\u043b\u043e\u043d\u0435: %d (%d \u043d\u0430\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0435\u043c\u044b\u0445, %d \u0434\u0430\u0442, %d \u043d\u043e\u043c\u0435\u0440\u043e\u0432, %d \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0439)' %
            (placeholder_count, len(self.scan_result['simple']),
             len(self.scan_result['today']), len(self.scan_result['doc_number']),
             len(self.scan_result['image'])))
        stats.setStyleSheet('color: #666;')
        main_layout.addWidget(stats)

        # + Add field button
        add_btn_layout = QHBoxLayout()
        add_btn_layout.addStretch()
        btn_add_field = QPushButton('+ \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u043f\u043e\u043b\u0435')
        btn_add_field.setFont(QFont('Segoe UI', 9))
        btn_add_field.clicked.connect(self._add_field_dialog)
        add_btn_layout.addWidget(btn_add_field)
        main_layout.addLayout(add_btn_layout)

        # Scrollable field list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.fields_widget = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_widget)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(6)

        scroll.setWidget(self.fields_widget)
        main_layout.addWidget(scroll, stretch=1)

        # Advanced section
        self.advanced_group = QGroupBox('\u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u043e: \u0446\u0438\u043a\u043b\u044b \u0438 \u0430\u0433\u0440\u0435\u0433\u0430\u0446\u0438\u0438')
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        self.advanced_layout = QVBoxLayout(self.advanced_group)

        self.cycles_widget = QWidget()
        self.cycles_layout = QVBoxLayout(self.cycles_widget)
        self.advanced_layout.addWidget(self.cycles_widget)

        self.btn_add_cycle = QPushButton('+ \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0446\u0438\u043a\u043b')
        self.btn_add_cycle.clicked.connect(self._add_cycle_row)
        self.advanced_layout.addWidget(self.btn_add_cycle)

        self.aggr_widget = QWidget()
        self.aggr_layout = QVBoxLayout(self.aggr_widget)
        self.advanced_layout.addWidget(self.aggr_widget)

        self.btn_add_aggr = QPushButton('+ \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0430\u0433\u0440\u0435\u0433\u0430\u0446\u0438\u044e')
        self.btn_add_aggr.clicked.connect(self._add_aggr_row)
        self.advanced_layout.addWidget(self.btn_add_aggr)

        self.btn_add_cycle.setVisible(False)
        self.btn_add_aggr.setVisible(False)
        self.cycles_widget.setVisible(False)
        self.aggr_widget.setVisible(False)

        self.advanced_group.toggled.connect(self._on_advanced_toggled)

        main_layout.addWidget(self.advanced_group)

        # Generation section
        batch_group = QGroupBox('\u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f')
        batch_layout = QVBoxLayout(batch_group)

        # Filename template row
        filename_row = QHBoxLayout()
        filename_row.addWidget(QLabel('\u0428\u0430\u0431\u043b\u043e\u043d \u0438\u043c\u0435\u043d\u0438 \u0444\u0430\u0439\u043b\u0430:'))
        self.edit_filename_template = QLineEdit()
        self.edit_filename_template.setPlaceholderText('{{ doc_number }}_{{ client_name }} (пусто = авто)')
        self.edit_filename_template.setToolTip('Используйте {{ field_name }} для подстановки значений полей. Пусто = автоматическое именование.')
        filename_row.addWidget(self.edit_filename_template)
        batch_layout.addLayout(filename_row)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel('\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432:'))
        self.spin_total_docs = QSpinBox()
        self.spin_total_docs.setMinimum(1)
        self.spin_total_docs.setMaximum(99999)
        self.spin_total_docs.setValue(1)
        self.spin_total_docs.setFixedWidth(80)
        total_row.addWidget(self.spin_total_docs)
        self.chk_auto_docs = QCheckBox('\u0410\u0432\u0442\u043e')
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
        self.chk_continue = QCheckBox('\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u0441 \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0435\u0439 \u0441\u0442\u0440\u043e\u043a\u0438')
        self.chk_continue.setChecked(True)
        resume_row.addWidget(self.chk_continue)
        self.resume_info_label = QLabel('')
        self.resume_info_label.setStyleSheet('color: #888; font-size: 9pt;')
        resume_row.addWidget(self.resume_info_label)
        resume_row.addStretch()
        batch_layout.addLayout(resume_row)

        main_layout.addWidget(batch_group)

        # Add stretch to push generation section down when window is resized
        main_layout.addStretch(1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_validate = QPushButton('\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c')
        btn_validate.clicked.connect(self._validate)
        btn_layout.addWidget(btn_validate)
        btn_create = QPushButton('\u0421\u043e\u0437\u0434\u0430\u0442\u044c')
        btn_create.setMinimumWidth(120)
        btn_create.clicked.connect(self._create)
        btn_layout.addWidget(btn_create)
        main_layout.addLayout(btn_layout)
