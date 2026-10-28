# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project settings dialog: folder and default template (021, 024).

Creating projects moved to ProjectStartDialog / ProjectCheckDialog (024).
"""

from __future__ import annotations

import logging
from pathlib import Path

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

from ..services.storage import ProjectStore
from .dialogs import ask_yes_no
from .strings import STRINGS
from .theme import set_button_role

logger = logging.getLogger(__name__)


class CreateDialog(QDialog):
    """Modal settings view for an existing project (edit_ref is required)."""

    def __init__(
        self,
        store: ProjectStore | None = None,
        folder_hint: str = "",
        parent=None,
        edit_ref: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._edit_ref = edit_ref
        self._templates: list[str] = []
        self.project_folder: str = ""
        self.project_name: str = ""
        self._build_ui(folder_hint)

    # -- UI construction -------------------------------------------------
    def _build_ui(self, folder_hint: str) -> None:
        folder_hint = str(folder_hint or "")
        self.setWindowTitle(STRINGS.CRT_EDIT_TITLE)
        self.resize(620, 280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)

        title = QLabel(STRINGS.CRT_EDIT_TITLE, self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel(STRINGS.CRT_NAME))
        self.name_edit = QLineEdit(self)
        self.name_edit.setReadOnly(True)
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel(STRINGS.CRT_FOLDER))
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit(folder_hint, self)
        self.folder_edit.textChanged.connect(self._update_create_enabled)
        folder_row.addWidget(self.folder_edit)
        browse_btn = QPushButton(STRINGS.CRT_BROWSE, self)
        browse_btn.clicked.connect(self._on_browse_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        self.path_label = QLabel(self)
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self._fill_settings()

        buttons = QDialogButtonBox(self)
        self.create_btn = buttons.addButton(STRINGS.CRT_SAVE, QDialogButtonBox.AcceptRole)
        set_button_role(self.create_btn, "primary")
        cancel_btn = buttons.addButton(
            STRINGS.CRT_CANCEL, QDialogButtonBox.RejectRole
        )
        self.create_btn.clicked.connect(self._on_create)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
        self._update_create_enabled()

    def _fill_settings(self) -> None:
        """Prefill settings: name (read-only), folder, default template."""
        pj, config_path = self._store.resolve_project(self._edit_ref)
        self.project_name = config_path.stem
        self.name_edit.setText(config_path.stem)
        self.folder_edit.setText(pj.folder or "")
        self._templates = list(pj.templates)
        self.default_combo = QComboBox(self)
        self.layout().addWidget(QLabel(STRINGS.CRT_DEFAULT_TPL))
        for name in self._templates:
            self.default_combo.addItem(name, name)
        idx = self.default_combo.findData(pj.default_template)
        self.default_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.layout().addWidget(self.default_combo)

    # -- slots -----------------------------------------------------------
    def _on_browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, STRINGS.CRT_FOLDER)
        if folder:
            self.folder_edit.setText(folder)

    def _update_create_enabled(self) -> None:
        if not hasattr(self, "create_btn"):
            return  # signals fire while _fill_settings runs before buttons exist
        folder = self.folder_edit.text().strip() or str(Path.home())
        self.create_btn.setEnabled(bool(folder))
        self.path_label.setText(self._project_paths_text(Path(folder)))

    def _project_paths_text(self, base: Path) -> str:
        """Project folder and its Данные/Шаблоны/Результат as absolute lines."""
        base = base.resolve()
        lines = [STRINGS.CRT_PATH.format(path=base)]
        lines += [
            str(base / sub)
            for sub in (
                STRINGS.DATA_DIR,
                STRINGS.TPL_DIR,
                STRINGS.GEN_RESULT_DIR,
            )
        ]
        return "\n".join(lines)

    def _confirm_mkdir(self, path: str) -> bool:
        """Ask the user to create a missing folder; True if confirmed."""
        return ask_yes_no(
            self,
            self.windowTitle(),
            STRINGS.CRT_MKDIR_ASK.format(path=path),
        )

    def _on_create(self) -> None:
        folder = self.folder_edit.text().strip() or str(Path.home())
        if not Path(folder).exists() and not self._confirm_mkdir(folder):
            return
        self._save_settings(folder)

    def _save_settings(self, folder: str) -> None:
        try:
            default = self.default_combo.currentData()
            if default:
                self._store.set_default_template(self._edit_ref, default)
            self._store.set_project_folder(self._edit_ref, folder)
        except Exception as e:
            logger.warning(f"save settings failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.CRT_SAVE_ERR_TITLE, str(e))
            return
        self.project_folder = str(Path(folder).resolve())
        self.accept()
