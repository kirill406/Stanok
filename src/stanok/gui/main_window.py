# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 1: recent projects, per-project/all generation, settings, create."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from ..services.generate import GenerateCommand, GenerateReport
from ..engine.schema import SchemaError
from ..services.storage import ProjectStore, StorageError
from .dialogs import ask_yes_no
from .project_dialog import ProjectDialog
from .report_text import done_text
from .strings import STRINGS
from .theme import set_button_role
from .widgets import ElidedLabel
from .worker import GenerateWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Thin view over services: widgets in, signals out, no business logic."""

    def __init__(self, store: ProjectStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._worker: GenerateWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._queue: list[str] = []
        self._queue_total = 0
        self._queue_results: list[tuple[str, GenerateReport | str]] = []
        self._cancel_requested = False
        self._last_started = ""
        self._build_ui()
        self.refresh_recent()

    # -- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.MAIN_TITLE)
        self.resize(900, 650)
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel(STRINGS.MAIN_TITLE, root)
        title.setObjectName("appTitle")
        layout.addWidget(title)
        subtitle = QLabel(STRINGS.MAIN_SUBTITLE, root)
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(subtitle)

        group = QGroupBox(STRINGS.MAIN_PROJECT_GROUP, root)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(14, 18, 14, 14)
        group_layout.setSpacing(10)
        self.recent_list = QListWidget(group)
        self.recent_list.setSpacing(4)
        self.recent_list.itemClicked.connect(self._on_row_clicked)
        group_layout.addWidget(self.recent_list)
        self.empty_label = QLabel(STRINGS.MAIN_EMPTY, group)
        self.empty_label.setObjectName("muted")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignCenter)
        group_layout.addWidget(self.empty_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.generate_all_btn = QPushButton(STRINGS.MAIN_GENERATE_ALL, group)
        set_button_role(self.generate_all_btn, "primary")
        self.generate_all_btn.clicked.connect(self._on_generate_all)
        buttons.addWidget(self.generate_all_btn)
        self.browse_btn = QPushButton(STRINGS.MAIN_OPEN, group)
        self.browse_btn.clicked.connect(self._on_browse)
        buttons.addWidget(self.browse_btn)
        self.create_btn = QPushButton(STRINGS.MAIN_CREATE, group)
        self.create_btn.clicked.connect(self._on_create)
        buttons.addWidget(self.create_btn)
        self.settings_btn = QPushButton(STRINGS.MAIN_SETTINGS, group)
        self.settings_btn.clicked.connect(self._on_settings)
        buttons.addWidget(self.settings_btn)
        group_layout.addLayout(buttons)
        layout.addWidget(group, 1)

        self.progress_bar = QProgressBar(root)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.setCentralWidget(root)
        self.statusBar().showMessage(STRINGS.MAIN_STATUS_READY)

    # -- project list -----------------------------------------------------
    def refresh_recent(self) -> None:
        """Reload recent-projects list, one row per project + button."""
        self.recent_list.clear()
        for item in self._store.get_recent():
            entry = QListWidgetItem(self.recent_list)
            entry.setData(Qt.UserRole, item.config)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(10)
            identity = QVBoxLayout()
            identity.setSpacing(1)
            name = ElidedLabel(item.config, row, Qt.ElideRight)
            name.setObjectName("rowTitle")
            path = ElidedLabel(item.folder, row, Qt.ElideMiddle)
            path.setObjectName("rowSubtitle")
            path.setToolTip(item.folder)
            identity.addWidget(name)
            identity.addWidget(path)
            row_layout.addLayout(identity, 1)
            self._add_template_controls(row, row_layout, item.config)
            btn = QPushButton(STRINGS.MAIN_GENERATE, row)
            btn.clicked.connect(
                lambda _checked=False, ref=item.config: self._on_generate_one(ref)
            )
            row_layout.addWidget(btn)
            rm_btn = QPushButton(STRINGS.MAIN_REMOVE, row)
            rm_btn.clicked.connect(
                lambda _checked=False, folder=item.folder, config=item.config: self._on_remove_recent(
                    folder, config
                )
            )
            row_layout.addWidget(rm_btn)
            entry.setSizeHint(row.sizeHint())
            self.recent_list.addItem(entry)
            self.recent_list.setItemWidget(entry, row)
        has_recent = self.recent_list.count() > 0
        self.recent_list.setVisible(has_recent)
        self.empty_label.setVisible(not has_recent)

    def _add_template_controls(self, row: QWidget, layout: QHBoxLayout, ref: str) -> None:
        """Show the default template name + editable limit before «Сгенерировать»."""
        try:
            pj, _ = self._store.resolve_project(ref)
            template = pj.default_template
            limit = pj.templates[template].limit
        except (StorageError, SchemaError, OSError, ValueError) as e:
            logger.warning(f"default template of {ref}: {e}", exc_info=True)
            layout.addWidget(QLabel(STRINGS.MAIN_TPL_UNAVAILABLE, row))
            return
        except Exception as e:
            logger.critical(
                f"unexpected default template of {ref}: {e}", exc_info=True
            )
            layout.addWidget(QLabel(STRINGS.MAIN_TPL_UNAVAILABLE, row))
            return
        layout.addWidget(QLabel(STRINGS.MAIN_TPL.format(name=template), row))
        spin = QSpinBox(row)
        spin.setRange(0, 1_000_000)
        spin.setValue(limit)
        spin.setToolTip(STRINGS.MAIN_TPL_LIMIT_TIP)
        spin.valueChanged.connect(
            lambda value, r=ref, t=template: self._on_row_limit_changed(r, t, value)
        )
        layout.addWidget(spin)

    def _on_row_limit_changed(self, ref: str, template: str, value: int) -> None:
        """Persist a row's default-template limit as soon as it changes."""
        try:
            self._store.set_template_limit(ref, template, value)
        except (StorageError, SchemaError, OSError, ValueError) as e:
            logger.warning(
                f"set template limit {ref}/{template}: {e}", exc_info=True
            )
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
        except Exception as e:
            logger.critical(
                f"unexpected set template limit {ref}/{template}: {e}",
                exc_info=True,
            )
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")

    def _on_browse(self) -> None:
        """Pick a project from the known list (open by config name)."""
        from .open_project_dialog import OpenProjectDialog

        dialog = OpenProjectDialog(self._store, self)
        accepted = dialog.exec_()
        # Import inside the dialog adds recent entries even when it is cancelled.
        self.refresh_recent()
        if not accepted:
            return
        config = dialog.selected_config
        if not config:
            return
        created = getattr(dialog, "created_config", "") == config
        self._store.touch_recent(config)
        self.refresh_recent()
        self._open_project_dialog(config, highlight_new=created)

    def _on_row_clicked(self, item: QListWidgetItem) -> None:
        self._open_project_dialog(item.data(Qt.UserRole))

    def _on_remove_recent(self, folder: str, config: str) -> None:
        """Drop one entry from recent list (project itself untouched)."""
        self._store.remove_recent(folder, config)
        self.refresh_recent()

    def _open_project_dialog(self, ref: str, *, highlight_new: bool = False) -> None:
        """Open window 2 (ProjectDialog, 009) by config name."""
        try:
            dialog = ProjectDialog(
                ref, self._store, self, highlight_new=highlight_new
            )
        except StorageError as e:
            logger.warning(f"open project dialog {ref}: {e}", exc_info=True)
            if "folder not found" in str(e):
                self._offer_relocate(ref)
            else:
                self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
            return
        except Exception as e:
            logger.critical(
                f"unexpected open project dialog {ref}: {e}", exc_info=True
            )
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
            return
        dialog.exec_()
        self.refresh_recent()

    def _offer_relocate(self, ref: str) -> None:
        """Missing project folder: let the user pick a new one (020 risk)."""
        if not ask_yes_no(
            self,
            STRINGS.MAIN_ERROR_TITLE,
            STRINGS.MAIN_FOLDER_MISSING.format(name=ref),
        ):
            return
        folder = QFileDialog.getExistingDirectory(self, STRINGS.MAIN_FIND_FOLDER)
        if not folder:
            return
        try:
            self._store.set_project_folder(ref, folder)
        except (StorageError, SchemaError, OSError, ValueError) as e:
            logger.warning(f"relocate project {ref}: {e}", exc_info=True)
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
            return
        except Exception as e:
            logger.critical(
                f"unexpected relocate project {ref}: {e}", exc_info=True
            )
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
            return
        self.refresh_recent()
        self._open_project_dialog(ref)

    def _on_settings(self) -> None:
        """Open settings dialog (018); keeps import lazy like create (tests)."""
        from .settings_dialog import SettingsDialog

        dialog = SettingsDialog(self._store, self)
        dialog.exec_()

    def _on_create(self) -> None:
        """Open window 4 (CreateDialog, 014); refresh recent on success."""
        # Local import: keeps module import light and patchable in tests.
        from .create_dialog import CreateDialog

        recent = self._store.get_recent()
        # get_recent() is newest-first: the hint comes from the latest project.
        hint = str(Path(recent[0].folder).parent) if recent else str(Path.home())
        dialog = CreateDialog(self._store, hint, self)
        if dialog.exec_():
            self.refresh_recent()
            name = getattr(dialog, "project_name", "")
            if name:
                self._open_project_dialog(name, highlight_new=True)

    # -- generation queue ---------------------------------------------------
    def _on_generate_one(self, ref: str) -> None:
        self._start_queue([ref])

    def _on_generate_all(self) -> None:
        refs = [
            self.recent_list.item(i).data(Qt.UserRole)
            for i in range(self.recent_list.count())
        ]
        if refs:
            self._start_queue(refs)

    def _start_queue(self, refs: list[str]) -> None:
        self._queue = list(refs)
        self._queue_total = len(refs)
        self._queue_results = []
        self._cancel_requested = False
        self._set_busy(True)
        self._progress_dialog = QProgressDialog(
            STRINGS.MAIN_PROGRESS_TITLE, STRINGS.MAIN_CANCEL, 0, 0, self
        )
        self._progress_dialog.canceled.connect(self._on_cancel)
        self._progress_dialog.show()
        self._run_next()

    def _run_next(self) -> None:
        if self._cancel_requested or not self._queue:
            self._finish_queue()
            return
        ref = self._queue.pop(0)
        self._last_started = ref
        done = self._queue_total - len(self._queue)
        self.statusBar().showMessage(f"{ref}: {done}/{self._queue_total}")
        cmd = GenerateCommand(project_ref=ref)
        self._worker = GenerateWorker(cmd, store=self._store, parent=self)
        self._worker.progressed.connect(self._on_progressed)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_cancel(self) -> None:
        self._cancel_requested = True
        if self._worker is not None:
            self._worker.request_cancel()

    def _on_progressed(self, created: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(created)
        self.statusBar().showMessage(
            STRINGS.MAIN_STATUS_RUNNING.format(created=created, total=total)
        )

    def _on_finished(self, report: GenerateReport) -> None:
        self._queue_results.append((self._last_started, report))
        self._run_next()

    def _on_failed(self, message: str) -> None:
        self._queue_results.append((self._last_started, message))
        self._run_next()

    def _finish_queue(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        self._set_busy(False)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage(STRINGS.MAIN_STATUS_READY)
        self.refresh_recent()
        if self._queue_total == 1 and len(self._queue_results) == 1:
            ref, result = self._queue_results[0]
            if isinstance(result, str):
                self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {result}")
            else:
                text = done_text(result)
                if result.errors:
                    details = "\n".join(f"{i}: {msg}" for i, msg in result.errors)
                    QMessageBox.information(
                        self, STRINGS.MAIN_DONE_TITLE, f"{text}\n\n{details}"
                    )
                else:
                    QMessageBox.information(self, STRINGS.MAIN_DONE_TITLE, text)
        elif self._queue_results:
            lines = []
            for ref, result in self._queue_results:
                if isinstance(result, str):
                    lines.append(f"{ref}: {STRINGS.MAIN_ERROR_TITLE}: {result}")
                else:
                    lines.append(f"{ref}: {done_text(result)}")
            QMessageBox.information(
                self, STRINGS.MAIN_SUMMARY_TITLE, "\n".join(lines)
            )

    def _set_busy(self, busy: bool) -> None:
        self.generate_all_btn.setEnabled(not busy)
        self.browse_btn.setEnabled(not busy)
        self.create_btn.setEnabled(not busy)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, message)
