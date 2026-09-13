# -*- coding: utf-8 -*-
"""Advanced section mixin: cycle rows, aggregation rows, and advanced toggle."""

from PyQt5.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout,
                              QLabel, QComboBox, QLineEdit, QPushButton,
                              QWidget, QGridLayout)


class AdvancedSectionMixin:
    """Methods for managing cycle and aggregation rows in FillForm."""

    def _add_cycle_row(self, table='', columns=None):
        group = QGroupBox('\u0426\u0438\u043a\u043b')
        row = QVBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)

        top = QHBoxLayout()
        top.addWidget(QLabel('\u0422\u0430\u0431\u043b\u0438\u0446\u0430:'))
        file_combo = QComboBox()
        file_combo.addItems([''] + self.data_files)
        if table:
            idx = file_combo.findText(table)
            if idx >= 0:
                file_combo.setCurrentIndex(idx)
        top.addWidget(file_combo)
        row.addLayout(top)

        cols_layout = QGridLayout()
        row.addLayout(cols_layout)

        def add_column_row(cname='', cval=''):
            r = cols_layout.rowCount()
            col_name = QLineEdit(cname)
            col_name.setPlaceholderText('\u0438\u043c\u044f \u043f\u043e\u043b\u044f \u0432 \u0448\u0430\u0431\u043b\u043e\u043d\u0435')
            cols_layout.addWidget(QLabel('\u041f\u043e\u043b\u0435:'), r, 0)
            cols_layout.addWidget(col_name, r, 1)
            col_val = QComboBox()
            col_val.setEditable(True)
            if table:
                col_val.addItems(self._get_columns(table))
            cols_layout.addWidget(QLabel('\u0421\u0442\u043e\u043b\u0431\u0435\u0446:'), r, 2)
            cols_layout.addWidget(col_val, r, 3)
            return col_name, col_val

        if columns:
            for cname, cval in columns.items():
                add_column_row(cname, cval)

        add_btn = QPushButton('+ \u041f\u043e\u043b\u0435')
        add_btn.clicked.connect(lambda: add_column_row())
        row.addWidget(add_btn)

        group.setProperty('file_combo', file_combo)
        group.setProperty('cols_layout', cols_layout)
        self.cycles_layout.addWidget(group)

    def _add_aggr_row(self, aname='', func='sum', table='',
                      column='', multiplier=None):
        group = QGroupBox('\u0410\u0433\u0440\u0435\u0433\u0430\u0446\u0438\u044f')
        row = QVBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)

        top = QHBoxLayout()
        top.addWidget(QLabel('\u041f\u043e\u043b\u0435 \u0432 \u0448\u0430\u0431\u043b\u043e\u043d\u0435:'))
        name_edit = QLineEdit(aname)
        name_edit.setPlaceholderText('{{ \u0438\u0442\u043e\u0433\u043e }}')
        top.addWidget(name_edit)
        row.addLayout(top)

        mid = QHBoxLayout()
        mid.addWidget(QLabel('\u0424\u0443\u043d\u043a\u0446\u0438\u044f:'))
        func_combo = QComboBox()
        func_combo.addItems(['sum', 'sum * \u0447\u0438\u0441\u043b\u043e', 'count', 'max', 'min'])
        idx = func_combo.findText(func)
        if idx >= 0:
            func_combo.setCurrentIndex(idx)
        mid.addWidget(func_combo)
        mid.addWidget(QLabel('\u0422\u0430\u0431\u043b\u0438\u0446\u0430:'))
        table_combo = QComboBox()
        table_combo.addItems([''] + self.data_files)
        if table:
            idx = table_combo.findText(table)
            if idx >= 0:
                table_combo.setCurrentIndex(idx)
        mid.addWidget(table_combo)
        mid.addWidget(QLabel('\u0421\u0442\u043e\u043b\u0431\u0435\u0446:'))
        col_combo = QComboBox()
        if table:
            col_combo.addItems(self._get_columns(table))
        mid.addWidget(col_combo)
        mult = QLineEdit(str(multiplier) if multiplier else '')
        mult.setPlaceholderText('\u043c\u043d\u043e\u0436\u0438\u0442\u0435\u043b\u044c')
        mult.setMaximumWidth(60)
        mid.addWidget(QLabel('x'))
        mid.addWidget(mult)

        row.addLayout(mid)
        self.aggr_layout.addWidget(group)

    def _on_advanced_toggled(self, checked):
        self.btn_add_cycle.setVisible(checked)
        self.btn_add_aggr.setVisible(checked)
        self.cycles_widget.setVisible(checked)
        self.aggr_widget.setVisible(checked)

    def _on_auto_docs_toggled(self, checked):
        self.spin_total_docs.setVisible(not checked)
        self.spin_total_docs.setEnabled(not checked)
        self._update_auto_info()

    def _get_row_count(self, filename):
        """Get number of data rows in an Excel file."""
        import os
        path = os.path.join(self.project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435', filename)
        if os.path.exists(path):
            return len(self.data_reader.read_excel(path))
        return 0