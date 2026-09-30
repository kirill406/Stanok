# -*- coding: utf-8 -*-
"""Config I/O mixin: load existing config, collect config, autosave, validate, create."""

import logging
import os
from PyQt5.QtWidgets import (QMessageBox, QProgressDialog, QInputDialog)

from docxforge.engine.schema import (
    TemplateConfig, FieldMapping, FieldType, CycleMapping, AggregationMapping,
    AggregationFunction, BatchSourceConfig, RowIterationMode, ResumeState,
)
from docxforge.generate import GenerationError
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
        # Cycles/aggregations: the advanced section UI is currently not built
        # (no cycles_layout/aggr_layout on the dialog), so only restore rows
        # when the containers exist. Calling the row builders unconditionally
        # raised AttributeError on projects with cycles/aggregations.
        # Values are preserved untouched otherwise; round-trip on save is
        # handled in ConfigCollectorMixin._collect_config.
        if getattr(self, 'cycles_layout', None) is not None and hasattr(self, '_add_cycle_row'):
            for cycle in self.config.cycles:
                self._add_cycle_row(cycle.table, cycle.columns)
        elif getattr(self.config, 'cycles', None):
            logging.getLogger(__name__).debug(
                'Skipping %d cycle row(s): advanced section UI not built',
                len(self.config.cycles))
        if getattr(self, 'aggr_layout', None) is not None and hasattr(self, '_add_aggr_row'):
            for aname, agg in self.config.aggregations.items():
                self._add_aggr_row(aname, agg.function.value, agg.table, agg.column, agg.multiplier)
        elif getattr(self.config, 'aggregations', None):
            logging.getLogger(__name__).debug(
                'Skipping %d aggregation row(s): advanced section UI not built',
                len(self.config.aggregations))
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
            # Load counter settings for sequential/circular modes
            if bsc.mode in (RowIterationMode.SEQUENTIAL, RowIterationMode.CIRCULAR):
                if bsc.counter_column:
                    idx = bw['counter_col_combo'].findText(bsc.counter_column)
                    if idx >= 0:
                        bw['counter_col_combo'].setCurrentIndex(idx)
                if bsc.counter_current_row > 1:
                    bw['counter_row_spin'].setValue(bsc.counter_current_row)
            # B4: restore the «skip copying» checkbox.
            _skip_box = bw.get('chk_skip_copy')
            if _skip_box is not None:
                _skip_box.setChecked(bool(getattr(bsc, 'skip_copy', False)))
        # B1: sync the «Поля шаблона для генерируемых проектов» section
        # (fields exist by now) and restore the stored subset selection.
        if hasattr(self, '_sync_generated_field_checks'):
            self._sync_generated_field_checks()
        stored = set(getattr(self.config, 'generated_project_fields', []) or [])
        for name, box in (getattr(self, 'generated_field_checks', {}) or {}).items():
            box.setChecked(not stored or name in stored)
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
                errors.append(STRINGS['msg_table_field_missing'].format(name=fn))
        # Validate composite path template when create_projects mode is active:
        # format {{employee_column}}/{{project_column}} (dynamic column names).
        if config.create_projects:
            from .form_dialog import FillForm
            errors.extend(FillForm.validate_composite_template(config.folder_name_template))
        if errors:
            QMessageBox.warning(self, STRINGS['msg_error'], '\n'.join(errors))
            return
        # Save config on validation
        self.renderer.project.templates[self.template_rel_path] = config
        self.renderer.save_project()
        QMessageBox.information(self, STRINGS['msg_check'], STRINGS['msg_validation_ok'])

    def _create(self):
        config = self._collect_config()
        
        # Validate composite path template for create_projects mode:
        # format {{employee_column}}/{{project_column}} (dynamic column names).
        if config.create_projects:
            from .form_dialog import FillForm
            template_errors = FillForm.validate_composite_template(config.folder_name_template)
            if template_errors:
                QMessageBox.warning(self, STRINGS['msg_error'], '\n'.join(template_errors))
                return
        
        total_docs = config.total_docs
        if total_docs is None:
            total_docs = 1
        
        if config.create_projects:
            # Create projects mode (flat or nested employee/project structure)
            self._create_projects_mode(config)
        else:
            # Normal document generation mode.
            # B3: the template may disappear (or become unreadable) after the
            # dialog was opened, so engine errors are reported via a warning
            # dialog instead of escaping the Qt slot (FileNotFoundError crash).
            progress = QProgressDialog(STRINGS['msg_progress_generating'], None, 0, total_docs, self)
            progress.setWindowTitle(STRINGS['msg_progress_creating_docs'])
            progress.setWindowModality(1)  # Qt.WindowModal
            try:
                outputs = self.renderer.render(
                    self.template_rel_path,
                    {},
                    output_dir=os.path.join(self.project_dir, 'Результат'),
                    max_docs=total_docs,
                )
            except FileNotFoundError as e:
                logging.getLogger(__name__).exception(
                    f'Render failed, template gone {self.template_rel_path}: {e}')
                progress.close()
                QMessageBox.warning(
                    self, STRINGS['msg_error'],
                    STRINGS['msg_render_error'].format(error=e))
                return
            except Exception as e:
                logging.getLogger(__name__).exception(
                    f'Render failed for {self.template_rel_path}: {e}')
                progress.close()
                QMessageBox.warning(
                    self, STRINGS['msg_error'],
                    STRINGS['msg_render_error'].format(error=e))
                return
            progress.close()
            if outputs:
                QMessageBox.information(
                    self, STRINGS['msg_success'],
                    STRINGS['msg_generation_done'].format(
                        count=len(outputs),
                        files='\n'.join(os.path.basename(o) for o in outputs)))
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
                QMessageBox.warning(self, STRINGS['msg_error'], STRINGS['msg_generation_failed'])
    
    def _create_projects_mode(self, config: 'TemplateConfig'):
        """Create-projects mode: row-count dialog, engine call, result dialog.

        Runs in the GUI thread with modal dialogs only (no threads/timers),
        so the Qt event loop handling stays unchanged.
        """
        logger = logging.getLogger(__name__)

        # Total rows of the primary batch source = total projects to create.
        # Counting uses the in-memory config: nothing is persisted yet, so
        # cancelling the dialog below leaves no trace (M12).
        try:
            total_rows = self._count_primary_rows(config)
        except ValueError as e:
            logger.exception(f'Failed to count batch rows: {e}')
            QMessageBox.warning(self, STRINGS['msg_error'], str(e))
            return
        except Exception as e:
            logger.exception(f'Failed to count batch rows: {e}')
            QMessageBox.warning(self, STRINGS['msg_error'], str(e))
            return
        if total_rows < 1:
            QMessageBox.warning(self, STRINGS['msg_error'], STRINGS['msg_no_batch_rows'])
            return

        # Row-count dialog (cancel aborts before anything is created/saved).
        chosen = total_rows
        if total_rows > 1:
            chosen, ok = QInputDialog.getInt(
                self,
                STRINGS['fill_create_projects_btn'],
                STRINGS['fill_found_rows'].format(count=total_rows),
                total_rows, 1, total_rows, 1)
            if not ok:
                return

        # Engine reads the project file from disk, so persist the config now
        # (after confirmation). Follow the resolved file (folder or migrated
        # Home copy). Snapshot first: on engine failure the previous
        # config is restored instead of leaving a half-applied one (M12).
        project_file = getattr(self.renderer, 'project_file', None)
        if project_file is None:
            from docxforge.engine.schema import default_project_file
            project_file = default_project_file(self.project_dir)
        snapshot = None
        if os.path.exists(project_file):
            with open(project_file, 'rb') as f:
                snapshot = f.read()
        self.renderer.project.templates[self.template_rel_path] = config
        self.renderer.save_project()

        # Single engine entry point: create_projects_from_template() routes
        # composite (employee/project) templates to nested generation
        # internally. generate.py itself is never modified here, only called.
        from docxforge.generate import create_projects_from_template
        try:
            result = create_projects_from_template(
                self.project_dir, self.template_rel_path,
                config.folder_name_template, max_projects=chosen)
        except GenerationError as e:
            logger.exception(f'Create projects failed: {e}')
            if snapshot is not None:
                try:
                    with open(project_file, 'wb') as f:
                        f.write(snapshot)
                    self.renderer.load_project()
                except OSError as restore_error:
                    logger.exception(
                        f'Failed to restore config snapshot {project_file}: {restore_error}')
                except Exception as restore_error:
                    logger.exception(
                        f'Failed to restore config snapshot {project_file}: {restore_error}')
            QMessageBox.warning(self, STRINGS['msg_error'], str(e))
            return
        except Exception as e:
            logger.exception(f'Create projects failed: {e}')
            if snapshot is not None:
                try:
                    with open(project_file, 'wb') as f:
                        f.write(snapshot)
                    self.renderer.load_project()
                except OSError as restore_error:
                    logger.exception(
                        f'Failed to restore config snapshot {project_file}: {restore_error}')
                except Exception as restore_error:
                    logger.exception(
                        f'Failed to restore config snapshot {project_file}: {restore_error}')
            QMessageBox.warning(self, STRINGS['msg_error'], str(e))
            return

        # Nested (Phase 3) returns (path, employees, projects);
        # flat returns (path, count). Both are supported.
        if len(result) == 3:
            projects_dir, n_employees, n_projects = result
            message = STRINGS['fill_nested_projects_created'].format(
                employees=n_employees, count=n_projects, path=projects_dir)
            created_count = n_projects
        else:
            projects_dir, created_count = result[0], result[1]
            message = STRINGS['fill_projects_created'].format(
                count=created_count, path=projects_dir)
        QMessageBox.information(self, STRINGS['msg_success'], message)

        # Save template name and doc count to main window settings
        main_window = self._get_main_window()
        if main_window:
            if hasattr(main_window, '_set_last_template'):
                main_window._set_last_template(self.project_dir, os.path.basename(self.template_path))
            if hasattr(main_window, '_set_last_doc_count'):
                main_window._set_last_doc_count(self.project_dir, chosen)
            if hasattr(main_window, '_refresh_recent_list'):
                main_window._refresh_recent_list()

    def _count_primary_rows(self, config: 'TemplateConfig') -> int:
        """Return total row count of the first SEQUENTIAL batch source.

        Delegates to the single engine counter
        (Renderer.count_source_rows, M3).
        """
        primary_file = None
        for _source_name, bsc in config.batch_sources.items():
            if bsc.mode == RowIterationMode.SEQUENTIAL:
                primary_file = bsc.file
                break
        if primary_file is None:
            raise ValueError(STRINGS['msg_no_batch_rows'])
        return self.renderer.count_source_rows(primary_file)

