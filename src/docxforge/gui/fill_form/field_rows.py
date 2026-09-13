# -*- coding: utf-8 -*-
"""Field rows mixin: populate, add, and configure individual field rows."""

from PyQt5.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QComboBox,
                              QLineEdit, QPushButton, QFileDialog, QWidget, QMessageBox, QVBoxLayout)
from PyQt5.QtGui import QFont

from docxforge.gui.field_dialog import FieldTemplateDialog
from .constants import FIELD_TYPES, FIELD_TYPES_ENUM
from ..strings import STRINGS


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
        row.setSpacing(6)  # Fixed spacing between label, type combo, and stack

        label = QLabel(field_name)
        label.setMinimumWidth(150)
        label.setFont(QFont('Consolas', 9))
        row.addWidget(label)

        type_combo = QComboBox()
        type_combo.addItems(FIELD_TYPES)
        type_combo.setCurrentText(preset_type)
        type_combo.setFixedWidth(140)  # Static width for all type combos
        type_combo.currentTextChanged.connect(
            lambda t, fn=field_name: self._on_type_changed(fn, t))
        type_combo.installEventFilter(self._wheel_filter)
        row.addWidget(type_combo)

        # Main input stack - each type gets its own aligned input area
        stack = QWidget()
        stack_layout = QHBoxLayout(stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(4)

        # Constant value input (for constant type)
        const_value = QLineEdit()
        const_value.setPlaceholderText(STRINGS.get('field_placeholder_value', '\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435'))

        # Table file input (for table type) - aligned with const_value
        table_file = QComboBox()
        table_file.addItems([''] + self.data_files)
        table_file.installEventFilter(self._wheel_filter)

        # Table column input (for table type)
        table_column = QComboBox()
        table_column.installEventFilter(self._wheel_filter)

        def on_tf_changed(tf, tc=table_column):
            tc.clear()
            if tf:
                tc.addItems(self._get_columns(tf))
        table_file.currentTextChanged.connect(on_tf_changed)

        # Counter start input (for counter type)
        counter_start = QLineEdit('1')
        counter_start.setMaximumWidth(60)

        # Counter format combo (for counter type)
        counter_format = QComboBox()
        counter_format.addItems(['1', '0001', '001', '00001'])
        counter_format.installEventFilter(self._wheel_filter)

        # Today format combo (for today type) - aligned with const_value
        today_format = QComboBox()
        today_format.addItems(['dd.MM.yyyy', 'dd.MM.yyyy HH:mm', 'dd', 'MM', 'yyyy', 'dd.MM.yy', STRINGS['today_format_month']])
        today_format.installEventFilter(self._wheel_filter)

        # Image file input (for image type)
        image_file = QLineEdit()
        image_file.setPlaceholderText(STRINGS.get('field_placeholder_image', '\u043f\u0443\u0442\u044c \u043a \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435'))

        image_btn = QPushButton('\U0001f4ce')
        image_btn.setMaximumWidth(40)
        image_btn.clicked.connect(lambda: image_file.setText(
            QFileDialog.getOpenFileName(self, STRINGS.get('field_dialog_select_image', '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435'),
                                         self.project_dir,
                                         STRINGS.get('field_filter_image', '\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 (*.png *.jpg *.jpeg *.bmp)'))[0]))

        lbl_file = QLabel(STRINGS['field_label_file'])
        lbl_column = QLabel(STRINGS['field_label_column'])
        lbl_start = QLabel(STRINGS['field_label_start'])
        lbl_counter_format = QLabel(STRINGS['field_label_counter_format'])
        lbl_today_format = QLabel(STRINGS['field_label_today_format'])
        lbl_image = QLabel(STRINGS['field_label_image'])

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

        # Add all widgets to stack layout
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

        row.addWidget(stack, 1)  # Stretch factor 1: stack expands, label and type_combo stay fixed
        self.fields_layout.addWidget(group)
        self._on_type_changed(field_name, preset_type)

    def _on_type_changed(self, field_name, type_name):
        w = self.field_widgets.get(field_name)
        if not w:
            return
        # Show/hide widgets based on type, keeping alignment consistent
        is_constant = (type_name == STRINGS['field_type_constant'])
        is_table = (type_name == STRINGS['field_type_table'])
        is_counter = (type_name == STRINGS['field_type_counter'])
        is_today = (type_name == STRINGS['field_type_today'])
        is_image = (type_name == STRINGS['field_type_image'])

        # Auto-fill constant value with {{field_name}} when type changes to constant
        if is_constant and not w['const_value'].text():
            w['const_value'].setText('{{ %s }}' % field_name)

        # Main input area - always show the primary input for the current type
        w['const_value'].setVisible(is_constant)
        w['table_file'].setVisible(is_table)
        w['today_format'].setVisible(is_today)
        w['image_file'].setVisible(is_image)
        w['image_btn'].setVisible(is_image)

        # Secondary inputs for table type - hide "Файл:" label for alignment
        w['table_column'].setVisible(is_table)
        w['lbl_file'].setVisible(False)  # Hidden for alignment with constant type
        w['lbl_column'].setVisible(is_table)

        # Counter inputs
        w['counter_start'].setVisible(is_counter)
        w['counter_format'].setVisible(is_counter)
        w['lbl_start'].setVisible(is_counter)
        w['lbl_counter_format'].setVisible(is_counter)

        # Today format label - hidden for alignment with constant type
        w['lbl_today_format'].setVisible(False)

        # Image
        w['lbl_image'].setVisible(is_image)
        w['image_btn'].setVisible(is_image)

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
                    QMessageBox.warning(self, STRINGS['msg_warning'],
                                         STRINGS['msg_field_exists'].format(name=field_name))
                    return
                self._add_field_row(field_name, preset_type=result.get('type', STRINGS['field_type_constant']))
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