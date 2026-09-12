# -*- coding: utf-8 -*-
"""Config I/O mixin: load existing config, collect config, autosave, validate, create."""

import os
from PyQt5.QtWidgets import (QGroupBox, QMessageBox, QProgressDialog)

from docxforge.engine.schema import (
    TemplateConfig, FieldMapping, FieldType, CycleMapping, AggregationMapping,
    AggregationFunction, BatchSourceConfig, RowIterationMode, ResumeState,
)
from .constants import FIELD_TYPES_ENUM
from ..strings import STRINGS


class ConfigIOMixin:
    """Methods for loading, saving, and validating FillForm configuration."""

    def _get_main_window(self):
        """Get reference to MainWindow via parent chain (ProjectWindow -> MainWindow)."""
        parent = self.parent()
        if parent and hasattr(parent, 'main_window'):
            return parent.main_window
        return None

    def _load_existing_config(self):
        for field_name, fm in self.config.fields.items():
            if field_name not in self.field_widgets:
                preset = '\u043a\u043e\u043d\u0441\u0442\u0430\u043d\u0442\u0430'
                if fm.type == FieldType.COUNTER:
                    preset = '\u0441\u0447\u0451\u0442\u0447\u0438\u043a'
                elif fm.type == FieldType.TODAY:
                    preset = '\u0441\u0435\u0433\u043e\u0434\u043d\u044f'
                elif fm.type == FieldType.TABLE:
                    preset = '\u0442\u0430\u0431\u043b\u0438\u0446\u0430'
                elif fm.type == FieldType.IMAGE:
                    preset = '\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435'
                self._add_field_row(field_name, preset_type=preset)
            w = self.field_widgets.get(field_name)
            if not w:
                continue
            type_name = next((k for k, v in FIELD_TYPES_ENUM.items() if v == fm.type), '\u043a\u043e\u043d\u0441\u0442\u0430\u043d\u0442\u0430')
            w['type_combo'].setCurrentText(type_name)
            if fm.type == FieldType.CONSTANT:
                w['const_value'].setText(fm.value or '')
            elif fm.type == FieldType.TABLE:
                idx = w['table_file'].findText(fm.file or '')
                if idx >= 0:
                    w['table_file'].setCurrentIndex(idx)
                idx = w['table_column'].findText(fm.column or '')
                if idx >= 0:
                    w['table_column'].setCurrentIndex(idx)
            elif fm.type == FieldType.COUNTER:
                w['counter_start'].setText(str(fm.start))
                idx = w['counter_format'].findText(fm.format)
                if idx >= 0:
                    w['counter_format'].setCurrentIndex(idx)
            elif fm.type == FieldType.TODAY:
                idx = w['today_format'].findText(fm.format)
                if idx >= 0:
                    w['today_format'].setCurrentIndex(idx)
            elif fm.type == FieldType.IMAGE:
                w['image_file'].setText(fm.value or fm.file or '')
        for cycle in self.config.cycles:
            self._add_cycle_row(cycle.table, cycle.columns)
        for aname, agg in self.config.aggregations.items():
            self._add_aggr_row(aname, agg.function.value, agg.table, agg.column, agg.multiplier)
        for df, bsc in self.config.batch_sources.items():
            bw = self.batch_source_widgets.get(df)
            if not bw:
                continue
            if bsc.mode == RowIterationMode.CONSTANT:
                bw['radio_constant'].setChecked(True)
            elif bsc.mode == RowIterationMode.SEQUENTIAL:
                bw['radio_sequential'].setChecked(True)
            elif bsc.mode == RowIterationMode.CIRCULAR:
                bw['radio_circular'].setChecked(True)
            if bsc.mode == RowIterationMode.CONSTANT:
                idx = bw['lookup_col_combo'].findText(bsc.lookup_column or '')
                if idx >= 0:
                    bw['lookup_col_combo'].setCurrentIndex(idx)
                idx = bw['lookup_val_combo'].findText(bsc.lookup_value or '')
                if idx >= 0:
                    bw['lookup_val_combo'].setCurrentIndex(idx)
                else:
                    bw['lookup_val_combo'].setCurrentText(bsc.lookup_value or '')
            # Per-table resume checkbox (removed - using counter settings instead)
            # Load counter settings for sequential/circular modes
            if bsc.mode in (RowIterationMode.SEQUENTIAL, RowIterationMode.CIRCULAR):
                if bsc.counter_column:
                    idx = bw['counter_col_combo'].findText(bsc.counter_column)
                    if idx >= 0:
                        bw['counter_col_combo'].setCurrentIndex(idx)
                if bsc.counter_current_row > 1:
                    bw['counter_row_spin'].setValue(bsc.counter_current_row)
        if self.config.total_docs is not None:
            self.chk_auto_docs.setChecked(False)
            self.spin_total_docs.setValue(self.config.total_docs)
            self.spin_total_docs.setVisible(True)
        else:
            self.chk_auto_docs.setChecked(True)
            self.spin_total_docs.setVisible(False)
        # Filename template
        if self.config.filename_template:
            self.edit_filename_template.setText(self.config.filename_template)
        # Directory template
        if self.config.directory_template:
            self.edit_directory_template.setText(self.config.directory_template)
        # Create projects mode
        if hasattr(self, 'chk_create_projects'):
            create_projects = self.config.ui_state.get('create_projects', False)
            self.chk_create_projects.setChecked(create_projects)
            # Trigger UI toggle
            self._on_create_projects_toggled(create_projects)
        if hasattr(self, 'edit_folder_name_template'):
            folder_name_template = self.config.ui_state.get('folder_name_template')
            if folder_name_template:
                self.edit_folder_name_template.setText(folder_name_template)
        # Per-source continue_from_last is loaded in _rebuild_batch_source_rows
        self._update_resume_info()

    def _connect_autosave(self):
        self._autosave_enabled = True
        for fn, w in self.field_widgets.items():
            w['type_combo'].currentTextChanged.connect(self._schedule_save)
            w['const_value'].textChanged.connect(self._schedule_save)
            w['table_file'].currentTextChanged.connect(self._schedule_save)
            w['table_column'].currentTextChanged.connect(self._schedule_save)
            w['counter_start'].textChanged.connect(self._schedule_save)
            w['counter_format'].currentTextChanged.connect(self._schedule_save)
            w['today_format'].currentTextChanged.connect(self._schedule_save)
            w['image_file'].textChanged.connect(self._schedule_save)
        self.edit_filename_template.textChanged.connect(self._schedule_save)
        self.edit_directory_template.textChanged.connect(self._schedule_save)
        if hasattr(self, 'edit_folder_name_template'):
            self.edit_folder_name_template.textChanged.connect(self._schedule_save)
        self.spin_total_docs.valueChanged.connect(self._schedule_save)
        self.chk_auto_docs.toggled.connect(self._schedule_save)
        if hasattr(self, 'chk_create_projects'):
            self.chk_create_projects.toggled.connect(self._schedule_save)
        for df, bw in self.batch_source_widgets.items():
            bw['radio_constant'].toggled.connect(self._schedule_save)
            bw['radio_sequential'].toggled.connect(self._schedule_save)
            bw['radio_circular'].toggled.connect(self._schedule_save)
            bw['lookup_col_combo'].currentTextChanged.connect(self._schedule_save)
            bw['lookup_val_combo'].currentTextChanged.connect(self._schedule_save)
            # New counter widgets
            bw['counter_col_combo'].currentTextChanged.connect(self._schedule_save)
            bw['counter_row_spin'].valueChanged.connect(self._schedule_save)

    def _schedule_save(self, *_args):
        if not self._autosave_enabled:
            return
        self._save_timer.start(500)

    def _do_save_project(self):
        if not self._autosave_enabled:
            return
        config = self._collect_config()
        self.renderer.project.templates[self.template_rel_path] = config
        self.renderer.save_project()

    def _validate(self):
        config = self._collect_config()
        errors = []
        for fn, fm in config.fields.items():
            if fm.type == FieldType.TABLE and (not fm.file or not fm.column):
                errors.append('\u041f\u043e\u043b\u0435 {{ %s }}: \u0443\u043a\u0430\u0436\u0438\u0442\u0435 \u0444\u0430\u0439\u043b \u0438 \u0441\u0442\u043e\u043b\u0431\u0435\u0446' % fn)
        # Validate create projects mode
        if getattr(self, 'chk_create_projects', None) and self.chk_create_projects.isChecked():
            folder_template = config.ui_state.get('folder_name_template')
            if not folder_template:
                errors.append('\u0414\u043b\u044f \u0440\u0435\u0436\u0438\u043c\u0430 \u00ab\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u0440\u043e\u0435\u043a\u0442\u044b\u00bb \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e \u0437\u0430\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0448\u0430\u0431\u043b\u043e\u043d \u0438\u043c\u0435\u043d\u0438 \u043f\u0430\u043f\u043a\u0438')
        if errors:
            QMessageBox.warning(self, '\u041e\u0448\u0438\u0431\u043a\u0438', '\n'.join(errors))
            return
        # Save config on validation
        self.renderer.project.templates[self.template_rel_path] = config
        self.renderer.save_project()
        QMessageBox.information(self, '\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430', '\u0412\u0441\u0451 \u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u043e. \u041a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u044f \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0430.')

    def _create(self):
        config = self._collect_config()
        
        # Check if create projects mode is active
        if getattr(self, 'chk_create_projects', None) and self.chk_create_projects.isChecked():
            self._create_projects_mode(config)
            return
        
        # Normal document generation mode
        total_docs = config.total_docs
        if total_docs is None:
            total_docs = 1
        progress = QProgressDialog('\u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f...', None, 0, total_docs, self)
        progress.setWindowTitle('\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432')
        progress.setWindowModality(1)  # Qt.WindowModal
        outputs = self.renderer.render(
            self.template_rel_path,
            {},
            output_dir=os.path.join(self.project_dir, 'output'),
            max_docs=total_docs,
        )
        progress.close()
        if outputs:
            QMessageBox.information(
                self, '\u0413\u043e\u0442\u043e\u0432\u043e',
                '\u0421\u043e\u0437\u0434\u0430\u043d\u043e \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432: %d\n%s' % (
                    len(outputs), '\n'.join(os.path.basename(o) for o in outputs)))
            # Save template name and doc count to main window settings
            main_window = self._get_main_window()
            if main_window:
                if hasattr(main_window, '_set_last_template'):
                    main_window._set_last_template(self.project_dir, os.path.basename(self.template_path))
                if hasattr(main_window, '_set_last_doc_count'):
                    main_window._set_last_doc_count(self.project_dir, total_docs)
                # Refresh recent list to show updated count
                if hasattr(main_window, '_refresh_recent_list'):
                    main_window._refresh_recent_list()
        else:
            QMessageBox.warning(self, '\u041e\u0448\u0438\u0431\u043a\u0430', '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b')

    def _create_projects_mode(self, config):
        """Handle create projects mode - generate project folders from template."""
        # Validate folder name template
        folder_name_template = config.ui_state.get('folder_name_template')
        if not folder_name_template:
            QMessageBox.warning(
                self, STRINGS['msg_warning'],
                '\u0414\u043b\u044f \u0440\u0435\u0436\u0438\u043c\u0430 \u00ab\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u0440\u043e\u0435\u043a\u0442\u044b\u00bb \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e \u0437\u0430\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0448\u0430\u0431\u043b\u043e\u043d \u0438\u043c\u0435\u043d\u0438 \u043f\u0430\u043a\u043a\u0438.')
            return
        
        # Find primary batch source (first sequential table)
        primary_source = None
        for df, bsc in config.batch_sources.items():
            if bsc.mode == RowIterationMode.SEQUENTIAL:
                primary_source = df
                break
        
        if not primary_source:
            QMessageBox.warning(
                self, STRINGS['msg_warning'],
                '\u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0434\u0430\u043d\u043d\u044b\u0445 \u0441 \u0440\u0435\u0436\u0438\u043c\u043e\u043c \u00ab\u041f\u043e \u0441\u0442\u0440\u043e\u043a\u0430\u043c\u00bb. '
                '\u0414\u043b\u044f \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u044f \u043f\u0440\u043e\u0435\u043a\u0442\u043e\u0432 \u043d\u0443\u0436\u0435\u043d \u0430\u043b\u044c\u044f \u043e\u0434\u043d\u0430 \u0442\u0430\u0431\u043b\u0438\u0446\u0430 \u0441 \u0440\u0435\u0436\u0438\u043c\u043e\u043c \u00ab\u041f\u043e \u0441\u0442\u0440\u043e\u043a\u0430\u043c\u00bb.')
            return
        
        # Count rows in primary source
        row_count = self._get_row_count(primary_source)
        if row_count == 0:
            QMessageBox.warning(
                self, STRINGS['msg_warning'],
                '\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0434\u0430\u043d\u043d\u044b\u0445 \u00ab%s\u00bb \u043f\u0443\u0441\u0442 \u0438\u043b\u0438 \u043d\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u0435\u0442.' % primary_source)
            return
        
        # Show confirmation dialog if more than 1 row
        if row_count > 1:
            reply = QMessageBox.question(
                self, STRINGS['msg_info'],
                STRINGS['fill_found_rows'].format(count=row_count),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes)
            if reply == QMessageBox.No:
                return  # User cancelled
        
        # Call create_projects_from_template (to be implemented in Phase 4)
        # For now, we'll show a placeholder message
        try:
            # TODO: Import and call create_projects_from_template when implemented
            # from docxforge.generate import create_projects_from_template
            # created_count, projects_path = create_projects_from_template(
            #     self.project_dir, self.template_rel_path, folder_name_template, row_count)
            
            # Placeholder for Phase 4 implementation
            QMessageBox.information(
                self, STRINGS['msg_info'],
                '\u0420\u0435\u0436\u0438\u043c \u00ab\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u0440\u043e\u0435\u043a\u0442\u044b\u00bb \u0431\u0443\u0434\u0435\u0442 \u0440\u0435\u0430\u043b\u0438\u0437\u043e\u0432\u0430\u043d \u0432 Phase 4.\n'
                '\u041d\u0430\u0439\u0434\u0435\u043d\u043e \u0441\u0442\u0440\u043e\u043a: %d\n'
                '\u0428\u0430\u0431\u043b\u043e\u043d \u043f\u0430\u043a\u043a\u0438: %s' % (row_count, folder_name_template))
        except Exception as e:
            QMessageBox.critical(
                self, STRINGS['msg_error'],
                '\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u0438 \u043f\u0440\u043e\u0435\u043a\u0442\u043e\u0432: %s' % str(e))

