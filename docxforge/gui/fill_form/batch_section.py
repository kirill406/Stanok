# -*- coding: utf-8 -*-
"""Batch section mixin: batch source rows, auto-info, resume-info."""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QComboBox, QRadioButton)

from ..strings import STRINGS


class BatchSectionMixin:
    """Methods for managing batch source configuration in FillForm."""

    def _update_auto_info(self):
        if not self.chk_auto_docs.isChecked():
            self.auto_info_label.setText('')
            return
        seq = [df for df, bw in self.batch_source_widgets.items() if bw['radio_sequential'].isChecked()]
        if seq:
            counts = ['%s: %d' % (df, self._get_row_count(df)) for df in seq]
            self.auto_info_label.setText(
                STRINGS['batch_auto_info_with_tables'].format(counts=', '.join(counts)))
        else:
            self.auto_info_label.setText(STRINGS['batch_auto_info_no_tables'])

    def _update_resume_info(self):
        resume = self.config.resume
        if not resume.sources:
            self.resume_info_label.setText('')
            return
        parts = ['%s: \u0441\u0442\u0440\u043e\u043a\u0430 %d' % (f, r + 1) for f, r in resume.sources.items()]
        if resume.last_counter_value > 0:
            parts.append('\u0441\u0447\u0451\u0442\u0447\u0438\u043a: %d' % resume.last_counter_value)
        self.resume_info_label.setText('(%s)' % ', '.join(parts) if parts else '')

    def _rebuild_batch_source_rows(self):
        layout = self.batch_sources_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self.batch_source_widgets = {}
        for df in self.data_files:
            row_widget = QWidget()
            rl = QVBoxLayout(row_widget)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(2)
            top = QHBoxLayout()
            lbl = QLabel(df)
            lbl.setMinimumWidth(140)
            top.addWidget(lbl)
            rc = QRadioButton(STRINGS['batch_mode_constant'])
            rc.setChecked(True)
            top.addWidget(rc)
            rs = QRadioButton(STRINGS['batch_mode_sequential'])
            top.addWidget(rs)
            ry = QRadioButton(STRINGS['batch_mode_circular'])
            top.addWidget(ry)
            top.addStretch()
            rl.addLayout(top)
            lp = QWidget()
            lpl = QHBoxLayout(lp)
            lpl.setContentsMargins(20, 0, 0, 0)
            lpl.setSpacing(4)
            lpl.addWidget(QLabel(STRINGS['batch_lookup_column']))
            lcc = QComboBox()
            lcc.addItems(self._get_columns(df))
            lcc.setMinimumWidth(100)
            lcc.installEventFilter(self._wheel_filter)
            lpl.addWidget(lcc)
            lpl.addWidget(QLabel(STRINGS['batch_lookup_value']))
            lvc = QComboBox()
            lvc.setEditable(True)
            lvc.setMinimumWidth(120)
            lvc.installEventFilter(self._wheel_filter)
            lpl.addWidget(lvc)
            def on_lcc(col, vc=lvc, fname=df):
                vc.clear()
                if col:
                    path = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435', fname)
                    if os.path.exists(path):
                        vc.addItems(self.data_reader.get_distinct_values(path, col))
            lcc.currentTextChanged.connect(on_lcc)
            rl.addWidget(lp)
            def on_mc(c, l=lp):
                l.setVisible(c)
            rc.toggled.connect(on_mc)
            lp.setVisible(True)
            rc.toggled.connect(lambda _: self._update_auto_info())
            rs.toggled.connect(lambda _: self._update_auto_info())
            self.batch_source_widgets[df] = {
                'radio_constant': rc, 'radio_sequential': rs, 'radio_circular': ry,
                'lookup_panel': lp, 'lookup_col_combo': lcc, 'lookup_val_combo': lvc,
            }
            layout.addWidget(row_widget)