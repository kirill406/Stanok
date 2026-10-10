# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 2: project templates, per-template counts and runs."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.generate import GenerateCommand, GenerateReport
from ..services.storage import ProjectStore
from .fields_dialog import FieldsDialog
from .strings import STRINGS
from .worker import GenerateWorker

logger = logging.getLogger(__name__)


class ProjectDialog(QDialog):
    """Modal project view: template table with counts and per-template runs."""

    def __init__(
        self, project_ref: str, store: ProjectStore | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._project_ref = project_ref
        self._worker: GenerateWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._running = False
        pj, _ = self._store.resolve_project(project_ref)
        self._pj = pj
        self._template_names = list(pj.templates)
        self._build_ui()

    # -- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(
            STRINGS.PROJ_TITLE.format(name=Path(self._project_ref).name)
        )
        self.resize(900, 650)
        layout = QVBoxLayout(self)

        ds_file = self._pj.data_sources[0].file if self._pj.data_sources else "-"
        layout.addWidget(QLabel(STRINGS.PROJ_DATA.format(path=self._project_ref)))
        layout.addWidget(QLabel(STRINGS.PROJ_SOURCE.format(file=ds_file)))

        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            [STRINGS.PROJ_TPL_COL, STRINGS.PROJ_COUNT_COL, ""]
        )
        self.table.setRowCount(len(self._template_names))
        self.table.cellClicked.connect(self._on_cell_clicked)
        for row, name in enumerate(self._template_names):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            spin = QSpinBox(self.table)
            spin.setRange(0, 1_000_000)
            spin.setToolTip(STRINGS.PROJ_COUNT_TIP)
            self.table.setCellWidget(row, 1, spin)
            btn = QPushButton(STRINGS.PROJ_RUN, self.table)
            btn.clicked.connect(
                lambda _checked=False, template=name: self._on_run_template(template)
            )
            self.table.setCellWidget(row, 2, btn)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- window 3 hook ------------------------------------------------------
    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col == 0:
            self._open_fields_dialog(self._template_names[row])

    def _open_fields_dialog(self, template_name: str) -> None:
        """Open window 3 (FieldsDialog, 010)."""
        dialog = FieldsDialog(self._project_ref, template_name, self._store, self)
        dialog.exec_()

    # -- per-template run ----------------------------------------------------
    def _on_run_template(self, template_name: str) -> None:
        if self._running:
            return
        self._running = True
        row = self._template_names.index(template_name)
        spin = self.table.cellWidget(row, 1)
        limit = spin.value()
        cmd = GenerateCommand(
            project_ref=self._project_ref,
            template=template_name,
            max_docs=limit if limit > 0 else None,
        )
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
        if self._progress_dialog is not None:
            self._progress_dialog.setLabelText(
                STRINGS.MAIN_STATUS_RUNNING.format(created=created, total=total)
            )

    def _finish_run(self) -> None:
        self._running = False
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None

    def _on_finished(self, report: GenerateReport) -> None:
        self._finish_run()
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
        QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, message)
