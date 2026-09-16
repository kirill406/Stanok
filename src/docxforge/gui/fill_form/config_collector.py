# -*- coding: utf-8 -*-
"""Config collection: gathers widget state into TemplateConfig."""

from docxforge.engine.schema import (
    TemplateConfig, FieldMapping, FieldType, CycleMapping, AggregationMapping,
    AggregationFunction, BatchSourceConfig, RowIterationMode, ResumeState,
)
from .constants import FIELD_TYPES_ENUM


class ConfigCollectorMixin:
    def _collect_config(self):
        config = TemplateConfig()
        # B1: keep the generated-projects section complete (fields added via
        # the dialog after load get a checked-by-default box here).
        if hasattr(self, '_sync_generated_field_checks'):
            self._sync_generated_field_checks()
        for fn, w in self.field_widgets.items():
            tp = w['type_combo'].currentText()
            ft = FIELD_TYPES_ENUM.get(tp, FieldType.CONSTANT)
            fm = FieldMapping(type=ft)
            if ft == FieldType.CONSTANT:
                fm.value = w['const_value'].text()
            elif ft == FieldType.TABLE:
                fm.file = w['table_file'].currentText()
                fm.column = w['table_column'].currentText()
            elif ft == FieldType.COUNTER:
                try:
                    fm.start = int(w['counter_start'].text() or '1')
                except ValueError:
                    fm.start = 1
                fm.format = w['counter_format'].currentText()
            elif ft == FieldType.TODAY:
                fm.format = w['today_format'].currentText()
            elif ft == FieldType.IMAGE:
                fm.value = w['image_file'].text()
            config.fields[fn] = fm
        seen_tables = {}
        for fn, fm in config.fields.items():
            if fm.type == FieldType.TABLE and fm.file:
                if fm.file in seen_tables:
                    fm.linked_to = seen_tables[fm.file]
                else:
                    seen_tables[fm.file] = fn
        resume_sources = {}
        for df, bw in self.batch_source_widgets.items():
            mode = RowIterationMode.CONSTANT
            if bw['radio_sequential'].isChecked():
                mode = RowIterationMode.SEQUENTIAL
            elif bw['radio_circular'].isChecked():
                mode = RowIterationMode.CIRCULAR
            bsc = BatchSourceConfig(file=df, mode=mode)
            # B4: per-table «skip copying» flag from the batch row checkbox.
            _skip_box = bw.get('chk_skip_copy')
            bsc.skip_copy = bool(_skip_box is not None and _skip_box.isChecked())
            if mode == RowIterationMode.CONSTANT:
                bsc.lookup_column = bw['lookup_col_combo'].currentText() or None
                bsc.lookup_value = bw['lookup_val_combo'].currentText() or None
            # Per-source counter settings (for sequential and circular modes)
            if mode in (RowIterationMode.SEQUENTIAL, RowIterationMode.CIRCULAR):
                bsc.counter_column = bw['counter_col_combo'].currentText() or None
                bsc.counter_current_row = bw['counter_row_spin'].value()
            # Global continue_from_last is no longer used; per-source continue is in BatchSourceConfig
            config.batch_sources[df] = bsc
        if self.chk_auto_docs.isChecked():
            config.total_docs = None
        else:
            config.total_docs = self.spin_total_docs.value()
# Filename template
        config.filename_template = self.edit_filename_template.text().strip() or None
        # Directory template
        config.directory_template = self.edit_directory_template.text().strip() or None
        # Create projects mode
        config.create_projects = self.chk_create_projects.isChecked()
        config.folder_name_template = self.edit_folder_name_template.text().strip() or None
        # B1 «Поля шаблона для генерируемых проектов»: checked names define
        # the generated проект.docxforge template. All checked (or no boxes)
        # means "all fields" and is stored as [] (back-compat, clean files).
        checks = getattr(self, 'generated_field_checks', {}) or {}
        all_names = list(self.field_widgets.keys())
        selected = [n for n in all_names
                    if checks.get(n) is not None and checks[n].isChecked()]
        if selected and len(selected) < len(all_names):
            config.generated_project_fields = selected
        else:
            config.generated_project_fields = []
        # Build resume state from per-source counters
        resume_sources = {}
        for df, bw in self.batch_source_widgets.items():
            if bw['radio_sequential'].isChecked() or bw['radio_circular'].isChecked():
                resume_sources[df] = bw['counter_row_spin'].value() - 1  # 0-based
        config.resume = ResumeState(
            last_counter_value=self.config.resume.last_counter_value,
            sources=resume_sources,
            continue_from_last=True,  # Legacy field, kept for compatibility
        )
        # Preserve cycles/aggregations when the advanced section UI is not
        # built (no containers): nothing on screen edits them, so round-trip
        # the loaded values instead of silently dropping them on save.
        if getattr(self, 'cycles_layout', None) is None:
            config.cycles = list(getattr(getattr(self, 'config', None), 'cycles', []) or [])
        if getattr(self, 'aggr_layout', None) is None:
            config.aggregations = dict(getattr(getattr(self, 'config', None), 'aggregations', {}) or {})
        return config