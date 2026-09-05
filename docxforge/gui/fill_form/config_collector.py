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
        for i in range(self.cycles_layout.count()):
            grp = self.cycles_layout.itemAt(i).widget()
            if not isinstance(grp, QGroupBox):
                continue
            vb = grp.layout()
            if vb.count() < 2:
                continue
            top = vb.itemAt(0).layout()
            file_combo = top.itemAt(1).widget()
            cols_layout = grp.property('cols_layout')
            if not cols_layout:
                continue
            columns = {}
            for r in range(cols_layout.rowCount()):
                nw = cols_layout.itemAtPosition(r, 1)
                vw = cols_layout.itemAtPosition(r, 3)
                if nw and vw:
                    n = nw.widget().text().strip()
                    v = vw.widget().currentText().strip()
                    if n and v:
                        columns[n] = v
            if file_combo.currentText() and columns:
                config.cycles.append(CycleMapping(table=file_combo.currentText(), columns=columns))
        for i in range(self.aggr_layout.count()):
            grp = self.aggr_layout.itemAt(i).widget()
            if not isinstance(grp, QGroupBox):
                continue
            vb = grp.layout()
            top = vb.itemAt(0).layout()
            aname = top.itemAt(1).widget().text().strip()
            mid = vb.itemAt(1).layout()
            func_str = mid.itemAt(1).widget().currentText()
            table = mid.itemAt(3).widget().currentText()
            column = mid.itemAt(5).widget().currentText()
            mult_w = mid.itemAt(7).widget()
            if not aname or not table or not column:
                continue
            if func_str == 'sum * \u0447\u0438\u0441\u043b\u043e':
                func = AggregationFunction.SUM_MULTIPLY
                multiplier = float(mult_w.text() or '1')
            elif func_str in ('sum', 'count', 'max', 'min'):
                func = AggregationFunction(func_str)
                multiplier = None
            else:
                continue
            config.aggregations[aname] = AggregationMapping(function=func, table=table, column=column, multiplier=multiplier)
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
            config.batch_sources[df] = bsc
        if self.chk_auto_docs.isChecked():
            config.total_docs = None
        else:
            config.total_docs = self.spin_total_docs.value()
        config.resume = ResumeState(
            last_counter_value=self.config.resume.last_counter_value,
            sources=dict(self.config.resume.sources),
            continue_from_last=self.chk_continue.isChecked(),
        )
        config.ui_state = {'advanced_visible': self.advanced_group.isChecked()}
        return config

