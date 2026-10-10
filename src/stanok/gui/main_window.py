# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 1: recent projects, per-project/all generation, settings stub."""

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
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from ..services.generate import GenerateCommand, GenerateReport
from ..services.storage import ProjectStore
from .project_dialog import ProjectDialog
from .strings import STRINGS
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

        group = QGroupBox(STRINGS.MAIN_PROJECT_GROUP, root)
        group_layout = QVBoxLayout(group)
        self.recent_list = QListWidget(group)
        self.recent_list.itemClicked.connect(self._on_row_clicked)
        group_layout.addWidget(self.recent_list)

        buttons = QHBoxLayout()
        self.generate_all_btn = QPushButton(STRINGS.MAIN_GENERATE_ALL, group)
        self.generate_all_btn.setStyleSheet("background-color: #2e7d32; color: white;")
        self.generate_all_btn.clicked.connect(self._on_generate_all)
        buttons.addWidget(self.generate_all_btn)
        self.browse_btn = QPushButton(STRINGS.MAIN_BROWSE, group)
        self.browse_btn.clicked.connect(self._on_browse)
        buttons.addWidget(self.browse_btn)
        self.create_btn = QPushButton(STRINGS.MAIN_CREATE, group)
        self.create_btn.clicked.connect(self._on_create)
        buttons.addWidget(self.create_btn)
        self.settings_btn = QPushButton(STRINGS.MAIN_SETTINGS, group)
        self.settings_btn.clicked.connect(self._on_settings)
        buttons.addWidget(self.settings_btn)
        group_layout.addLayout(buttons)
        layout.addWidget(group)

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
            label = f"{item.folder} [{item.config}]"
            entry = QListWidgetItem(self.recent_list)
            entry.setData(Qt.UserRole, item.folder)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            name = QLabel(label, row)
            row_layout.addWidget(name, 1)
            btn = QPushButton(STRINGS.MAIN_GENERATE, row)
            btn.clicked.connect(
                lambda _checked=False, ref=item.folder: self._on_generate_one(ref)
            )
            row_layout.addWidget(btn)
            entry.setSizeHint(row.sizeHint())
            self.recent_list.addItem(entry)
            self.recent_list.setItemWidget(entry, row)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, STRINGS.MAIN_BROWSE)
        if not folder:
            return
        try:
            self._store.resolve_project(folder)
        except Exception as e:
            logger.warning(f"open project {folder}: {e}", exc_info=True)
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
            return
        resolved = str(Path(folder).resolve())
        self._store.add_recent(resolved, Path(folder).resolve().name)
        self.refresh_recent()

    def _on_row_clicked(self, item: QListWidgetItem) -> None:
        self._open_project_dialog(item.data(Qt.UserRole))

    def _open_project_dialog(self, ref: str) -> None:
        """Open window 2 (ProjectDialog, 009)."""
        try:
            dialog = ProjectDialog(ref, self._store, self)
        except Exception as e:
            logger.warning(f"open project dialog {ref}: {e}", exc_info=True)
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
            return
        dialog.exec_()
        self.refresh_recent()

    def _on_settings(self) -> None:
        QMessageBox.information(
            self, STRINGS.MAIN_SETTINGS, STRINGS.MAIN_SETTINGS_STUB
        )

    def _on_create(self) -> None:
        """Open window 4 (CreateDialog, 014); refresh recent on success."""
        # Local import: keeps module import light and patchable in tests.
        from .create_dialog import CreateDialog

        recent = self._store.get_recent()
        hint = recent[-1].folder if recent else str(Path.home())
        dialog = CreateDialog(self._store, hint, self)
        if dialog.exec_():
            self.refresh_recent()

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
                text = STRINGS.APP_DONE.format(
                    created=result.created,
                    skipped=result.skipped,
                    errors=len(result.errors),
                    elapsed=f"{result.elapsed:.1f}",
                )
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
                    lines.append(
                        f"{ref}: "
                        + STRINGS.APP_DONE.format(
                            created=result.created,
                            skipped=result.skipped,
                            errors=len(result.errors),
                            elapsed=f"{result.elapsed:.1f}",
                        )
                    )
            QMessageBox.information(
                self, STRINGS.MAIN_SUMMARY_TITLE, "\n".join(lines)
            )

    def _set_busy(self, busy: bool) -> None:
        self.generate_all_btn.setEnabled(not busy)
        self.browse_btn.setEnabled(not busy)
        self.create_btn.setEnabled(not busy)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, message)
