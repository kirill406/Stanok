# -*- coding: utf-8 -*-
"""Batch section mixin: batch source rows, auto-info, resume-info."""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QComboBox, QRadioButton, QCheckBox, QSpinBox)
from PyQt5.QtCore import QObject, pyqtSlot, Qt

from ..strings import STRINGS


class BatchSourceRow(QObject):
    """Manages UI and logic for a single batch data source row."""
    
    def __init__(self, parent, df, columns, wheel_filter, data_reader, project_dir):
        super().__init__(parent)
        self.parent = parent
        self.df = df
        self.columns = columns
        self.wheel_filter = wheel_filter
        self.data_reader = data_reader
        self.project_dir = project_dir
        
        self._build_ui()
        self._connect_signals()
        self._set_initial_state()
    
    def _build_ui(self):
        self.row_widget = QWidget()
        rl = QVBoxLayout(self.row_widget)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)
        
        # Top row: filename + radio buttons
        top = QHBoxLayout()
        lbl = QLabel(self.df)
        lbl.setMinimumWidth(140)
        top.addWidget(lbl)
        
        self.rc = QRadioButton(STRINGS['batch_mode_constant'])
        self.rs = QRadioButton(STRINGS['batch_mode_sequential'])
        self.ry = QRadioButton(STRINGS['batch_mode_circular'])
        self.rc.setAutoExclusive(False)
        self.rs.setAutoExclusive(False)
        self.ry.setAutoExclusive(False)
        top.addWidget(self.rc)
        top.addWidget(self.rs)
        top.addWidget(self.ry)
        top.addStretch()
        rl.addLayout(top)
        
        # Lookup panel (for constant mode)
        self.lp = QWidget()
        lpl = QHBoxLayout(self.lp)
        lpl.setContentsMargins(20, 0, 0, 0)
        lpl.setSpacing(4)
        lpl.addWidget(QLabel(STRINGS['batch_lookup_column']))
        self.lcc = QComboBox()
        self.lcc.addItems(self.columns)
        self.lcc.setMinimumWidth(100)
        self.lcc.installEventFilter(self.wheel_filter)
        lpl.addWidget(self.lcc)
        lpl.addWidget(QLabel(STRINGS['batch_lookup_value']))
        self.lvc = QComboBox()
        self.lvc.setEditable(True)
        self.lvc.setMinimumWidth(120)
        self.lvc.installEventFilter(self.wheel_filter)
        lpl.addWidget(self.lvc)
        rl.addWidget(self.lp)
        
        # Counter panel (for sequential/circular modes)
        self.counter_panel = QWidget()
        counter_layout = QHBoxLayout(self.counter_panel)
        counter_layout.setContentsMargins(20, 0, 0, 0)
        counter_layout.setSpacing(4)
        
        counter_layout.addWidget(QLabel(STRINGS['batch_counter_column']))
        self.ccc = QComboBox()
        self.ccc.addItems(self.columns)
        self.ccc.setMinimumWidth(100)
        self.ccc.installEventFilter(self.wheel_filter)
        counter_layout.addWidget(self.ccc)
        
        counter_layout.addWidget(QLabel(STRINGS['batch_counter_current_row']))
        self.ccr = QSpinBox()
        self.ccr.setMinimum(1)
        self.ccr.setMaximum(999999)
        self.ccr.setValue(1)
        self.ccr.setMinimumWidth(80)
        self.ccr.installEventFilter(self.wheel_filter)
        counter_layout.addWidget(self.ccr)
        
        counter_layout.addStretch()
        self.counter_panel.setVisible(False)
        rl.addWidget(self.counter_panel)
        
        # Continue from last row checkbox - left aligned like Column label
        resume_widget = QWidget()
        resume_layout = QHBoxLayout(resume_widget)
        resume_layout.setContentsMargins(20, 0, 0, 0)
        resume_layout.setSpacing(4)
        self.chk_resume = QCheckBox(STRINGS['batch_continue_from_last'])
        self.chk_resume.setChecked(True)
        resume_layout.addWidget(self.chk_resume, alignment=Qt.AlignLeft)
        resume_layout.addStretch()
        rl.addWidget(resume_widget)
    
    def _connect_signals(self):
        # Lookup column change
        def on_lcc(col):
            had_value = bool(self.lvc.currentText())
            self.lvc.clear()
            if col:
                path = os.path.join(self.project_dir, 'Данные', self.df)
                if os.path.exists(path):
                    self.lvc.addItems(self.data_reader.get_distinct_values(path, col))
                    if not had_value and self.lvc.count() > 0:
                        self.lvc.setCurrentIndex(0)
        self.lcc.currentTextChanged.connect(on_lcc)
        
        # Mode change signals - use bound methods
        self.rc.toggled.connect(self._on_mode_changed)
        self.rs.toggled.connect(self._on_mode_changed)
        self.ry.toggled.connect(self._on_mode_changed)
        
        # Radio button exclusivity
        self.rc.toggled.connect(self._on_rc_toggled)
        self.rs.toggled.connect(self._on_rs_toggled)
        self.ry.toggled.connect(self._on_ry_toggled)
        
        # Auto-info update
        self.rc.toggled.connect(self.parent._update_auto_info)
        self.rs.toggled.connect(self.parent._update_auto_info)
    
    @pyqtSlot(bool)
    def _on_rc_toggled(self, checked):
        if checked:
            self._set_radio_exclusive(self.rc)
            self._on_mode_changed(checked)
    
    @pyqtSlot(bool)
    def _on_rs_toggled(self, checked):
        if checked:
            self._set_radio_exclusive(self.rs)
            self._on_mode_changed(checked)
    
    @pyqtSlot(bool)
    def _on_ry_toggled(self, checked):
        if checked:
            self._set_radio_exclusive(self.ry)
            self._on_mode_changed(checked)
    
    def _set_radio_exclusive(self, active_btn):
        for btn in (self.rc, self.rs, self.ry):
            if btn is not active_btn:
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
    
    @pyqtSlot(bool)
    def _on_mode_changed(self, checked):
        is_sequential = self.rs.isChecked()
        is_circular = self.ry.isChecked()
        lp_visible = self.rc.isChecked()
        
        self.lp.setVisible(lp_visible)
        self.counter_panel.setVisible(is_sequential or is_circular)
        
        if (is_sequential or is_circular) and self.ccc.count() > 0:
            if self.ccc.currentIndex() < 0:
                self.ccc.setCurrentIndex(0)
    
    def _set_initial_state(self):
        self.rc.setChecked(True)
        self._on_mode_changed(False)
        
        # Auto-select first column and trigger value population
        if self.lcc.count() > 0:
            # Set to -1 first to ensure signal emission when setting to 0
            self.lcc.setCurrentIndex(-1)
            self.lcc.setCurrentIndex(0)
    
    def get_widgets_dict(self):
        """Return dictionary of widgets for external access."""
        return {
            'radio_constant': self.rc,
            'radio_sequential': self.rs,
            'radio_circular': self.ry,
            'lookup_panel': self.lp,
            'lookup_col_combo': self.lcc,
            'lookup_val_combo': self.lvc,
            'counter_panel': self.counter_panel,
            'counter_col_combo': self.ccc,
            'counter_row_spin': self.ccr,
            'chk_resume': self.chk_resume,
        }


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
        """Update the resume info label with per-source counter summary."""
        resume = self.config.resume
        if not resume.sources:
            self.resume_info_label.setText('')
            return
        parts = ['%s: \u0441\u0442\u0440\u043e\u043a\u0430 %d' % (f, r + 1) for f, r in resume.sources.items()]
        if resume.last_counter_value > 0:
            parts.append('\u0441\u0447\u0451\u0442\u0447\u0438\u043a: %d' % resume.last_counter_value)
        self.resume_info_label.setText(STRINGS['batch_counter_summary'].format(counters=', '.join(parts)) if parts else '')
    
    def _rebuild_batch_source_rows(self):
        layout = self.batch_sources_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self.batch_source_widgets = {}
        
        for i, df in enumerate(self.data_files):
            columns = self._get_columns(df)
            row = BatchSourceRow(self, df, columns, self._wheel_filter, self.data_reader, self.project_dir)
            self.batch_source_widgets[df] = row.get_widgets_dict()
            layout.addWidget(row.row_widget)