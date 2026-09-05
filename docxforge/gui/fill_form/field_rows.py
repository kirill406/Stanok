# -*- coding: utf-8 -*-
"""Field rows mixin: populate, add, and configure individual field rows."""

from PyQt5.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QComboBox,
                              QLineEdit, QPushButton, QFileDialog, QWidget, QMessageBox)
from PyQt5.QtGui import QFont

from docxforge.gui.field_dialog import FieldTemplateDialog
from .constants import FIELD_TYPES, FIELD_TYPES_ENUM


class FieldRowsMixin:
    """Methods for managing individual field widget rows in FillForm."""

    def _populate_fields(self):
        """Create widget row for each simple field AND doc_number fields."""
        for field_name in self.scan_result['simple']:
            self._add_field_row(field_name)

        # Also show doc_number fields so user can configure counter
        for raw in self.scan_result.get('doc_number', []):
            base = raw.split(':')[0]
            if base not in self.field_widgets:
                self._add_field_row(base, preset_type='\u0441\u0447\u0451\u0442\u0447\u0438\u043a')

    def _add_field_row(self, field_name, preset_type='\u043a\u043e\u043d\u0441\u0442\u0430\u043d\u0442\u0430'):
        if field_name in self.field_widgets:
            return

        group = QGroupBox()
        row = QHBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)

        label = QLabel('{{ %s }}' % field_name)
        label.setMinimumWidth(150)
        label.setFont(QFont('Consolas', 9))
        row.addWidget(label)

        type_combo = QComboBox()
        type_combo.addItems(FIELD_TYPES)
        type_combo.setCurrentText(preset_type)
        type_combo.currentTextChanged.connect(
            lambda t, fn=field_name: self._on_type_changed(fn, t))
        row.addWidget(type_combo)

        stack = QWidget()
        stack_layout = QHBoxLayout(stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        const_value = QLineEdit()
        const_value.setPlaceholderText('\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435')

        table_file = QComboBox()
        table_file.addItems([''] + self.data_files)
        table_column = QComboBox()

        def on_tf_changed(tf, tc=table_column):
            tc.clear()
            if tf:
                tc.addItems(self._get_columns(tf))
        table_file.currentTextChanged.connect(on_tf_changed)

        counter_start = QLineEdit('1')
        counter_start.setMaximumWidth(60)
        counter_format = QComboBox()
        counter_format.addItems(['1', '0001', '001', '00001'])

        today_format = QComboBox()
        today_format.addItems(['dd.MM.yyyy', 'dd.MM.yyyy HH:mm', 'dd', 'MM', 'yyyy', 'dd.MM.yy'])

        image_file = QLineEdit()
        image_file.setPlaceholderText('\u043f\u0443\u0442\u044c \u043a \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044e')

        image_btn = QPushButton('\U0001f4ce')
        image_btn.setMaximumWidth(40)
        image_btn.clicked.connect(lambda: image_file.setText(
            QFileDialog.getOpenFileName(self, '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435',
                                         self.project_dir,
                                         '\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f (*.png *.jpg *.jpeg *.bmp)')[0]))

        lbl_file = QLabel('\u0424\u0430\u0439\u043b:')
        lbl_column = QLabel('\u0421\u0442\u043e\u043b\u0431\u0435\u0446:')
        lbl_start = QLabel('\u041d\u0430\u0447\u0430\u043b\u043e:')
        lbl_counter_format = QLabel('\u0424\u043e\u0440\u043c\u0430\u0442:')
        lbl_today_format = QLabel('\u0424\u043e\u0440\u043c\u0430\u0442:')
        lbl_image = QLabel('\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435:')

        self.field_widgets[field_name] = {
            'type_combo': type_combo,
            'const_value': const_value,
            'table_file': table_file,
            'table_column': table_column,
            'counter_start': counter_start,
            'counter_format': counter_format,
            'today_format': today_format,
            'image_file': image_file,
            'image_btn': image_btn,
            'lbl_file': lbl_file,
            'lbl_column': lbl_column,
            'lbl_start': lbl_start,
            'lbl_counter_format': lbl_counter_format,
            'lbl_today_format': lbl_today_format,
            'lbl_image': lbl_image,
        }

        stack_layout.addWidget(const_value)
        stack_layout.addWidget(lbl_file)
        stack_layout.addWidget(table_file)
        stack_layout.addWidget(lbl_column)
        stack_layout.addWidget(table_column)
        stack_layout.addWidget(lbl_start)
        stack_layout.addWidget(counter_start)
        stack_layout.addWidget(lbl_counter_format)
        stack_layout.addWidget(counter_format)
        stack_layout.addWidget(lbl_today_format)
        stack_layout.addWidget(today_format)
        stack_layout.addWidget(lbl_image)
        stack_layout.addWidget(image_file)
        stack_layout.addWidget(image_btn)

        row.addWidget(stack)
        self.fields_layout.addWidget(group)
        self._on_type_changed(field_name, preset_type)

    def _on_type_changed(self, field_name, type_name):
        w = self.field_widgets.get(field_name)
        if not w:
            return
        w['const_value'].setVisible(type_name == '\u043a\u043e\u043d\u0441\u0442\u0430\u043d\u0442\u0430')
        is_table = (type_name == '\u0442\u0430\u0431\u043b\u0438\u0446\u0430')
        w['table_file'].setVisible(is_table)
        w['table_column'].setVisible(is_table)
        w['lbl_file'].setVisible(is_table)
        w['lbl_column'].setVisible(is_table)
        is_counter = (type_name == '\u0441\u0447\u0451\u0442\u0447\u0438\u043a')
        w['counter_start'].setVisible(is_counter)
        w['counter_format'].setVisible(is_counter)
        w['lbl_start'].setVisible(is_counter)
        w['lbl_counter_format'].setVisible(is_counter)
        is_today = (type_name == '\u0441\u0435\u0433\u043e\u0434\u043d\u044f')
        w['today_format'].setVisible(is_today)
        w['lbl_today_format'].setVisible(is_today)
        is_image = (type_name == '\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435')
        w['image_file'].setVisible(is_image)
        w['image_btn'].setVisible(is_image)
        w['lbl_image'].setVisible(is_image)

    def _add_field_dialog(self):
        """Open the 'Add Field' template dialog."""
        existing = self._get_all_fields()
        dlg = FieldTemplateDialog(
            data_files=self.data_files,
            existing_fields=existing,
            parent=self)
        if dlg.exec_() == FieldTemplateDialog.Accepted:
            result = dlg.get_result()
            if result and result.get('field_name'):
                field_name = result['field_name'].strip()
                if field_name in self.field_widgets:
                    QMessageBox.warning(self, '\u041e\u0448\u0438\u0431\u043a\u0430',
                                         '\u041f\u043e\u043b\u0435 %s \u0443\u0436\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u0435\u0442' % field_name)
                    return
                self._add_field_row(field_name, preset_type=result.get('type', '\u043a\u043e\u043d\u0441\u0442\u0430\u043d\u0442\u0430'))
                w = self.field_widgets[field_name]
                if result.get('value'):
                    w['const_value'].setText(result['value'])
                if result.get('start'):
                    w['counter_start'].setText(result['start'])
                if result.get('format'):
                    idx = w['counter_format'].findText(result['format'])
                    if idx < 0:
                        idx = w['today_format'].findText(result['format'])
                    if idx >= 0:
                        w['counter_format' if 'counter' in result.get('type', '') else 'today_format'].setCurrentIndex(idx)
                if result.get('file'):
                    idx = w['table_file'].findText(result['file'])
                    if idx >= 0:
                        w['table_file'].setCurrentIndex(idx)
                if result.get('column'):
                    idx = w['table_column'].findText(result['column'])
                    if idx >= 0:
                        w['table_column'].setCurrentIndex(idx)
