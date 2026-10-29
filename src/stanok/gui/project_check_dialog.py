# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Hints and structure check of a project folder before creation (024).

The check button runs check_project_structure. Without errors the project is
created (config in Home); warnings are shown first and do not block.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..engine.schema import SchemaError, StorageError
from ..services.project_check import ProjectCheck, check_project_structure
from ..services.project_setup import create_project_from_check, ensure_subfolders
from ..services.storage import ProjectStore
from .strings import STRINGS
from .theme import set_button_role

logger = logging.getLogger(__name__)

SUBDIRS = (STRINGS.DATA_DIR, STRINGS.TPL_DIR)


class ProjectCheckDialog(QDialog):
    """Modal: hints, error/warning list, «Проверить» and «Закрыть»."""

    def __init__(
        self,
        store: ProjectStore,
        folder: str | Path,
        name: str = "",
        editable_name: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._folder = Path(folder)
        self._shown_warnings: tuple = ()
        self.project_name = ""
        self._build_ui(name, editable_name)
        self._refresh_missing()

    def _build_ui(self, name: str, editable_name: bool) -> None:
        self.setWindowTitle(STRINGS.PCHK_TITLE)
        self.resize(660, 540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)

        title = QLabel(STRINGS.PCHK_TITLE, self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        hint = QLabel(STRINGS.PCHK_HINT, self)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        path = QLabel(STRINGS.PCHK_FOLDER_LABEL.format(path=self._folder), self)
        path.setWordWrap(True)
        layout.addWidget(path)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(STRINGS.PCHK_NAME_LABEL, self))
        self.name_edit = QLineEdit(name, self)
        self.name_edit.setReadOnly(not editable_name)
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(
            [STRINGS.PCHK_COL_FILE, STRINGS.PCHK_COL_COLUMN, STRINGS.PCHK_COL_MESSAGE]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        self.status = QLabel(self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.dirs_btn = QPushButton(STRINGS.PCHK_CREATE_DIRS, self)
        self.dirs_btn.clicked.connect(self._on_create_dirs)
        buttons.addWidget(self.dirs_btn)
        buttons.addStretch(1)
        self.check_btn = QPushButton(STRINGS.PCHK_CHECK, self)
        set_button_role(self.check_btn, "primary")
        self.check_btn.clicked.connect(self._on_check)
        buttons.addWidget(self.check_btn)
        close_btn = QPushButton(STRINGS.PCHK_CLOSE, self)
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _missing_dirs(self) -> list[str]:
        return [sub for sub in SUBDIRS if not (self._folder / sub).is_dir()]

    def _refresh_missing(self) -> None:
        self.dirs_btn.setVisible(bool(self._missing_dirs()))

    def _on_create_dirs(self) -> None:
        try:
            ensure_subfolders(self._folder)
        except OSError as e:
            logger.warning(f"create subfolders {self._folder}: {e}", exc_info=True)
            self.status.setText(STRINGS.PCHK_CREATE_FAILED.format(cause=e))
            return
        self._refresh_missing()
        self._on_check()

    def _on_check(self) -> None:
        name = self.name_edit.text().strip()
        check = check_project_structure(self._folder, name, self._store)
        self._show(check)
        if not check.ok:
            self._shown_warnings = ()
            self.check_btn.setText(STRINGS.PCHK_CHECK)
            self.status.setText(STRINGS.PCHK_ERRORS_COUNT.format(count=len(check.errors)))
            return
        warnings = tuple((i.file, i.message) for i in check.warnings)
        if warnings and warnings != self._shown_warnings:
            # Show the warnings first; a second click on «Создать проект» goes on.
            self._shown_warnings = warnings
            self.check_btn.setText(STRINGS.PCHK_CREATE)
            self.status.setText(STRINGS.PCHK_WARNINGS_HINT)
            return
        self._create(name, check)

    def _create(self, name: str, check: ProjectCheck) -> None:
        try:
            create_project_from_check(self._store, self._folder, name, check)
        except (StorageError, SchemaError, OSError) as e:
            logger.warning(f"create project {name}: {e}", exc_info=True)
            self.status.setText(STRINGS.PCHK_CREATE_FAILED.format(cause=e))
            return
        except Exception as e:
            logger.critical(f"unexpected create project {name}: {e}", exc_info=True)
            self.status.setText(STRINGS.PCHK_CREATE_FAILED.format(cause=e))
            return
        self.project_name = name
        self.accept()

    def _show(self, check: ProjectCheck) -> None:
        rows = [(i, i.message) for i in check.errors] + [
            (i, STRINGS.PCHK_WARN_PREFIX.format(message=i.message))
            for i in check.warnings
        ]
        self.table.setRowCount(len(rows))
        for row, (issue, text) in enumerate(rows):
            for col, value in enumerate((issue.file, issue.column or "", text)):
                self.table.setItem(row, col, QTableWidgetItem(value))
