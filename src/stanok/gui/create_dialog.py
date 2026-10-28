# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 4: new project creation and project settings (FR-12, 021)."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from .dialogs import ask_yes_no
from .strings import STRINGS
from .theme import set_button_role

logger = logging.getLogger(__name__)


class CreateDialog(QDialog):
    """Modal create/edit view: creation (files) or settings (folder, default)."""

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

    @property
    def _edit_mode(self) -> bool:
        return bool(self._edit_ref)

    # -- UI construction -------------------------------------------------
    def _build_ui(self, folder_hint: str) -> None:
        folder_hint = str(folder_hint or "")
        self.setWindowTitle(
            STRINGS.CRT_EDIT_TITLE if self._edit_mode else STRINGS.CRT_TITLE
        )
        self.resize(620, 480 if not self._edit_mode else 280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)

        title = QLabel(
            STRINGS.CRT_EDIT_TITLE if self._edit_mode else STRINGS.CRT_TITLE, self
        )
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel(STRINGS.CRT_NAME))
        self.name_edit = QLineEdit(self)
        self.name_edit.textChanged.connect(self._update_create_enabled)
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

        if self._edit_mode:
            self._fill_settings()
        else:
            self.xlsx_list = QListWidget(self)
            self.docx_list = QListWidget(self)
            self.xlsx_list.setMinimumHeight(80)
            self.docx_list.setMinimumHeight(80)
            self.copy_check = QCheckBox(STRINGS.CRT_COPY, self)
            layout.addWidget(QLabel(STRINGS.CRT_XLSX))
            layout.addWidget(self.xlsx_list)
            layout.addLayout(self._list_buttons(self.xlsx_list, "Excel (*.xlsx)"))
            layout.addWidget(QLabel(STRINGS.CRT_DOCX))
            layout.addWidget(self.docx_list)
            layout.addLayout(self._list_buttons(self.docx_list, "Word (*.docx)"))
            self.copy_check.setChecked(True)
            layout.addWidget(self.copy_check)

        buttons = QDialogButtonBox(self)
        label = STRINGS.CRT_SAVE if self._edit_mode else STRINGS.CRT_CREATE
        self.create_btn = buttons.addButton(label, QDialogButtonBox.AcceptRole)
        set_button_role(self.create_btn, "primary")
        cancel_btn = buttons.addButton(
            STRINGS.CRT_CANCEL, QDialogButtonBox.RejectRole
        )
        self.create_btn.clicked.connect(self._on_create)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
        self._update_create_enabled()

    def _fill_settings(self) -> None:
        """Prefill settings mode: name (read-only), folder, default template."""
        pj, config_path = self._store.resolve_project(self._edit_ref)
        self.project_name = config_path.stem
        self.name_edit.setText(config_path.stem)
        self.name_edit.setReadOnly(True)
        self.folder_edit.setText(pj.folder or "")
        self._templates = list(pj.templates)
        self.default_combo = QComboBox(self)
        self.layout().addWidget(QLabel(STRINGS.CRT_DEFAULT_TPL))
        for name in self._templates:
            self.default_combo.addItem(name, name)
        idx = self.default_combo.findData(pj.default_template)
        self.default_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.layout().addWidget(self.default_combo)

    def _list_buttons(self, target: QListWidget, filt: str) -> QHBoxLayout:
        row = QHBoxLayout()
        add_btn = QPushButton(STRINGS.CRT_ADD)
        add_btn.clicked.connect(lambda: self._on_add_files(target, filt))
        remove_btn = QPushButton(STRINGS.CRT_REMOVE)
        remove_btn.clicked.connect(lambda: self._on_remove_selected(target))
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addStretch(1)
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
        if not hasattr(self, "create_btn"):
            return  # signals fire while _fill_settings runs before buttons exist
        name = self.name_edit.text().strip()
        folder = self.folder_edit.text().strip() or str(Path.home())
        if self._edit_mode:
            self.create_btn.setEnabled(bool(folder))
            self.path_label.setText(self._project_paths_text(Path(folder)))
            return
        taken = bool(name) and self._store.config_exists(name)
        bad_dir = Path(folder).name in (STRINGS.DATA_DIR, STRINGS.TPL_DIR)
        ok = bool(name) and not taken and not bad_dir
        ok = ok and self.xlsx_list.count() > 0 and self.docx_list.count() > 0
        self.create_btn.setEnabled(ok)
        self._update_preview(name, folder, taken, bad_dir)

    def _update_preview(
        self, name: str, folder: str, taken: bool, bad_dir: bool
    ) -> None:
        if taken:
            self.path_label.setStyleSheet("color: #b42318;")
            self.path_label.setText(STRINGS.CRT_NAME_TAKEN.format(name=name))
        elif bad_dir:
            self.path_label.setStyleSheet("color: #b42318;")
            self.path_label.setText(
                STRINGS.CRT_BAD_DIR.format(name=Path(folder).name)
            )
        else:
            self.path_label.setStyleSheet("")
            target = Path(folder) / (name or "")
            self.path_label.setText(self._project_paths_text(target))

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
        if self._edit_mode:
            if not Path(folder).exists() and not self._confirm_mkdir(folder):
                return
            self._save_settings(folder)
            return
        target = Path(folder).resolve() / self.name_edit.text().strip()
        if not target.exists() and not self._confirm_mkdir(str(target)):
            return
        try:
            self._store.init_project(
                target,
                self.name_edit.text(),
                [self.xlsx_list.item(i).text() for i in range(self.xlsx_list.count())],
                [self.docx_list.item(i).text() for i in range(self.docx_list.count())],
                copy_files=self.copy_check.isChecked(),
            )
        except Exception as e:
            logger.warning(f"create project failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.CRT_ERR_TITLE, str(e))
            return
        self.project_folder = str(target)
        self.project_name = self.name_edit.text().strip()
        self.accept()

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
