# -*- coding: utf-8 -*-
"""Config I/O mixin: load existing config, collect config, autosave, validate, create."""

import os
from typing import Dict, List
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
        self.chk_create_projects.setChecked(self.config.create_projects)
        if self.config.folder_name_template:
            self.edit_folder_name_template.setText(self.config.folder_name_template)
        # Apply UI state for create projects mode
        self._set_folder_name_visible(self.config.create_projects)
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
        self.edit_folder_name_template.textChanged.connect(self._schedule_save)
        self.spin_total_docs.valueChanged.connect(self._schedule_save)
        self.chk_auto_docs.toggled.connect(self._schedule_save)
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
        # Validate folder name template when create_projects mode is active
        if config.create_projects and not config.folder_name_template:
            errors.append(STRINGS['msg_folder_template_required'])
        if errors:
            QMessageBox.warning(self, '\u041e\u0448\u0438\u0431\u043a\u0438', '\n'.join(errors))
            return
        # Save config on validation
        self.renderer.project.templates[self.template_rel_path] = config
        self.renderer.save_project()
        QMessageBox.information(self, '\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430', '\u0412\u0441\u0451 \u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u043e. \u041a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u044f \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0430.')

    def _create(self):
        config = self._collect_config()
        
        # Validate folder name template for create_projects mode
        if config.create_projects and not config.folder_name_template:
            QMessageBox.warning(self, '\u041e\u0448\u0438\u0431\u043a\u0430', STRINGS['msg_folder_template_required'])
            return
        
        total_docs = config.total_docs
        if total_docs is None:
            total_docs = 1
        
        if config.create_projects:
            # Create projects mode
            progress = QProgressDialog('\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0435\u043a\u0442\u043e\u0432...', None, 0, total_docs, self)
            progress.setWindowTitle('\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0435\u043a\u0442\u043e\u0432')
            outputs = self._create_projects(config, total_docs, progress)
            progress.close()
            if outputs:
                QMessageBox.information(
                    self, '\u0413\u043e\u0442\u043e\u0432\u043e',
                    '\u0421\u043e\u0437\u0434\u0430\u043d\u043e \u043f\u0440\u043e\u0435\u043a\u0442\u043e\u0432: %d\n%s' % (
                        len(outputs), '\n'.join(os.path.basename(o) for o in outputs)))
                # Save template name and doc count to main window settings
                main_window = self._get_main_window()
                if main_window:
                    if hasattr(main_window, '_set_last_template'):
                        main_window._set_last_template(self.project_dir, os.path.basename(self.template_path))
                    if hasattr(main_window, '_set_last_doc_count'):
                        main_window._set_last_doc_count(self.project_dir, total_docs)
                    if hasattr(main_window, '_refresh_recent_list'):
                        main_window._refresh_recent_list()
            else:
                QMessageBox.warning(self, '\u041e\u0448\u0438\u0431\u043a\u0430', '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u0440\u043e\u0435\u043a\u0442\u044b')
        else:
            # Normal document generation mode
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
                    if hasattr(main_window, '_refresh_recent_list'):
                        main_window._refresh_recent_list()
            else:
                QMessageBox.warning(self, '\u041e\u0448\u0438\u0431\u043a\u0430', '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b')
    
    def _create_projects(self, config: 'TemplateConfig', total_docs: int, progress: 'QProgressDialog') -> List[str]:
        """Create project folders with filled templates."""
        import shutil
        from docxforge.engine.schema import Project, TemplateConfig
        
        outputs = []
        results_dir = os.path.join(self.project_dir, 'output')
        os.makedirs(results_dir, exist_ok=True)
        
        for doc_index in range(total_docs):
            progress.setValue(doc_index)
            progress.setLabelText('\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0435\u043a\u0442\u0430 %d \u0438\u0437 %d' % (doc_index + 1, total_docs))
            
            # Get effective values for this document index
            effective_values = self._get_effective_values_for_doc(config, doc_index)
            
            # Compute folder name from template
            folder_name = config.folder_name_template
            for key, value in effective_values.items():
                folder_name = folder_name.replace('{{ %s }}' % key, str(value))
                folder_name = folder_name.replace('{{%s}}' % key, str(value))
            
            # Create project folder
            project_folder = os.path.join(results_dir, folder_name)
            os.makedirs(project_folder, exist_ok=True)
            
            # Render document directly to project folder
            doc_outputs = self.renderer.render(
                self.template_rel_path,
                {},
                output_dir=project_folder,
                max_docs=1,
            )
            
            if doc_outputs:
                outputs.extend(doc_outputs)
        
        return outputs
    
    def _get_effective_values_for_doc(self, config: 'TemplateConfig', doc_index: int) -> Dict[str, str]:
        """Get effective field values for a specific document index (for folder name template)."""
        from datetime import datetime
        from docxforge.engine.renderer import Renderer
        from docxforge.engine.data_reader import DataReader
        from docxforge.engine.render_loop import (
            scan_raw_placeholders, resolve_field_values, process_xml,
        )
        
        # This is a simplified version - we need to compute effective values
        # similar to what the renderer does, but without writing the file
        template_path = self.renderer.get_template_path(self.template_rel_path)
        
        import zipfile
        with zipfile.ZipFile(template_path, 'r') as zf:
            zdata = {name: zf.read(name) for name in zf.namelist()}
        
        all_raw_phs = scan_raw_placeholders(zdata)
        now = datetime.now()
        
        # Read all table data
        all_table_data = {}
        for fn, fm in config.fields.items():
            if fm.type == 'table' and fm.file and fm.file not in all_table_data:
                all_table_data[fm.file] = self.renderer._read_table_data(fm.file)
        for source_file in config.batch_sources:
            if source_file not in all_table_data:
                all_table_data[source_file] = self.renderer._read_table_data(source_file)
        
        # Resolve rows for this document index
        per_source_rows = {}
        for source_file, bsc in config.batch_sources.items():
            rows = all_table_data.get(source_file, [])
            row = self.renderer._resolve_row_for_source(
                source_file, doc_index, config.batch_sources, config.resume, rows)
            per_source_rows[source_file] = row
        
        # Load cycle data
        cycle_data = {}
        for cycle in config.cycles:
            if cycle.table not in all_table_data:
                cycle_data[cycle.table] = self.renderer._read_table_data(cycle.table)
            else:
                cycle_data[cycle.table] = all_table_data[cycle.table]
        for agg in config.aggregations.values():
            if agg.table not in cycle_data:
                if agg.table not in all_table_data:
                    cycle_data[agg.table] = self.renderer._read_table_data(agg.table)
                else:
                    cycle_data[agg.table] = all_table_data[agg.table]
        
        # Get effective values
        effective, _ = resolve_field_values(
            config, all_raw_phs, doc_index, per_source_rows,
            all_table_data, cycle_data, config.resume, now, {})
        
        return effective

