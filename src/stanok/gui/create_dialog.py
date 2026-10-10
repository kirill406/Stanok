# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 4: new project creation (FR-12)."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..services.storage import ProjectStore
from .strings import STRINGS

logger = logging.getLogger(__name__)


class CreateDialog(QDialog):
    """Modal new-project view: name, folder, xlsx/docx lists, copy flag."""

    def __init__(
        self,
        store: ProjectStore | None = None,
        folder_hint: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self.project_folder: str = ""
        self.project_name: str = ""
        self._build_ui(folder_hint)

    # -- UI construction -------------------------------------------------
    def _build_ui(self, folder_hint: str) -> None:
        self.setWindowTitle(STRINGS.CRT_TITLE)
        self.resize(600, 450)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(STRINGS.CRT_NAME))
        self.name_edit = QLineEdit(self)
        self.name_edit.textChanged.connect(self._update_create_enabled)
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel(STRINGS.CRT_FOLDER))
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit(folder_hint, self)
        folder_row.addWidget(self.folder_edit)
        browse_btn = QPushButton(STRINGS.CRT_BROWSE, self)
        browse_btn.clicked.connect(self._on_browse_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        self.xlsx_list = QListWidget(self)
        self.docx_list = QListWidget(self)
        layout.addWidget(QLabel(STRINGS.CRT_XLSX))
        layout.addWidget(self.xlsx_list)
        layout.addLayout(
            self._list_buttons(self.xlsx_list, "Excel (*.xlsx)")
        )
        layout.addWidget(QLabel(STRINGS.CRT_DOCX))
        layout.addWidget(self.docx_list)
        layout.addLayout(
            self._list_buttons(self.docx_list, "Word (*.docx)")
        )

        self.copy_check = QCheckBox(STRINGS.CRT_COPY, self)
        self.copy_check.setChecked(True)
        layout.addWidget(self.copy_check)

        buttons = QDialogButtonBox(self)
        self.create_btn = buttons.addButton(
            STRINGS.CRT_CREATE, QDialogButtonBox.AcceptRole
        )
        cancel_btn = buttons.addButton(
            STRINGS.CRT_CANCEL, QDialogButtonBox.RejectRole
        )
        self.create_btn.clicked.connect(self._on_create)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
        self._update_create_enabled()

    def _list_buttons(self, target: QListWidget, filt: str) -> QHBoxLayout:
        row = QHBoxLayout()
        add_btn = QPushButton(STRINGS.CRT_ADD)
        add_btn.clicked.connect(lambda: self._on_add_files(target, filt))
        remove_btn = QPushButton(STRINGS.CRT_REMOVE)
        remove_btn.clicked.connect(lambda: self._on_remove_selected(target))
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        return row

    # -- slots -----------------------------------------------------------
    def _on_browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, STRINGS.CRT_FOLDER)
        if folder:
            self.folder_edit.setText(folder)

    def _on_add_files(self, target: QListWidget, filt: str) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, STRINGS.CRT_ADD, "", filt)
        existing = {target.item(i).text() for i in range(target.count())}
        for f in files:
            if f not in existing:
                target.addItem(f)
                existing.add(f)
        self._update_create_enabled()

    def _on_remove_selected(self, target: QListWidget) -> None:
        for item in target.selectedItems():
            target.takeItem(target.row(item))
        self._update_create_enabled()

    def _update_create_enabled(self) -> None:
        ok = bool(self.name_edit.text().strip())
        ok = ok and self.xlsx_list.count() > 0 and self.docx_list.count() > 0
        self.create_btn.setEnabled(ok)

    def _on_create(self) -> None:
        folder = self.folder_edit.text().strip() or str(Path.home())
        try:
            self._store.init_project(
                folder,
                self.name_edit.text(),
                [self.xlsx_list.item(i).text() for i in range(self.xlsx_list.count())],
                [self.docx_list.item(i).text() for i in range(self.docx_list.count())],
                copy_files=self.copy_check.isChecked(),
            )
        except Exception as e:
            logger.warning(f"create project failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.CRT_ERR_TITLE, str(e))
            return
        self.project_folder = str(Path(folder).resolve())
        self.project_name = self.name_edit.text().strip()
        self.accept()
