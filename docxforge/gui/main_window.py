# -*- coding: utf-8 -*-
"""DocxForge main window: create/open project, recent projects with quick generate."""

import os
import sys
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QPushButton, QLabel, QListWidget,
                              QListWidgetItem, QFileDialog, QMessageBox,
                              QFrame, QSizePolicy, QSpinBox, QProgressDialog,
                              QToolButton)
from PyQt5.QtCore import Qt, QSettings, QCoreApplication
from PyQt5.QtGui import QFont, QIcon

from docxforge.gui.project_window import ProjectWindow
from docxforge.engine.schema import create_project
from docxforge.generate import generate_project, GenerationError

def get_settings_path():
    """Get settings file path next to executable."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'docxforge_settings.json')

SETTINGS_FILE = get_settings_path()


class RecentProjectWidget(QWidget):
    """Widget for a single recent project with generate button, doc count, and delete button."""

    def __init__(self, project_path: str, main_window: 'MainWindow', last_doc_count: int = 1):
        super().__init__()
        self.project_path = project_path
        self.main_window = main_window
        self.last_doc_count = last_doc_count
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Project name
        name_label = QLabel(os.path.basename(self.project_path))
        name_label.setFont(QFont('Segoe UI', 10, QFont.Bold))
        name_label.setMinimumWidth(180)
        layout.addWidget(name_label)

        # Path (truncated)
        path_label = QLabel(self.project_path)
        path_label.setFont(QFont('Segoe UI', 9))
        path_label.setStyleSheet('color: #888;')
        path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(path_label)

        # Spin box for number of documents
        self.spin_docs = QSpinBox()
        self.spin_docs.setMinimum(1)
        self.spin_docs.setMaximum(9999)
        self.spin_docs.setValue(self.last_doc_count)
        self.spin_docs.setFixedWidth(80)
        self.spin_docs.setToolTip('Количество документов для генерации')
        layout.addWidget(self.spin_docs)

        # Generate button
        btn_generate = QPushButton('⚡ Сгенерировать')
        btn_generate.setFont(QFont('Segoe UI', 9))
        btn_generate.setMinimumHeight(30)
        btn_generate.setStyleSheet("""
            QPushButton { background-color: #107c10; color: white; border: none;
                          border-radius: 4px; padding: 4px 12px; }
            QPushButton:hover { background-color: #0e6e0e; }
            QPushButton:pressed { background-color: #0b5a0b; }
        """)
        btn_generate.clicked.connect(self._on_generate)
        layout.addWidget(btn_generate)

        # Delete button (remove from recent only)
        btn_delete = QToolButton()
        btn_delete.setText('✕')
        btn_delete.setFont(QFont('Segoe UI', 10))
        btn_delete.setToolTip('Удалить из недавних')
        btn_delete.setFixedSize(28, 28)
        btn_delete.setStyleSheet("""
            QToolButton { background-color: transparent; color: #888; border: none;
                          border-radius: 4px; }
            QToolButton:hover { background-color: #ffe0e0; color: #cc0000; }
        """)
        btn_delete.clicked.connect(self._on_delete)
        layout.addWidget(btn_delete)

    def _on_generate(self):
        value = self.spin_docs.value()
        self.main_window.generate_for_project(self.project_path, value)

    def _on_delete(self):
        self.main_window.remove_recent_project(self.project_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DocxForge')
        self.setMinimumSize(550, 500)
        self.resize(700, 600)
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

        # Generate All button
        btn_generate_all = QPushButton('⚡  Сгенерировать все недавние проекты')
        btn_generate_all.setMinimumHeight(40)
        btn_generate_all.setFont(QFont('Segoe UI', 10))
        btn_generate_all.setStyleSheet("""
            QPushButton { background-color: #107c10; color: white; border: none;
                          border-radius: 6px; padding: 8px 16px; }
            QPushButton:hover { background-color: #0e6e0e; }
            QPushButton:pressed { background-color: #0b5a0b; }
        """)
        btn_generate_all.clicked.connect(self._generate_all_recent)
        layout.addWidget(btn_generate_all)

        layout.addSpacing(5)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color: #ddd;')
        layout.addWidget(sep)

        # Recent projects header with Generate All
        recent_header = QHBoxLayout()
        recent_label = QLabel('Недавние проекты')
        recent_label.setFont(QFont('Segoe UI', 10, QFont.Bold))
        recent_label.setStyleSheet('color: #888;')
        recent_header.addWidget(recent_label)
        recent_header.addStretch()
        layout.addLayout(recent_header)

        self.recent_list = QListWidget()
        self.recent_list.setFont(QFont('Segoe UI', 10))
        self.recent_list.itemDoubleClicked.connect(self._open_recent)
        self._refresh_recent_list()
        layout.addWidget(self.recent_list, stretch=1)

    def _refresh_recent_list(self):
        self.recent_list.clear()
        for path in self.recent_projects:
            if os.path.exists(path):
                last_count = self._get_last_doc_count(path)
                item = QListWidgetItem()
                item.setData(Qt.UserRole, path)
                widget = RecentProjectWidget(path, self, last_count)
                item.setSizeHint(widget.sizeHint())
                self.recent_list.addItem(item)
                self.recent_list.setItemWidget(item, widget)

    def _generate_all_recent(self):
        """Generate documents for all recent projects using their saved doc counts."""
        if not self.recent_projects:
            QMessageBox.information(self, 'Нет проектов', 'Список недавних проектов пуст.')
            return

        valid_projects = [p for p in self.recent_projects if os.path.exists(p)]
        if not valid_projects:
            QMessageBox.warning(self, 'Ошибка', 'Ни один из недавних проектов не найден на диске.')
            return

        total = len(valid_projects)
        progress = QProgressDialog('Генерация всех проектов...', 'Отмена', 0, total, self)
        progress.setWindowTitle('Пакетная генерация')
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.setAutoReset(True)

        results = []
        for i, project_path in enumerate(valid_projects):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            progress.setLabelText(f'Генерация: {os.path.basename(project_path)}')
            QApplication.processEvents()

            try:
                num_docs = self._get_last_doc_count(project_path)
                outputs = generate_project(project_path, num_docs=num_docs)
                results.append((project_path, len(outputs), None))
            except GenerationError as e:
                results.append((project_path, 0, str(e)))
            except Exception as e:
                results.append((project_path, 0, str(e)))

        progress.setValue(total)
        progress.close()

        # Show summary
        success_count = sum(1 for _, cnt, err in results if err is None and cnt > 0)
        msg_lines = [f'Обработано проектов: {len(results)}', f'Успешно: {success_count}', '']
        for project_path, count, error in results:
            name = os.path.basename(project_path)
            if error:
                msg_lines.append(f'❌ {name}: {error}')
            else:
                msg_lines.append(f'✅ {name}: {count} док.')
        
        QMessageBox.information(self, 'Генерация завершена', '\n'.join(msg_lines))

    def remove_recent_project(self, path: str):
        """Remove a project from recent list only."""
        path = os.path.abspath(path)
        if path in self.recent_projects:
            self.recent_projects.remove(path)
            self._save_recent()
            self._refresh_recent_list()

    def _add_recent(self, path):
        path = os.path.abspath(path)
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:10]
        self._save_recent()
        self._refresh_recent_list()

    def _get_last_doc_count(self, path: str) -> int:
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('doc_counts', {}).get(path, 1)
        except Exception:
            pass
        return 1

    def _set_last_doc_count(self, path: str, count: int):
        try:
            data = {'recent_projects': self.recent_projects, 'doc_counts': {}}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data.setdefault('doc_counts', {})[path] = count
            data['recent_projects'] = self.recent_projects
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

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
                    if isinstance(data, list):
                        # Old format compatibility
                        return data
                    return data.get('recent_projects', [])
        except Exception:
            pass
        return []

    def _save_recent(self):
        try:
            data = {'recent_projects': self.recent_projects, 'doc_counts': {}}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        data['doc_counts'] = existing.get('doc_counts', {})
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def generate_for_project(self, project_path: str, num_docs: int):
        """Generate documents for a project using the first template found."""
        progress = QProgressDialog('Генерация...', None, 0, num_docs, self)
        progress.setWindowTitle('Создание документов')
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.setAutoReset(True)

        try:
            outputs = generate_project(project_path, num_docs=num_docs)

            progress.close()

            msg = f'Создано документов: {len(outputs)}\n'
            msg += '\n'.join(os.path.basename(o) for o in outputs[:5])
            if len(outputs) > 5:
                msg += f'\n... и ещё {len(outputs) - 5} файлов'
            QMessageBox.information(self, 'Готово', msg)
            self._set_last_doc_count(project_path, num_docs)
            self._add_recent(project_path)  # Move to top

        except GenerationError as e:
            progress.close()
            QMessageBox.warning(self, 'Ошибка', str(e))
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, 'Ошибка генерации', str(e))


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
        QListWidget::item { padding: 4px; }
        QListWidget::item:hover { background: #e8f0fe; }
        QSpinBox { padding: 4px; border: 1px solid #ccc; border-radius: 4px; }
    """)
    window = MainWindow()
    window.showMaximized()  # Open in full screen
    sys.exit(app.exec_())


if __name__ == '__main__':
    run()
