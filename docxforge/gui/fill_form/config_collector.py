# -*- coding: utf-8 -*-
"""Config collection: gathers widget state into TemplateConfig."""

from PyQt5.QtWidgets import QGroupBox

from docxforge.engine.schema import (
    TemplateConfig, FieldMapping, FieldType, CycleMapping, AggregationMapping,
    AggregationFunction, BatchSourceConfig, RowIterationMode, ResumeState,
)
from .constants import FIELD_TYPES_ENUM


class ConfigCollectorMixin:
    def _collect_config(self):
        config = TemplateConfig()
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
        # Cycles and aggregations removed from UI - skip collection
        # if hasattr(self, 'cycles_layout'):
        #     for i in range(self.cycles_layout.count()):
        #         ...
        # if hasattr(self, 'aggr_layout'):
        #     for i in range(self.aggr_layout.count()):
        #         ...
        resume_sources = {}
        for df, bw in self.batch_source_widgets.items():
            mode = RowIterationMode.CONSTANT
            if bw['radio_sequential'].isChecked():
                mode = RowIterationMode.SEQUENTIAL
            elif bw['radio_circular'].isChecked():
                mode = RowIterationMode.CIRCULAR
            bsc = BatchSourceConfig(file=df, mode=mode)
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
        config.ui_state = {}
        return config