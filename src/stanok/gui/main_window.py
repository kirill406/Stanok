# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: pick project/template, run generation, show progress/result."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
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
)

from ..services.generate import GenerateCommand, GenerateReport
from ..services.storage import ProjectStore
from .strings import STRINGS
from .worker import GenerateWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Thin view over services: widgets in, signals out, no business logic."""

    def __init__(self, store: ProjectStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._project_ref: str | None = None
        self._worker: GenerateWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._build_ui()
        self.refresh_recent()

    # -- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.MAIN_TITLE)
        root = QWidget(self)
        layout = QVBoxLayout(root)

        group = QGroupBox(STRINGS.MAIN_PROJECT_GROUP, root)
        grid = QVBoxLayout(group)
        row = QHBoxLayout()
        self.recent_list = QListWidget(group)
        self.recent_list.itemClicked.connect(self._on_recent_clicked)
        row.addWidget(self.recent_list, 1)
        self.browse_btn = QPushButton(STRINGS.MAIN_BROWSE, group)
        self.browse_btn.clicked.connect(self._on_browse)
        row.addWidget(self.browse_btn)
        grid.addLayout(row)

        form = QHBoxLayout()
        form.addWidget(QLabel(STRINGS.MAIN_TEMPLATE, group))
        self.template_combo = QComboBox(group)
        form.addWidget(self.template_combo, 1)
        form.addWidget(QLabel(STRINGS.MAIN_SOURCE, group))
        self.source_label = QLabel("-", group)
        form.addWidget(self.source_label, 1)
        grid.addLayout(form)

        opts = QHBoxLayout()
        self.resume_check = QCheckBox(STRINGS.MAIN_RESUME, group)
        opts.addWidget(self.resume_check)
        opts.addWidget(QLabel(STRINGS.MAIN_LIMIT, group))
        self.limit_spin = QSpinBox(group)
        self.limit_spin.setRange(0, 1_000_000)
        opts.addWidget(self.limit_spin)
        opts.addStretch(1)
        grid.addLayout(opts)
        layout.addWidget(group)

        self.generate_btn = QPushButton(STRINGS.MAIN_GENERATE, root)
        self.generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_btn)

        self.progress_bar = QProgressBar(root)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.setCentralWidget(root)
        self.statusBar().showMessage(STRINGS.MAIN_STATUS_READY)

    # -- project selection ------------------------------------------------
    def refresh_recent(self) -> None:
        """Reload recent-projects list from ApplicationJSON."""
        self.recent_list.clear()
        for item in self._store.get_recent():
            label = f"{item.folder} [{item.config}]"
            entry = QListWidgetItem(label, self.recent_list)
            entry.setData(Qt.UserRole, item.folder)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, STRINGS.MAIN_BROWSE)
        if folder:
            self._load_project(folder)

    def _on_recent_clicked(self, item: QListWidgetItem) -> None:
        self._load_project(item.data(Qt.UserRole))

    def _load_project(self, ref: str) -> None:
        try:
            pj, _ = self._store.resolve_project(ref)
        except Exception as e:
            logger.warning(f"open project {ref}: {e}", exc_info=True)
            self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {e}")
            return
        self._project_ref = ref
        self.template_combo.clear()
        self.template_combo.addItems(list(pj.templates))
        self.source_label.setText(pj.data_sources[0].file if pj.data_sources else "-")
        self.statusBar().showMessage(STRINGS.MAIN_STATUS_READY)

    # -- generation --------------------------------------------------------
    def _on_generate(self) -> None:
        if not self._project_ref:
            self._show_error(STRINGS.MAIN_NO_PROJECT)
            return
        limit = self.limit_spin.value()
        cmd = GenerateCommand(
            project_ref=self._project_ref,
            template=self.template_combo.currentText() or None,
            max_docs=limit if limit > 0 else None,
            resume=self.resume_check.isChecked(),
        )
        self.generate_btn.setEnabled(False)
        self._progress_dialog = QProgressDialog(
            STRINGS.MAIN_PROGRESS_TITLE, STRINGS.MAIN_CANCEL, 0, 0, self
        )
        self._progress_dialog.canceled.connect(self._on_cancel)
        self._progress_dialog.show()
        self._worker = GenerateWorker(cmd, store=self._store, parent=self)
        self._worker.progressed.connect(self._on_progressed)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()

    def _on_progressed(self, created: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(created)
        self.statusBar().showMessage(
            STRINGS.MAIN_STATUS_RUNNING.format(created=created, total=total)
        )

    def _finish_run(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        self.generate_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage(STRINGS.MAIN_STATUS_READY)

    def _on_finished(self, report: GenerateReport) -> None:
        self._finish_run()
        if self._project_ref and Path(self._project_ref).is_dir():
            folder = str(Path(self._project_ref).resolve())
            self._store.add_recent(folder, Path(self._project_ref).resolve().name)
            self.refresh_recent()
        text = STRINGS.APP_DONE.format(
            created=report.created,
            skipped=report.skipped,
            errors=len(report.errors),
            elapsed=f"{report.elapsed:.1f}",
        )
        if report.errors:
            details = "\n".join(f"{i}: {msg}" for i, msg in report.errors)
            QMessageBox.information(
                self, STRINGS.MAIN_DONE_TITLE, f"{text}\n\n{details}"
            )
        else:
            QMessageBox.information(self, STRINGS.MAIN_DONE_TITLE, text)

    def _on_failed(self, message: str) -> None:
        self._finish_run()
        self._show_error(f"{STRINGS.MAIN_ERROR_TITLE}: {message}")

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, message)
