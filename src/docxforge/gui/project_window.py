# -*- coding: utf-8 -*-
"""Project window: shows template tree, data files, and opens fill form."""

import os
import shutil
import logging
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
                              QListWidget, QListWidgetItem, QFileDialog,
                              QMessageBox, QSplitter, QApplication, QToolButton)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from docxforge.gui.fill_form import FillForm
from docxforge.engine.data_reader import DataReader
from .strings import STRINGS

logger = logging.getLogger(__name__)


class ProjectWindow(QMainWindow):
    def __init__(self, project_dir: str, main_window):
        super().__init__()
        self.project_dir = project_dir
        self.main_window = main_window
        self.data_reader = DataReader()

        self.setWindowTitle('Станок — %s' % os.path.basename(project_dir))
        self._build_ui()
        self._scan_project()
        self.showMaximized()  # Open in full screen

    def _center(self):
        frame = self.frameGeometry()
        screen = QApplication.instance().primaryScreen().availableGeometry().center()
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
        title = QLabel('Проект: %s' % os.path.basename(self.project_dir))
        title.setFont(QFont('Segoe UI', 14, QFont.Bold))
        header.addWidget(title)
        header.addStretch()
        
        # Delete project button (delete project files and templates, keep data and output)
        btn_delete_project = QToolButton()
        btn_delete_project.setText('🗑')
        btn_delete_project.setFont(QFont('Segoe UI', 12))
        btn_delete_project.setToolTip('Удалить проект целиком (шаблоны и конфиг, данные и output сохраняются)')
        btn_delete_project.setFixedSize(36, 36)
        btn_delete_project.setStyleSheet("""
            QToolButton { background-color: transparent; border: none; border-radius: 4px; }
            QToolButton:hover { background-color: #ffe0e0; }
        """)
        btn_delete_project.clicked.connect(self._delete_project)
        header.addWidget(btn_delete_project)
        
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
        self.templates_tree.itemDoubleClicked.connect(self._on_tree_double_click)
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
        self.templates_tree.clear()
        templates_dir = os.path.join(self.project_dir, 'Шаблоны')
        if os.path.exists(templates_dir):
            self._scan_dir(templates_dir, self.templates_tree, templates_dir)

        self.data_list.clear()
        data_dir = os.path.join(self.project_dir, 'Данные')
        if os.path.exists(data_dir):
            for f in sorted(os.listdir(data_dir)):
                if f.endswith(('.xlsx', '.xls')):
                    self.data_list.addItem('📊 %s' % f)

    def _scan_dir(self, base_dir, parent, root_dir):
        items = sorted(os.listdir(base_dir))
        for name in items:
            full = os.path.join(base_dir, name)
            rel = os.path.relpath(full, root_dir).replace('\\', '/')
            if os.path.isdir(full):
                item = QTreeWidgetItem(parent if isinstance(parent, QTreeWidget) else [parent])
                item.setText(0, '📁 %s' % name)
                item.setText(1, rel)
                self._scan_dir(full, item, root_dir)
            elif name.endswith('.docx'):
                item = QTreeWidgetItem(parent if isinstance(parent, QTreeWidget) else [parent])
                item.setText(0, '\U0001f4c4 %s' % name)
                item.setText(1, rel)

                # Create widget with both Fill and Delete buttons
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(2, 2, 2, 2)
                btn_layout.setSpacing(4)

                btn_fill = QPushButton(STRINGS.get('project_fill_template', 'Заполнить'))
                btn_fill.setFont(QFont('Segoe UI', 8))
                btn_fill.clicked.connect(lambda checked, p=rel: self._open_fill_form(p))
                btn_layout.addWidget(btn_fill)

                btn_delete = QToolButton()
                btn_delete.setText('\U0001f5d1')
                btn_delete.setFont(QFont('Segoe UI', 10))
                btn_delete.setToolTip(STRINGS.get('project_delete_template', 'Удалить шаблон'))
                btn_delete.setFixedSize(28, 28)
                btn_delete.setStyleSheet("""
                    QToolButton { background-color: transparent; border: none; border-radius: 4px; }
                    QToolButton:hover { background-color: #ffe0e0; }
                """)
                btn_delete.clicked.connect(lambda checked, p=rel: self._delete_template(p))
                btn_layout.addWidget(btn_delete)

                self.templates_tree.setItemWidget(item, 1, btn_widget)

    def _on_tree_double_click(self, item):
        if item and item.childCount() == 0 and item.text(1):
            self._open_fill_form(item.text(1))

    def _open_fill_form(self, rel_path=None):
        if rel_path is None or isinstance(rel_path, bool):
            return

        full_path = os.path.join(self.project_dir, 'Шаблоны', rel_path)
        if not os.path.exists(full_path):
            QMessageBox.warning(self, 'Ошибка', 'Шаблон не найден: %s' % full_path)
            return

        dlg = FillForm(self.project_dir, rel_path, self)
        dlg.exec_()
        self._scan_project()

    def _add_template(self):
        templates_dir = os.path.join(self.project_dir, 'Шаблоны')
        file, _ = QFileDialog.getOpenFileName(
            self, 'Выберите шаблон .docx',
            templates_dir, 'Word документы (*.docx)')
        if file:
            dest = os.path.join(self.project_dir, 'Шаблоны', os.path.basename(file))
            if not os.path.exists(dest):
                shutil.copy2(file, dest)
            self._scan_project()

    def _add_data(self):
        data_dir = os.path.join(self.project_dir, 'Данные')
        file, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл данных',
            data_dir, 'Excel файлы (*.xlsx *.xls)')
        if file:
            dest = os.path.join(self.project_dir, 'Данные', os.path.basename(file))
            if not os.path.exists(dest):
                shutil.copy2(file, dest)
            self._scan_project()

    def _delete_template(self, rel_path):
        """Delete a single template file with confirmation."""
        full_path = os.path.join(self.project_dir, 'Шаблоны', rel_path)
        if not os.path.exists(full_path):
            QMessageBox.warning(self, STRINGS['msg_warning'], 
                                STRINGS['msg_template_not_found'])
            return

        # Show confirmation dialog
        reply = QMessageBox.question(
            self, STRINGS.get('project_delete_template', 'Удалить шаблон'),
            STRINGS['project_delete_template_confirm'].format(name=rel_path),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            os.remove(full_path)
            logger.info(f"Deleted template: {rel_path}")
        except Exception as e:
            logger.error(f"Failed to delete template {rel_path}: {e}")
            QMessageBox.critical(self, STRINGS['msg_error'], 
                                 'Не удалось удалить шаблон: %s' % str(e))
            return

        # Refresh the project tree
        self._scan_project()
        QMessageBox.information(self, STRINGS['msg_info'], 
                                'Шаблон "%s" удалён.' % rel_path)

    def _delete_project(self):
        """Delete project files and templates, but keep data and output folders."""
        reply = QMessageBox.question(
            self, 'Удалить проект',
            'Удалить файлы проекта и шаблоны?\n'
            'Папки "Данные" и "output" НЕ будут удалены.\n\n'
            'Папка проекта: %s' % self.project_dir,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Remove from recent in main window
        self.main_window.remove_recent_project(self.project_dir)

        # Delete Шаблоны folder and проект.docxforge
        templates_dir = os.path.join(self.project_dir, 'Шаблоны')
        project_file = os.path.join(self.project_dir, 'проект.docxforge')
        project_bak = os.path.join(self.project_dir, 'проект.docxforge.bak')
        project_tmp = os.path.join(self.project_dir, 'проект.docxforge.tmp')

        for path in [templates_dir, project_file, project_bak, project_tmp]:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

        QMessageBox.information(self, 'Готово', 'Проект удалён. Данные и сгенерированные файлы сохранены.')
        self.main_window.show()
        self.close()

    def _go_back(self):
        self.main_window.show()
        self.main_window._add_recent(self.project_dir)
        self.main_window._refresh_recent_list()
        self.close()

    def closeEvent(self, event):
        self.main_window._add_recent(self.project_dir)
        self.main_window._refresh_recent_list()
        super().closeEvent(event)
