# -*- coding: utf-8 -*-
"""Dialog for adding a new field with template picker showing previews."""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QComboBox, QLineEdit, QGroupBox,
                              QDialogButtonBox, QWidget, QScrollArea,
                              QFrame, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

FIELD_TEMPLATES = [
    {
        'name': 'Константа (текст)',
        'icon': '📝',
        'description': 'Одно значение на все документы. Вводится вручную.',
        'example': '{{ организация }}\n→  "ООО Ромашка"',
        'type': 'константа',
        'fields': [
            {'label': 'Имя поля', 'key': 'field_name', 'widget': 'text', 'placeholder': 'организация'},
            {'label': 'Значение', 'key': 'value', 'widget': 'text', 'placeholder': 'ООО Ромашка'},
        ],
    },
    {
        'name': 'Из таблицы Excel',
        'icon': '📊',
        'description': 'Значение из Excel. При генерации выбирается строка.',
        'example': '{{ название_клиента }}\n→  "ООО Альфа" (из клиенты.xlsx, столбец название)',
        'type': 'таблица',
        'fields': [
            {'label': 'Имя поля', 'key': 'field_name', 'widget': 'text', 'placeholder': 'название_клиента'},
            {'label': 'Excel-файл', 'key': 'file', 'widget': 'combo_data', 'placeholder': 'клиенты.xlsx'},
            {'label': 'Столбец', 'key': 'column', 'widget': 'combo_column', 'placeholder': 'название'},
            {'label': 'Связать с полем', 'key': 'linked_to', 'widget': 'combo_fields', 'placeholder': '(авто)'},
        ],
    },
    {
        'name': 'Счётчик (номер документа)',
        'icon': '🔢',
        'description': 'Автоинкремент. В пакетной генерации +1 на каждый документ.',
        'example': '{{ номер }}\n→  0001, 0002, 0003...',
        'type': 'счётчик',
        'fields': [
            {'label': 'Имя поля', 'key': 'field_name', 'widget': 'text', 'placeholder': 'номер'},
            {'label': 'Начальное значение', 'key': 'start', 'widget': 'text', 'placeholder': '1'},
            {'label': 'Формат', 'key': 'format', 'widget': 'combo_counter_format', 'placeholder': '0001'},
        ],
    },
    {
        'name': 'Дата (сегодня)',
        'icon': '📅',
        'description': 'Текущая дата. Подставляется автоматически при генерации.',
        'example': '{{ дата }}\n→  04.09.2026',
        'type': 'сегодня',
        'fields': [
            {'label': 'Имя поля', 'key': 'field_name', 'widget': 'text', 'placeholder': 'дата'},
            {'label': 'Формат', 'key': 'format', 'widget': 'combo_date_format', 'placeholder': 'dd.MM.yyyy'},
        ],
    },
    {
        'name': 'Изображение',
        'icon': '🖼',
        'description': 'Картинка: логотип, подпись, печать. Выбор файла.',
        'example': '{{ image:логотип }}\n→  logo.png',
        'type': 'изображение',
        'fields': [
            {'label': 'Имя поля', 'key': 'field_name', 'widget': 'text', 'placeholder': 'логотип'},
            {'label': 'Файл изображения', 'key': 'value', 'widget': 'file', 'placeholder': 'logo.png'},
        ],
    },
]


