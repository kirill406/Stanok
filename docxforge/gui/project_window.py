# -*- coding: utf-8 -*-
"""Project window: shows template tree, data files, and opens fill form."""

import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
                              QListWidget, QListWidgetItem, QFileDialog,
                              QMessageBox, QSplitter)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from docxforge.gui.fill_form import FillForm
from docxforge.engine.template_parser import scan_template
from docxforge.engine.schema import Project, TemplateConfig, FieldMapping, FieldType
from docxforge.engine.data_reader import DataReader


class ProjectWindow(QMainWindow):
    def __init__(self, project_dir: str, main_window):
        super().__init__()
        self.project_dir = project_dir
        self.main_window = main_window
        self.data_reader = DataReader()

        self.setWindowTitle(f'DocxForge — {os.path.basename(project_dir)}')
        self.resize(800, 550)
        self._build_ui()
        self._scan_project()
        self._center()

    def _center(self):
        frame = self.frameGeometry()
        screen = self.app().primaryScreen().availableGeometry().center()
        frame.moveCenter(screen)
        self.move(frame.topLeft())

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        title = QLabel(f'Проект: {os.path.basename(self.project_dir)}')
        title.setFont(QFont('Segoe UI', 14, QFont.Bold))
        header.addWidget(title)
        header.addStretch()
        btn_back = QPushButton('←  Назад к проектам')
        btn_back.setFont(QFont('Segoe UI', 9))
        btn_back.clicked.connect(self._go_back)
        header.addWidget(btn_back)
        layout.addLayout(header)

        # Splitter: templates left, data right
        splitter = QSplitter(Qt.Horizontal)

        # Templates panel
        templates_widget = QWidget()
        tpl_layout = QVBoxLayout(templates_widget)
        tpl_layout.setContentsMargins(0, 0, 0, 0)

        tpl_header = QHBoxLayout()
        tpl_label = QLabel('Шаблоны')
        tpl_label.setFont(QFont('Segoe UI', 11, QFont.Bold))
        tpl_header.addWidget(tpl_label)
        tpl_header.addStretch()
        btn_add_tpl = QPushButton('+ Добавить')
        btn_add_tpl.setFont(QFont('Segoe UI', 9))
        btn_add_tpl.clicked.connect(self._add_template)
        tpl_header.addWidget(btn_add_tpl)
        tpl_layout.addLayout(tpl_header)

        self.templates_tree = QTreeWidget()
        self.templates_tree.setHeaderLabels(['Шаблон', ''])
        self.templates_tree.setColumnWidth(0, 300)
        self.templates_tree.itemDoubleClicked.connect(self._open_fill_form)
        tpl_layout.addWidget(self.templates_tree)

        splitter.addWidget(templates_widget)

        # Data panel
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        data_layout.setContentsMargins(0, 0, 0, 0)

        data_header = QHBoxLayout()
        data_label = QLabel('Данные')
        data_label.setFont(QFont('Segoe UI', 11, QFont.Bold))
        data_header.addWidget(data_label)
        data_header.addStretch()
        btn_add_data = QPushButton('+ Добавить')
        btn_add_data.setFont(QFont('Segoe UI', 9))
        btn_add_data.clicked.connect(self._add_data)
        data_header.addWidget(btn_add_data)
        data_layout.addLayout(data_header)

        self.data_list = QListWidget()
        self.data_list.setFont(QFont('Segoe UI', 10))
        data_layout.addWidget(self.data_list)

        splitter.addWidget(data_widget)
        splitter.setSizes([450, 250])
        layout.addWidget(splitter)

    def _scan_project(self):
        """Scan template and data directories."""
        # Templates
        self.templates_tree.clear()
        templates_dir = os.path.join(self.project_dir, 'Шаблоны')
        if os.path.exists(templates_dir):
            self._scan_dir(templates_dir, self.templates_tree, templates_dir)

        # Data
        self.data_list.clear()
        data_dir = os.path.join(self.project_dir, 'Данные')
        if os.path.exists(data_dir):
            for f in sorted(os.listdir(data_dir)):
                if f.endswith(('.xlsx', '.xls')):
                    self.data_list.addItem(f'📊 {f}')

    def _scan_dir(self, base_dir, parent_item, root_dir):
        """Recursively scan directory for .docx files."""
        items = sorted(os.listdir(base_dir))
        for name in items:
            full = os.path.join(base_dir, name)
            rel = os.path.relpath(full, root_dir).replace('\\', '/')
            if os.path.isdir(full):
                sub_tree = QTreeWidgetItem(parent_item if isinstance(parent_item, QTreeWidget) else [parent_item])
                sub_tree.setText(0, f'📁 {name}')
                sub_tree.setText(1, rel)
                self._scan_dir(full, sub_tree, root_dir)
            elif name.endswith('.docx'):
                item = QTreeWidgetItem(parent_item if isinstance(parent_item, QTreeWidget) else [parent_item])
                item.setText(0, f'📄 {name}')
                item.setText(1, rel)
                # Button
                btn = QPushButton('Заполнить')
                btn.setFont(QFont('Segoe UI', 8))
                btn.clicked.connect(lambda checked, p=rel: self._open_fill_form(p))
                if isinstance(parent_item, QTreeWidget):
                    self.templates_tree.setItemWidget(item, 1, btn)
                else:
                    # For nested items we need a different approach
                    pass

        # Add fill buttons to all leaf items
        self._add_buttons_recursive(self.templates_tree)

    def _add_buttons_recursive(self, parent):
        for i in range(parent.topLevelItemCount() if isinstance(parent, QTreeWidget) else parent.childCount()):
            item = parent.topLevelItem(i) if isinstance(parent, QTreeWidget) else parent.child(i)
            if item.childCount() == 0:  # leaf = .docx file
                if not self.templates_tree.itemWidget(item, 1):
                    btn = QPushButton('Заполнить')
                    btn.setFont(QFont('Segoe UI', 8))
                    rel_path = item.text(1)
                    btn.clicked.connect(lambda checked, p=rel_path: self._open_fill_form(p))
                    self.templates_tree.setItemWidget(item, 1, btn)
            else:
                self._add_buttons_recursive(item)

    def _open_fill_form(self, rel_path=None):
        """Open the fill form dialog for a template."""
        if rel_path is None:
            # From double-click
            current = self.templates_tree.currentItem()
            if current and current.childCount() == 0:
                rel_path = current.text(1)
            else:
                return

        if isinstance(rel_path, bool):  # Clicked signal passes checked=False
            current = self.templates_tree.currentItem()
            if current and current.childCount() == 0:
                rel_path = current.text(1)
            else:
                return

        full_path = os.path.join(self.project_dir, 'Шаблоны', rel_path)
        if not os.path.exists(full_path):
            QMessageBox.warning(self, 'Ошибка', f'Шаблон не найден: {full_path}')
            return

        dlg = FillForm(self.project_dir, rel_path, self)
        dlg.exec_()
        self._scan_project()

    def _add_template(self):
        file, _ = QFileDialog.getOpenFileName(
            self, 'Выберите шаблон .docx',
            os.path.expanduser('~'), 'Word документы (*.docx)')
        if file:
            # Copy to templates dir
            import shutil
            dest = os.path.join(self.project_dir, 'Шаблоны',
                                os.path.basename(file))
            if not os.path.exists(dest):
                shutil.copy2(file, dest)
            self._scan_project()

    def _add_data(self):
        file, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл данных',
            os.path.expanduser('~'), 'Excel файлы (*.xlsx *.xls)')
        if file:
            import shutil
            dest = os.path.join(self.project_dir, 'Данные',
                                os.path.basename(file))
            if not os.path.exists(dest):
                shutil.copy2(file, dest)
            self._scan_project()

    def _go_back(self):
        self.main_window.show()
        # Refresh recent
        self.main_window._add_recent(self.project_dir)
        self.main_window._refresh_recent_list()
        self.close()

    def closeEvent(self, event):
        self.main_window._add_recent(self.project_dir)
        self.main_window._refresh_recent_list()
        super().closeEvent(event)
