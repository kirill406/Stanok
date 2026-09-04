# -*- coding: utf-8 -*-
"""Fill form dialog: map template fields to data sources, then render."""

import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QComboBox, QLineEdit, QScrollArea,
                              QWidget, QGroupBox, QCheckBox, QMessageBox,
                              QFileDialog, QProgressDialog, QFrame, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from docxforge.engine.template_parser import scan_template
from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
    CycleMapping, AggregationMapping, AggregationFunction,
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer
from docxforge.gui.field_dialog import FieldTemplateDialog


FIELD_TYPES = ['константа', 'таблица', 'счётчик', 'сегодня', 'изображение']
FIELD_TYPES_ENUM = {
    'константа': FieldType.CONSTANT,
    'таблица': FieldType.TABLE,
    'счётчик': FieldType.COUNTER,
    'сегодня': FieldType.TODAY,
    'изображение': FieldType.IMAGE,
}


class FillForm(QDialog):
    def __init__(self, project_dir: str, template_rel_path: str, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.template_rel_path = template_rel_path
        self.template_path = os.path.join(project_dir, 'Шаблоны', template_rel_path)
        self.data_reader = DataReader()
        self.renderer = Renderer(project_dir, self.data_reader)
        self.renderer.load_project()

        self.scan_result = scan_template(self.template_path)
        self.config = self.renderer.project.templates.get(
            template_rel_path, TemplateConfig())
        self.field_widgets = {}
        self.data_files = self._scan_data_files()
        self.columns_cache = {}

        self.setWindowTitle('Заполнение: %s' % os.path.basename(self.template_path))
        self.resize(750, 620)
        self._build_ui()
        self._populate_fields()
        self._load_existing_config()

    def _scan_data_files(self):
        data_dir = os.path.join(self.project_dir, 'Данные')
        if not os.path.exists(data_dir):
            return []
        return sorted([f for f in os.listdir(data_dir) if f.endswith(('.xlsx', '.xls'))])

    def _get_columns(self, filename):
        if filename not in self.columns_cache:
            path = os.path.join(self.project_dir, 'Данные', filename)
            if os.path.exists(path):
                self.columns_cache[filename] = self.data_reader.get_columns(path)
            else:
                self.columns_cache[filename] = []
        return self.columns_cache[filename]

    def _get_all_fields(self):
        """Return list of all field names in form (for linked-to combos)."""
        return list(self.field_widgets.keys())

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 10)
        main_layout.setSpacing(10)

        # Header
        info = QLabel('Шаблон: %s' % os.path.basename(self.template_path))
        info.setFont(QFont('Segoe UI', 11, QFont.Bold))
        main_layout.addWidget(info)

        placeholder_count = (len(self.scan_result['simple']) +
                           len(self.scan_result['today']) +
                           len(self.scan_result['doc_number']) +
                           len(self.scan_result['image']))
        stats = QLabel(
            'Полей в шаблоне: %d (%d настраиваемых, %d дат, %d номеров, %d изображений)' %
            (placeholder_count, len(self.scan_result['simple']),
             len(self.scan_result['today']), len(self.scan_result['doc_number']),
             len(self.scan_result['image'])))
        stats.setStyleSheet('color: #666;')
        main_layout.addWidget(stats)

        # + Add field button
        add_btn_layout = QHBoxLayout()
        add_btn_layout.addStretch()
        btn_add_field = QPushButton('+ Добавить поле')
        btn_add_field.setFont(QFont('Segoe UI', 9))
        btn_add_field.clicked.connect(self._add_field_dialog)
        add_btn_layout.addWidget(btn_add_field)
        main_layout.addLayout(add_btn_layout)

        # Scrollable field list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.fields_widget = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_widget)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(6)

        scroll.setWidget(self.fields_widget)
        main_layout.addWidget(scroll, stretch=1)

        # Advanced section
        self.advanced_group = QGroupBox('Дополнительно: циклы и агрегации')
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        self.advanced_layout = QVBoxLayout(self.advanced_group)

        self.cycles_widget = QWidget()
        self.cycles_layout = QVBoxLayout(self.cycles_widget)
        self.advanced_layout.addWidget(self.cycles_widget)

        btn_add_cycle = QPushButton('+ Добавить цикл')
        btn_add_cycle.clicked.connect(self._add_cycle_row)
        self.advanced_layout.addWidget(btn_add_cycle)

        self.aggr_widget = QWidget()
        self.aggr_layout = QVBoxLayout(self.aggr_widget)
        self.advanced_layout.addWidget(self.aggr_widget)

        btn_add_aggr = QPushButton('+ Добавить агрегацию')
        btn_add_aggr.clicked.connect(self._add_aggr_row)
        self.advanced_layout.addWidget(btn_add_aggr)

        main_layout.addWidget(self.advanced_group)

        # Batch section
        batch_group = QGroupBox('Генерация')
        batch_layout = QVBoxLayout(batch_group)

        radio_layout = QHBoxLayout()
        self.radio_single = QPushButton('Один документ')
        self.radio_single.setCheckable(True)
        self.radio_single.setChecked(True)
        self.radio_single.clicked.connect(lambda: self._toggle_batch(False))

        self.radio_batch = QPushButton('Несколько — по строкам таблицы')
        self.radio_batch.setCheckable(True)
        self.radio_batch.clicked.connect(lambda: self._toggle_batch(True))

        radio_layout.addWidget(self.radio_single)
        radio_layout.addWidget(self.radio_batch)
        batch_layout.addLayout(radio_layout)

        self.batch_panel = QWidget()
        batch_panel_layout = QHBoxLayout(self.batch_panel)
        batch_panel_layout.setContentsMargins(0, 0, 0, 0)
        batch_panel_layout.addWidget(QLabel('Таблица-источник:'))
        self.batch_combo = QComboBox()
        self.batch_combo.addItems(self.data_files)
        batch_panel_layout.addWidget(self.batch_combo)
        self.batch_panel.setVisible(False)
        batch_layout.addWidget(self.batch_panel)

        main_layout.addWidget(batch_group)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_validate = QPushButton('Проверить')
        btn_validate.clicked.connect(self._validate)
        btn_layout.addWidget(btn_validate)
        btn_create = QPushButton('Создать')
        btn_create.setMinimumWidth(120)
        btn_create.clicked.connect(self._create)
        btn_layout.addWidget(btn_create)
        main_layout.addLayout(btn_layout)

    def _populate_fields(self):
        """Create widget row for each simple field AND doc_number fields."""
        for field_name in self.scan_result['simple']:
            self._add_field_row(field_name)

        # Also show doc_number fields so user can configure counter
        for raw in self.scan_result.get('doc_number', []):
            # raw is like 'doc_number' or 'doc_number:0001'
            base = raw.split(':')[0]
            if base not in self.field_widgets:
                self._add_field_row(base, preset_type='счётчик')

    def _add_field_row(self, field_name, preset_type='константа'):
        if field_name in self.field_widgets:
            return  # already exists

        group = QGroupBox()
        row = QHBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)

        label = QLabel('{{{{ %s }}}}' % field_name)
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
        const_value.setPlaceholderText('значение')

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
        image_file.setPlaceholderText('путь к изображению')

        image_btn = QPushButton('📎')
        image_btn.setMaximumWidth(40)
        image_btn.clicked.connect(lambda: image_file.setText(
            QFileDialog.getOpenFileName(self, 'Выберите изображение',
                                         self.project_dir,
                                         'Изображения (*.png *.jpg *.jpeg *.bmp)')[0]))

        self.field_widgets[field_name] = {
            'type_combo': type_combo,
            'const_value': const_value,
            'table_file': table_file,
            'table_column': table_column,
            'counter_start': counter_start,
            'counter_format': counter_format,
            'today_format': today_format,
            'image_file': image_file,
        }

        stack_layout.addWidget(const_value)
        stack_layout.addWidget(QLabel('Файл:'))
        stack_layout.addWidget(table_file)
        stack_layout.addWidget(QLabel('Столбец:'))
        stack_layout.addWidget(table_column)
        stack_layout.addWidget(QLabel('Начало:'))
        stack_layout.addWidget(counter_start)
        stack_layout.addWidget(QLabel('Формат:'))
        stack_layout.addWidget(counter_format)
        stack_layout.addWidget(QLabel('Формат:'))
        stack_layout.addWidget(today_format)
        stack_layout.addWidget(image_file)
        stack_layout.addWidget(image_btn)

        row.addWidget(stack)
        self.fields_layout.addWidget(group)
        self._on_type_changed(field_name, preset_type)

    def _on_type_changed(self, field_name, type_name):
        w = self.field_widgets.get(field_name)
        if not w:
            return
        w['const_value'].setVisible(type_name == 'константа')
        for key in ['table_file', 'table_column']:
            if key in w:
                w[key].setVisible(type_name == 'таблица')
        w['counter_start'].setVisible(type_name == 'счётчик')
        w['counter_format'].setVisible(type_name == 'счётчик')
        w['today_format'].setVisible(type_name == 'сегодня')
        w['image_file'].setVisible(type_name == 'изображение')

    def _add_field_dialog(self):
        """Open the 'Add Field' template dialog."""
        existing = self._get_all_fields()
        dlg = FieldTemplateDialog(
            data_files=self.data_files,
            existing_fields=existing,
            parent=self)
        if dlg.exec_() == QDialog.Accepted:
            result = dlg.get_result()
            if result and result.get('field_name'):
                field_name = result['field_name'].strip()
                if field_name in self.field_widgets:
                    QMessageBox.warning(self, 'Ошибка',
                                         'Поле %s уже существует' % field_name)
                    return
                self._add_field_row(field_name, preset_type=result.get('type', 'константа'))
                # Fill in details from dialog
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

    def _load_existing_config(self):
        for field_name, fm in self.config.fields.items():
            # Ensure widget exists
            if field_name not in self.field_widgets:
                preset = 'константа'
                if fm.type == FieldType.COUNTER:
                    preset = 'счётчик'
                elif fm.type == FieldType.TODAY:
                    preset = 'сегодня'
                elif fm.type == FieldType.TABLE:
                    preset = 'таблица'
                elif fm.type == FieldType.IMAGE:
                    preset = 'изображение'
                self._add_field_row(field_name, preset_type=preset)

            w = self.field_widgets.get(field_name)
            if not w:
                continue
            type_name = next((k for k, v in FIELD_TYPES_ENUM.items()
                             if v == fm.type), 'константа')
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

        for cycle in self.config.cycles:
            self._add_cycle_row(cycle.table, cycle.columns)

        for aname, agg in self.config.aggregations.items():
            self._add_aggr_row(aname, agg.function.value, agg.table,
                               agg.column, agg.multiplier)

    def _add_cycle_row(self, table='', columns=None):
        group = QGroupBox('Цикл')
        row = QVBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)

        top = QHBoxLayout()
        top.addWidget(QLabel('Таблица:'))
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
            col_name.setPlaceholderText('имя поля в шаблоне')
            cols_layout.addWidget(QLabel('Поле:'), r, 0)
            cols_layout.addWidget(col_name, r, 1)
            col_val = QComboBox()
            col_val.setEditable(True)
            if table:
                col_val.addItems(self._get_columns(table))
            cols_layout.addWidget(QLabel('Столбец:'), r, 2)
            cols_layout.addWidget(col_val, r, 3)
            return col_name, col_val

        if columns:
            for cname, cval in columns.items():
                add_column_row(cname, cval)

        add_btn = QPushButton('+ Поле')
        add_btn.clicked.connect(lambda: add_column_row())
        row.addWidget(add_btn)

        group.setProperty('file_combo', file_combo)
        group.setProperty('cols_layout', cols_layout)
        self.cycles_layout.addWidget(group)

    def _add_aggr_row(self, aname='', func='sum', table='',
                      column='', multiplier=None):
        group = QGroupBox('Агрегация')
        row = QVBoxLayout(group)
        row.setContentsMargins(8, 4, 8, 4)

        top = QHBoxLayout()
        top.addWidget(QLabel('Поле в шаблоне:'))
        name_edit = QLineEdit(aname)
        name_edit.setPlaceholderText('{{ итого }}')
        top.addWidget(name_edit)
        row.addLayout(top)

        mid = QHBoxLayout()
        mid.addWidget(QLabel('Функция:'))
        func_combo = QComboBox()
        func_combo.addItems(['sum', 'sum * число', 'count', 'max', 'min'])
        idx = func_combo.findText(func)
        if idx >= 0:
            func_combo.setCurrentIndex(idx)
        mid.addWidget(func_combo)
        mid.addWidget(QLabel('Таблица:'))
        table_combo = QComboBox()
        table_combo.addItems([''] + self.data_files)
        if table:
            idx = table_combo.findText(table)
            if idx >= 0:
                table_combo.setCurrentIndex(idx)
        mid.addWidget(table_combo)
        mid.addWidget(QLabel('Столбец:'))
        col_combo = QComboBox()
        if table:
            col_combo.addItems(self._get_columns(table))
        mid.addWidget(col_combo)
        mult = QLineEdit(str(multiplier) if multiplier else '')
        mult.setPlaceholderText('множитель')
        mult.setMaximumWidth(60)
        mid.addWidget(QLabel('x'))
        mid.addWidget(mult)

        row.addLayout(mid)
        self.aggr_layout.addWidget(group)

    def _toggle_batch(self, enabled):
        self.radio_single.setChecked(not enabled)
        self.radio_batch.setChecked(enabled)
        self.batch_panel.setVisible(enabled)

    def _validate(self):
        issues = []
        for fn, w in self.field_widgets.items():
            tp = w['type_combo'].currentText()
            if tp == 'константа' and not w['const_value'].text().strip():
                issues.append('%s: константа без значения' % fn)
            elif tp == 'таблица':
                if not w['table_file'].currentText():
                    issues.append('%s: не выбран файл' % fn)
                if not w['table_column'].currentText():
                    issues.append('%s: не выбран столбец' % fn)
            elif tp == 'изображение' and not w['image_file'].text().strip():
                issues.append('%s: не выбран файл' % fn)

        if issues:
            QMessageBox.warning(self, 'Предупреждение',
                                 'Незаполненные поля:\n' + '\n'.join(issues))
        else:
            QMessageBox.information(self, 'OK', 'Все поля заполнены корректно.')

    def _create(self):
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

        # Auto-link
        seen_tables = {}
        for fn, fm in config.fields.items():
            if fm.type == FieldType.TABLE and fm.file:
                if fm.file in seen_tables:
                    fm.linked_to = seen_tables[fm.file]
                else:
                    seen_tables[fm.file] = fn

        # Cycles
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
                name_w = cols_layout.itemAtPosition(r, 1)
                val_w = cols_layout.itemAtPosition(r, 3)
                if name_w and val_w:
                    n = name_w.widget().text().strip()
                    v = val_w.widget().currentText().strip()
                    if n and v:
                        columns[n] = v
            if file_combo.currentText() and columns:
                config.cycles.append(CycleMapping(
                    table=file_combo.currentText(), columns=columns))

        # Aggregations
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
            if func_str == 'sum * число':
                func = AggregationFunction.SUM_MULTIPLY
                multiplier = float(mult_w.text() or '1')
            elif func_str in ('sum', 'count', 'max', 'min'):
                func = AggregationFunction(func_str)
                multiplier = None
            else:
                continue
            config.aggregations[aname] = AggregationMapping(
                function=func, table=table, column=column, multiplier=multiplier)

        self.renderer.project.templates[self.template_rel_path] = config
        self.renderer.save_project()

        user_values = {}
        for fn, fm in config.fields.items():
            if fm.type == FieldType.CONSTANT:
                user_values[fn] = fm.value or ''
            elif fm.type == FieldType.IMAGE:
                user_values[fn] = fm.value or fm.file or ''

        batch_table = self.batch_combo.currentText() if self.radio_batch.isChecked() else None

        progress = QProgressDialog('Генерация документов...', 'Отмена', 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        try:
            output_dir = os.path.join(self.project_dir, 'output')
            outputs = self.renderer.render(
                self.template_rel_path, user_values,
                batch_table=batch_table, output_dir=output_dir)
            progress.close()
            QMessageBox.information(
                self, 'Готово',
                'Создано документов: %d\nПапка: %s\nПервый файл: %s' %
                (len(outputs), output_dir,
                 os.path.basename(outputs[0]) if outputs else '—'))
        except Exception as e:
            progress.close()
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, 'Ошибка',
                                 'Не удалось создать документ:\n%s' % str(e))