class FieldTemplateDialog(QDialog):
    """Dialog: pick a field template, fill in details, add to form."""

    def __init__(self, data_files=None, existing_fields=None, parent=None):
        super().__init__(parent)
        self.data_files = data_files or []
        self.existing_fields = existing_fields or []
        self.result_data = None

        self.setWindowTitle('Добавить поле')
        self.setMinimumWidth(550)
        self.resize(600, 480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 10)
        layout.setSpacing(10)

        title = QLabel('Выберите тип поля')
        title.setFont(QFont('Segoe UI', 12, QFont.Bold))
        layout.addWidget(title)

        desc = QLabel('Каждый тип показывает, как поле будет выглядеть в шаблоне и в результате.')
        desc.setStyleSheet('color: #666;')
        layout.addWidget(desc)

        # Scrollable template cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        cards_widget = QWidget()
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        self.template_buttons = []
        for tpl in FIELD_TEMPLATES:
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            card.setStyleSheet('QFrame { background: white; border: 1px solid #ddd; border-radius: 6px; padding: 10px; } QFrame:hover { border-color: #0078d4; }')
            card.setCursor(Qt.PointingHandCursor)

            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            # Icon + name
            left = QVBoxLayout()
            icon_label = QLabel(tpl['icon'] + '  ' + tpl['name'])
            icon_label.setFont(QFont('Segoe UI', 11, QFont.Bold))
            left.addWidget(icon_label)

            desc_label = QLabel(tpl['description'])
            desc_label.setStyleSheet('color: #666; font-size: 9pt;')
            desc_label.setWordWrap(True)
            left.addWidget(desc_label)

            card_layout.addLayout(left, stretch=1)

            # Example preview
            example_frame = QFrame()
            example_frame.setStyleSheet('background: #f0f0f0; border-radius: 4px; padding: 6px;')
            example_layout = QVBoxLayout(example_frame)
            example_label = QLabel(tpl['example'])
            example_label.setFont(QFont('Consolas', 8))
            example_label.setStyleSheet('color: #333;')
            example_layout.addWidget(example_label)
            card_layout.addWidget(example_frame)

            # Store template data
            card.setProperty('template_data', tpl)
            card.mousePressEvent = lambda e, t=tpl: self._on_template_selected(t)

            cards_layout.addWidget(card)
            self.template_buttons.append(card)

        scroll.setWidget(cards_widget)
        layout.addWidget(scroll, stretch=1)

        # Detail form (shown after template selection)
        self.detail_group = QGroupBox('Параметры поля')
        self.detail_group.setVisible(False)
        self.detail_layout = QVBoxLayout(self.detail_group)
        self.detail_layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.detail_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        self.add_btn = QPushButton('Добавить поле')
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(self.add_btn)
        layout.addLayout(btn_layout)

        self._detail_widgets = {}

    def _on_template_selected(self, template):
        """User clicked a template card — show detail form."""
        self.selected_template = template

        # Clear previous detail widgets
        for i in reversed(range(self.detail_layout.count())):
            self.detail_layout.itemAt(i).widget().setParent(None)

        self._detail_widgets = {}

        self.detail_group.setTitle(template['name'])
        self.detail_group.setVisible(True)
        self.add_btn.setEnabled(True)

        for field_def in template['fields']:
            row = QHBoxLayout()
            label = QLabel(field_def['label'] + ':')
            label.setMinimumWidth(120)
            row.addWidget(label)

            widget_type = field_def.get('widget', 'text')
            if widget_type == 'text':
                widget = QLineEdit()
                widget.setPlaceholderText(field_def.get('placeholder', ''))
            elif widget_type == 'combo_data':
                widget = QComboBox()
                widget.addItems([''] + self.data_files)
            elif widget_type == 'combo_column':
                widget = QComboBox()
                widget.setEditable(True)
            elif widget_type == 'combo_fields':
                widget = QComboBox()
                widget.addItems(['(авто)'] + self.existing_fields)
            elif widget_type == 'combo_counter_format':
                widget = QComboBox()
                widget.addItems(['0001', '001', '00001', '1'])
            elif widget_type == 'combo_date_format':
                widget = QComboBox()
                widget.addItems(['dd.MM.yyyy', 'dd.MM.yyyy HH:mm', 'dd', 'MM', 'yyyy', 'dd.MM.yy'])
            elif widget_type == 'file':
                w = QWidget()
                wl = QHBoxLayout(w)
                wl.setContentsMargins(0, 0, 0, 0)
                widget = QLineEdit()
                widget.setPlaceholderText(field_def.get('placeholder', ''))
                wl.addWidget(widget)
                btn = QPushButton('📎')
                btn.setMaximumWidth(40)
                btn.clicked.connect(lambda: self._pick_file(widget))
                wl.addWidget(btn)
                widget = w  # hack: store the container

            row.addWidget(widget, stretch=1)
            self.detail_layout.addLayout(row)
            self._detail_widgets[field_def['key']] = widget

    def _pick_file(self, line_edit):
        from PyQt5.QtWidgets import QFileDialog
        file, _ = QFileDialog.getOpenFileName(
            self, 'Выберите изображение',
            '', 'Изображения (*.png *.jpg *.jpeg *.bmp)')
        if file:
            line_edit.setText(file)

    def _on_add(self):
        """Collect values and return."""
        tpl = self.selected_template
        result = {'type': tpl['type']}

        for key, widget in self._detail_widgets.items():
            if isinstance(widget, QLineEdit):
                result[key] = widget.text()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText()
            elif isinstance(widget, QWidget):
                # File picker container — find the QLineEdit inside
                for child in widget.findChildren(QLineEdit):
                    result[key] = child.text()
                    break

        # Validate
        if not result.get('field_name', '').strip():
            return  # silently ignore — user needs to enter a name

        self.result_data = result
        self.accept()

    def get_result(self):
        return self.result_data
