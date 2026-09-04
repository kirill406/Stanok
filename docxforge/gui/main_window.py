# -*- coding: utf-8 -*-
"""DocxForge main window: create/open project, recent projects."""

import os
import sys
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QPushButton, QLabel, QListWidget,
                              QListWidgetItem, QFileDialog, QMessageBox,
                              QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont, QIcon

from docxforge.gui.project_window import ProjectWindow
from docxforge.engine.schema import create_project

SETTINGS_FILE = 'docxforge_settings.json'


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DocxForge')
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        self.settings = QSettings('DocxForge', 'MainWindow')
        self.recent_projects = self._load_recent()
        self._build_ui()
        self._center()

    def _center(self):
        frame = self.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry().center()
        frame.moveCenter(screen)
        self.move(frame.topLeft())

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel('DocxForge')
        title.setFont(QFont('Segoe UI', 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel('Генератор документов из шаблонов')
        subtitle.setFont(QFont('Segoe UI', 11))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('color: #666;')
        layout.addWidget(subtitle)

        layout.addSpacing(10)

        # Buttons
        btn_new = QPushButton('📁  Создать новый проект')
        btn_new.setMinimumHeight(45)
        btn_new.setFont(QFont('Segoe UI', 11))
        btn_new.clicked.connect(self._create_project)
        layout.addWidget(btn_new)

        btn_open = QPushButton('📂  Открыть проект')
        btn_open.setMinimumHeight(45)
        btn_open.setFont(QFont('Segoe UI', 11))
        btn_open.clicked.connect(self._open_project)
        layout.addWidget(btn_open)

        layout.addSpacing(5)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color: #ddd;')
        layout.addWidget(sep)

        # Recent projects
        recent_label = QLabel('Недавние проекты')
        recent_label.setFont(QFont('Segoe UI', 10, QFont.Bold))
        recent_label.setStyleSheet('color: #888;')
        layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        self.recent_list.setFont(QFont('Segoe UI', 10))
        self.recent_list.itemDoubleClicked.connect(self._open_recent)
        self._refresh_recent_list()
        layout.addWidget(self.recent_list)

    def _refresh_recent_list(self):
        self.recent_list.clear()
        for path in self.recent_projects:
            if os.path.exists(path):
                item = QListWidgetItem(f'{os.path.basename(path)}  —  {path}')
                item.setData(Qt.UserRole, path)
                self.recent_list.addItem(item)

    def _add_recent(self, path):
        path = os.path.abspath(path)
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:10]
        self._save_recent()
        self._refresh_recent_list()

    def _create_project(self):
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку для проекта',
                                                 os.path.expanduser('~'))
        if not path:
            return
        project_file = create_project(path)
        self._add_recent(path)
        self._open_project_at(path)

    def _open_project(self):
        path = QFileDialog.getExistingDirectory(self, 'Откройте папку проекта',
                                                 os.path.expanduser('~'))
        if not path:
            return
        self._open_project_at(path)

    def _open_recent(self, item):
        path = item.data(Qt.UserRole)
        if path and os.path.exists(path):
            self._open_project_at(path)
        else:
            QMessageBox.warning(self, 'Ошибка',
                                 'Папка проекта не найдена. Возможно, она была перемещена.')

    def _open_project_at(self, path):
        self.project_window = ProjectWindow(path, self)
        self.project_window.show()
        self.hide()

    def _load_recent(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('recent_projects', [])
        except Exception:
            pass
        return []

    def _save_recent(self):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'recent_projects': self.recent_projects}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass


def run():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet("""
        QMainWindow { background-color: #f5f5f5; }
        QPushButton { background-color: #0078d4; color: white; border: none;
                      border-radius: 6px; padding: 8px 16px; }
        QPushButton:hover { background-color: #106ebe; }
        QPushButton:pressed { background-color: #005a9e; }
        QListWidget { border: 1px solid #ddd; border-radius: 4px;
                      background: white; }
        QListWidget::item { padding: 8px; }
        QListWidget::item:hover { background: #e8f0fe; }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    run()
