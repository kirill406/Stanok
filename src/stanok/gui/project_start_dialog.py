# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window: how to create a project (024).

Three ways in: a minimal empty skeleton, an existing folder, or a copy of a
stored project. Every way ends in ProjectCheckDialog.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..engine.schema import StorageError
from ..services.project_setup import (
    clone_structure,
    create_skeleton,
    ensure_subfolders,
)
from ..services.storage import ProjectStore
from .dialogs import ask_yes_no
from .project_check_dialog import SUBDIRS, ProjectCheckDialog
from .strings import STRINGS
from .theme import set_button_role

logger = logging.getLogger(__name__)


class _ProjectForm(QDialog):
    """Name, base folder and (for a copy) the source project."""

    def __init__(
        self,
        title: str,
        base_hint: str,
        sources: list[str] | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)

        layout.addWidget(QLabel(STRINGS.START_FORM_NAME, self))
        self.name_edit = QLineEdit(self)
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel(STRINGS.START_BASE, self))
        base_row = QHBoxLayout()
        self.base_edit = QLineEdit(base_hint, self)
        base_row.addWidget(self.base_edit)
        browse = QPushButton(STRINGS.START_BROWSE, self)
        browse.clicked.connect(self._on_browse)
        base_row.addWidget(browse)
        layout.addLayout(base_row)

        self.source_combo: QComboBox | None = None
        if sources is not None:
            layout.addWidget(QLabel(STRINGS.START_SOURCE, self))
            self.source_combo = QComboBox(self)
            self.source_combo.addItems(sources)
            layout.addWidget(self.source_combo)

        buttons = QDialogButtonBox(self)
        create_btn = buttons.addButton(
            STRINGS.START_FORM_CREATE, QDialogButtonBox.AcceptRole
        )
        set_button_role(create_btn, "primary")
        cancel_btn = buttons.addButton(STRINGS.CRT_CANCEL, QDialogButtonBox.RejectRole)
        create_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, STRINGS.START_PICK_TITLE, self.base_edit.text()
        )
        if folder:
            self.base_edit.setText(folder)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, self.windowTitle(), STRINGS.START_NAME_EMPTY)
            return
        self.accept()

    @property
    def name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def base(self) -> str:
        return self.base_edit.text().strip()

    @property
    def source(self) -> str:
        if self.source_combo is None:
            return ""
        return self.source_combo.currentText()


class ProjectStartDialog(QDialog):
    """Modal window 1 of creation: description and three buttons."""

    def __init__(
        self,
        store: ProjectStore | None = None,
        folder_hint: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._hint = str(folder_hint or "")
        self.project_name = ""
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.START_TITLE)
        self.resize(560, 300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)

        title = QLabel(STRINGS.START_TITLE, self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        descr = QLabel(STRINGS.START_DESCR, self)
        descr.setWordWrap(True)
        layout.addWidget(descr)

        for text, slot in (
            (STRINGS.START_MINIMAL, self._on_minimal),
            (STRINGS.START_PICK, self._on_pick),
            (STRINGS.START_CLONE, self._on_clone),
        ):
            btn = QPushButton(text, self)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addStretch(1)
        close_btn = QPushButton(STRINGS.START_CLOSE, self)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

    def _run_check(self, folder: Path, name: str, editable: bool) -> None:
        dialog = ProjectCheckDialog(self._store, folder, name, editable, self)
        if dialog.exec_():
            self.project_name = dialog.project_name
            self.accept()

    def _on_minimal(self) -> None:
        form = _ProjectForm(STRINGS.START_FORM_TITLE_MINIMAL, self._hint, None, self)
        if not form.exec_():
            return
        try:
            folder = create_skeleton(form.base or Path.home(), form.name, self._store)
        except (StorageError, OSError) as e:
            logger.warning(f"create skeleton {form.name}: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.START_ERR_TITLE, str(e))
            return
        self._run_check(folder, form.name, editable=False)

    def _on_clone(self) -> None:
        sources = [name for name, _pj in self._store.list_named()]
        if not sources:
            QMessageBox.information(self, STRINGS.START_TITLE, STRINGS.START_NO_SOURCES)
            return
        form = _ProjectForm(
            STRINGS.START_FORM_TITLE_CLONE, self._hint, sources, self
        )
        if not form.exec_():
            return
        try:
            folder = clone_structure(
                form.source, form.base or Path.home(), form.name, self._store
            )
        except (StorageError, OSError) as e:
            logger.warning(f"clone project {form.source}: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.START_ERR_TITLE, str(e))
            return
        self._run_check(folder, form.name, editable=False)

    def _on_pick(self) -> None:
        picked = QFileDialog.getExistingDirectory(
            self, STRINGS.START_PICK_TITLE, self._hint
        )
        if not picked:
            return
        folder = Path(picked)
        if self._store.config_exists(folder.name):
            # Spec 3.2: a project with this name already exists — just open it.
            self.project_name = folder.name
            self.accept()
            return
        missing = [sub for sub in SUBDIRS if not (folder / sub).is_dir()]
        if missing and ask_yes_no(
            self,
            STRINGS.START_TITLE,
            STRINGS.START_MISSING_ASK.format(dirs=", ".join(missing)),
        ):
            try:
                ensure_subfolders(folder)
            except OSError as e:
                logger.warning(f"ensure subfolders {folder}: {e}", exc_info=True)
                QMessageBox.warning(self, STRINGS.START_ERR_TITLE, str(e))
                return
        self._run_check(folder, folder.name, editable=True)
