# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project settings dialog: folder, default template, result copy folders (021, 024, 025).

Creating projects moved to ProjectStartDialog / ProjectCheckDialog (024).
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
    QWidget,
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
        self._result_dirs: list[str] = []
        self._section_paths: dict[str, QLabel] = {}
        self.project_folder: str = ""
        self.project_name: str = ""
        self._build_ui(folder_hint)

    # -- UI construction -------------------------------------------------
    def _build_ui(self, folder_hint: str) -> None:
        folder_hint = str(folder_hint or "")
        self.setWindowTitle(STRINGS.CRT_EDIT_TITLE)
        # Minimum width only: the height follows the content (sections, copies).
        self.setMinimumWidth(620)
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

        self._build_sections(layout)

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

    def _build_sections(self, layout: QVBoxLayout) -> None:
        """Данные, Шаблоны, Результаты — each with the path to its folder (025)."""
        for title, sub in (
            (STRINGS.CRT_SECTION_DATA, STRINGS.DATA_DIR),
            (STRINGS.CRT_SECTION_TPL, STRINGS.TPL_DIR),
        ):
            layout.addWidget(self._section_title(title))
            layout.addWidget(self._section_path(sub))

        header = QHBoxLayout()
        header.addWidget(self._section_title(STRINGS.CRT_SECTION_RESULTS))
        header.addStretch(1)
        add_btn = self._glyph_button("+", STRINGS.CRT_RESULT_COPY_TIP, self)
        add_btn.clicked.connect(self._on_add_result_dir)
        header.addWidget(add_btn)
        layout.addLayout(header)
        layout.addWidget(self._section_path(STRINGS.GEN_RESULT_DIR))

        self._copies_panel = QWidget(self)
        self._copies_layout = QVBoxLayout(self._copies_panel)
        self._copies_layout.setContentsMargins(0, 0, 0, 0)
        self._copies_layout.setSpacing(4)
        layout.addWidget(self._copies_panel)

    def _glyph_button(self, text: str, tip: str, parent: QWidget) -> QPushButton:
        """Small square button with a one-character label, shown larger than text."""
        btn = QPushButton(text, parent)
        # Size comes from the theme (objectName rule). A widget-level stylesheet
        # would also change the font of the tooltip shown for this button.
        btn.setObjectName("glyphButton")
        btn.setToolTip(tip)
        btn.setFixedSize(34, 30)
        return btn

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("sectionTitle")
        return label

    def _section_path(self, sub: str) -> QLabel:
        label = QLabel(self)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._section_paths[sub] = label
        return label

    def _fill_settings(self) -> None:
        """Prefill settings: name (read-only), folder, default template, copy folders."""
        pj, config_path = self._store.resolve_project(self._edit_ref)
        self.project_name = config_path.stem
        self.name_edit.setText(config_path.stem)
        self.folder_edit.setText(pj.folder or "")
        self._templates = list(pj.templates)
        self._result_dirs = list(pj.result_dirs)
        self.default_combo = QComboBox(self)
        self.layout().addWidget(QLabel(STRINGS.CRT_DEFAULT_TPL))
        for name in self._templates:
            self.default_combo.addItem(name, name)
        idx = self.default_combo.findData(pj.default_template)
        self.default_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.layout().addWidget(self.default_combo)
        self._refresh_copies()

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
        self._refresh_paths(Path(folder))

    def _refresh_paths(self, base: Path) -> None:
        """Show the absolute path of each section's folder under the project folder."""
        base = base.resolve()
        for sub, label in self._section_paths.items():
            label.setText(str(base / sub))

    def _refresh_copies(self) -> None:
        """Rebuild the list of result copy folders, one row with a remove button each."""
        while self._copies_layout.count():
            item = self._copies_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        if not self._result_dirs:
            self._copies_layout.addWidget(self._muted(STRINGS.CRT_COPIES_NONE))
            return
        for path in self._result_dirs:
            row = QWidget(self._copies_panel)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(self._path_text(path, row))
            remove_btn = self._glyph_button("×", STRINGS.CRT_RESULT_REMOVE_TIP, row)
            remove_btn.clicked.connect(
                lambda _checked=False, p=path: self._on_remove_result_dir(p)
            )
            row_layout.addWidget(remove_btn)
            self._copies_layout.addWidget(row)

    def _muted(self, text: str) -> QLabel:
        label = QLabel(text, self._copies_panel)
        label.setObjectName("muted")
        return label

    def _path_text(self, path: str, parent: QWidget) -> QLabel:
        label = QLabel(path, parent)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def _on_add_result_dir(self) -> None:
        base = Path(self.folder_edit.text().strip() or str(Path.home()))
        picked = QFileDialog.getExistingDirectory(
            self, STRINGS.CRT_RESULT_COPY_PICK, str(base)
        )
        if not picked:
            return
        path = str(Path(picked).resolve())
        if path == str((base / STRINGS.GEN_RESULT_DIR).resolve()):
            QMessageBox.information(self, self.windowTitle(), STRINGS.CRT_RESULT_COPY_OWN)
            return
        if path in self._result_dirs:
            QMessageBox.information(self, self.windowTitle(), STRINGS.CRT_RESULT_COPY_DUP)
            return
        self._result_dirs.append(path)
        self._refresh_copies()

    def _on_remove_result_dir(self, path: str) -> None:
        if path in self._result_dirs:
            self._result_dirs.remove(path)
        self._refresh_copies()

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
            self._store.set_result_dirs(self._edit_ref, self._result_dirs)
            self._store.set_project_folder(self._edit_ref, folder)
        except Exception as e:
            logger.warning(f"save settings failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.CRT_SAVE_ERR_TITLE, str(e))
            return
        self.project_folder = str(Path(folder).resolve())
        self.accept()
