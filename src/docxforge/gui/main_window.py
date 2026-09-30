# -*- coding: utf-8 -*-
"""DocxForge main window: create/open project, recent projects with quick generate."""

import os
import sys
import json
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QPushButton, QLabel, QListWidget,
                              QListWidgetItem, QFileDialog, QMessageBox,
                              QFrame, QSizePolicy, QSpinBox, QProgressDialog,
                              QToolButton)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

from docxforge.gui.project_window import ProjectWindow
from docxforge.gui.strings import STRINGS
from docxforge.engine.schema import create_project, Project
from docxforge.generate import (
    generate_project,
    GenerationError,
    is_project_folder,
    migrate_project_configs_to_home,
    resolve_project_file,
)
from docxforge.gui.worker import GenerateWorker, project_job

logger = logging.getLogger(__name__)

def _legacy_settings_path():
    """Pre-M11 location: next to the module (inside the package tree)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'docxforge_settings.json')


def _migrate_settings(legacy_path: str, new_path: str) -> bool:
    """Move settings from the legacy package-tree location (M11).

    Returns True when a migration happened (or nothing needed doing).
    Never raises: settings are a convenience cache, the app must start
    even if the home directory is not writable (then legacy is reused).
    """
    if os.path.exists(new_path):
        return True
    if not os.path.exists(legacy_path):
        return True
    try:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        with open(legacy_path, 'rb') as f:
            data = f.read()
        json.loads(data.decode('utf-8'))  # validate before moving
        with open(new_path, 'wb') as f:
            f.write(data)
        os.remove(legacy_path)
        logger.info('Migrated settings %s -> %s', legacy_path, new_path)
        return True
    except (OSError, ValueError) as e:
        logger.debug(f'Could not migrate settings: {e}', exc_info=True)
        return False
    except Exception as e:
        logger.debug(f'Could not migrate settings: {e}', exc_info=True)
        return False


def get_settings_path():
    """Get user-scope settings file path (M11: home dir, not package tree)."""
    new_path = os.path.join(
        os.path.expanduser('~'), '.docxforge', 'docxforge_settings.json')
    try:
        if _migrate_settings(_legacy_settings_path(), new_path):
            return new_path
    except (OSError, ValueError) as e:
        logger.debug(f'Settings path resolution failed: {e}', exc_info=True)
    except Exception as e:
        logger.debug(f'Settings path resolution failed: {e}', exc_info=True)
    return _legacy_settings_path()

SETTINGS_FILE = get_settings_path()


class RecentProjectWidget(QWidget):
    """Widget for a single recent project with generate button, doc count, template name, and delete button."""

    def __init__(self, project_path: str, main_window: 'MainWindow', last_doc_count: int = 1, last_template_name: str = ''):
        super().__init__()
        self.project_path = project_path
        self.main_window = main_window
        self.last_doc_count = last_doc_count
        self.last_template_name = last_template_name
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

        # Last template name (if any)
        if self.last_template_name:
            template_label = QLabel('📄 ' + self.last_template_name)
            template_label.setFont(QFont('Segoe UI', 9))
            template_label.setStyleSheet('color: #0078d4;')
            template_label.setMinimumWidth(150)
            template_label.setMaximumWidth(250)
            template_label.setToolTip('Последний использованный шаблон: ' + self.last_template_name)
            layout.addWidget(template_label)

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
        self.setWindowTitle('Станок')
        self.setMinimumSize(550, 500)
        self.resize(700, 600)
        self.recent_projects = self._load_recent()
        # Migrate per-project configs of recent folders into ~/.docxforge
        # (generated projects carry <name>.docxforge next to Данные/).
        for recent in list(self.recent_projects):
            if os.path.isdir(recent):
                try:
                    migrate_project_configs_to_home(recent)
                except Exception as e:
                    logger.debug(f'Config migration skipped for {recent!r}: {e}', exc_info=True)
        self._batch_worker = None
        self._batch_progress = None
        self._build_ui()
        self._center()

    def _center(self):
        frame = self.frameGeometry()
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel('Станок')
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
        btn_add_many = QPushButton(STRINGS['main_add_many_btn'])
        btn_add_many.setMinimumHeight(40)
        btn_add_many.setFont(QFont('Segoe UI', 10))
        btn_add_many.clicked.connect(self._add_many_projects)
        layout.addWidget(btn_add_many)

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
                last_template = self._get_last_template(path)
                item = QListWidgetItem()
                item.setData(Qt.UserRole, path)
                widget = RecentProjectWidget(path, self, last_count, last_template)
                item.setSizeHint(widget.sizeHint())
                self.recent_list.addItem(item)
                self.recent_list.setItemWidget(item, widget)

    def _generate_all_recent(self):
        """Generate documents for all recent projects (M10: worker thread).

        The per-project engine calls run in a GenerateWorker; the progress
        dialog stays responsive and Cancel honestly stops the queue between
        projects (never mid-call — the engine has no checkpoints).
        """
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
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        jobs = [(os.path.basename(p),
                 project_job(p, self._get_last_doc_count(p)))
                for p in valid_projects]
        self._batch_worker = GenerateWorker(jobs, self)
        self._batch_progress = progress
        self._batch_worker.progressed.connect(self._on_batch_progress)
        progress.canceled.connect(self._batch_worker.request_cancel)
        self._batch_worker.done.connect(self._on_batch_done)
        self._batch_worker.start()

    def _on_batch_progress(self, index: int, label: str):
        progress = getattr(self, '_batch_progress', None)
        if progress is not None:
            progress.setValue(index)
            progress.setLabelText(f'Генерация: {label}')

    def _on_batch_done(self, results):
        progress = getattr(self, '_batch_progress', None)
        if progress is not None:
            progress.setValue(progress.maximum())
            progress.close()
            self._batch_progress = None
        self._batch_worker = None

        # Show summary
        success_count = sum(1 for _, out, err in results
                            if err is None and out)
        msg_lines = [f'Обработано проектов: {len(results)}', f'Успешно: {success_count}', '']
        for label, outputs, error in results:
            if error:
                msg_lines.append(f'❌ {label}: {error}')
            else:
                msg_lines.append(f'✅ {label}: {len(outputs)} док.')

        QMessageBox.information(self, 'Генерация завершена', '\n'.join(msg_lines))

    def remove_recent_project(self, path: str):
        """Remove a project from recent list only."""
        path = os.path.abspath(path)
        if path in self.recent_projects:
            self.recent_projects.remove(path)
            self._save_recent()
            self._refresh_recent_list()

    def _add_recent(self, path, template_name: str = ''):
        path = os.path.abspath(path)
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:10]
        self._save_recent()
        if template_name:
            self._set_last_template(path, template_name)
        self._refresh_recent_list()

    def _get_last_doc_count(self, path: str) -> int:
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('doc_counts', {}).get(path, 1)
        except (OSError, ValueError) as e:
            logger.debug(f'Could not read doc count from settings: {e}', exc_info=True)
        except Exception as e:
            logger.debug(f'Could not read doc count from settings: {e}', exc_info=True)
        return 1

    def _get_last_template(self, path: str) -> str:
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_templates', {}).get(path, '')
        except (OSError, ValueError) as e:
            logger.debug(f'Could not read last template from settings: {e}', exc_info=True)
        except Exception as e:
            logger.debug(f'Could not read last template from settings: {e}', exc_info=True)
        return ''

    def _set_last_doc_count(self, path: str, count: int):
        try:
            data = {'recent_projects': self.recent_projects, 'doc_counts': {}, 'last_templates': {}}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data.setdefault('doc_counts', {})[path] = count
            data.setdefault('last_templates', {})
            data['recent_projects'] = self.recent_projects
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as e:
            logger.debug(f'Could not write doc count to settings: {e}', exc_info=True)
        except Exception as e:
            logger.debug(f'Could not write doc count to settings: {e}', exc_info=True)

    def _set_last_template(self, path: str, template_name: str):
        try:
            data = {'recent_projects': self.recent_projects, 'doc_counts': {}, 'last_templates': {}}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data.setdefault('doc_counts', {})
            data.setdefault('last_templates', {})[path] = template_name
            data['recent_projects'] = self.recent_projects
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as e:
            logger.debug(f'Could not write last template to settings: {e}', exc_info=True)
        except Exception as e:
            logger.debug(f'Could not write last template to settings: {e}', exc_info=True)

    def _create_project(self):
        path = QFileDialog.getExistingDirectory(self, 'Выберите папку для проекта',
                                                 os.path.expanduser('~'))
        if not path:
            return
        project_file = create_project(path)
        self._add_recent(path)
        self._open_project_at(path)

    def _add_many_projects(self):
        """Add several project folders to recent via multi-select dialog."""
        from docxforge.gui.dialogs import get_existing_directory_list
        dirs = get_existing_directory_list(
            self, STRINGS['dlg_select_dirs'], os.path.expanduser('~'))
        if not dirs:
            return
        added, skipped = 0, []
        for path in dirs:
            if is_project_folder(path):
                self._add_recent(path)
                added += 1
            else:
                skipped.append(os.path.basename(path) or path)
        if skipped:
            QMessageBox.information(
                self, STRINGS['msg_info'],
                STRINGS['main_added_many_skipped'].format(
                    count=added, skipped=', '.join(skipped)))
        else:
            QMessageBox.information(
                self, STRINGS['msg_info'],
                STRINGS['main_added_many'].format(count=added))

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
        try:
            migrate_project_configs_to_home(path)
        except Exception as e:
            logger.debug(f'Config migration skipped for {path!r}: {e}', exc_info=True)
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
        except (OSError, ValueError) as e:
            logger.debug(f'Could not read recent projects from settings: {e}', exc_info=True)
        except Exception as e:
            logger.debug(f'Could not read recent projects from settings: {e}', exc_info=True)
        return []

    def _save_recent(self):
        try:
            data = {'recent_projects': self.recent_projects, 'doc_counts': {}, 'last_templates': {}}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        data['doc_counts'] = existing.get('doc_counts', {})
                        data['last_templates'] = existing.get('last_templates', {})
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as e:
            logger.debug(f'Could not write recent projects to settings: {e}', exc_info=True)
        except Exception as e:
            logger.debug(f'Could not write recent projects to settings: {e}', exc_info=True)

    def generate_for_project(self, project_path: str, num_docs: int):
        """Generate documents for a project using the first template found."""
        # Find the first configured template
        project_file = resolve_project_file(project_path)
        template_name = ''
        try:
            project = Project.from_file(project_file)
            if project.templates:
                template_name = next(iter(project.templates.keys()))
        except (OSError, ValueError) as e:
            logger.debug(f'Could not read project file {project_file}: {e}', exc_info=True)
        except Exception as e:
            logger.debug(f'Could not read project file {project_file}: {e}', exc_info=True)
        
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
            self._add_recent(project_path, template_name)  # Move to top with template name

        except GenerationError as e:
            logger.exception(f'Generation failed for {project_path}: {e}')
            progress.close()
            QMessageBox.warning(self, 'Ошибка', str(e))
        except Exception as e:
            logger.exception(f'Generation failed for {project_path}: {e}')
            progress.close()
            QMessageBox.critical(self, 'Ошибка генерации', str(e))


def app_icon_path():
    """Absolute path to the application icon (docxforge/gui/icon.png).

    In a PyInstaller build the icon is bundled via spec ``datas`` and
    unpacked under ``sys._MEIPASS``.
    """
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        return os.path.join(base, 'docxforge', 'gui', 'icon.png')
    gui_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(gui_dir, 'icon.png')


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    icon_path = app_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        logger.warning('Application icon not found: %s', icon_path)
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
