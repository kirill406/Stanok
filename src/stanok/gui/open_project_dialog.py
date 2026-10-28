# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window: pick an existing project by config name (020, 022)."""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)

from ..services.import_export import ProjectLayout, detect_project_layout
from ..services.storage import ProjectStore
from .project_check_dialog import ProjectCheckDialog
from .strings import STRINGS
from .theme import set_button_role

logger = logging.getLogger(__name__)


class OpenProjectDialog(QDialog):
    """List known projects; import .stanok files or create from a folder."""

    def __init__(self, store: ProjectStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self.selected_config: str = ""
        self.created_config: str = ""
        self.setWindowTitle(STRINGS.OPEN_TITLE)
        self.resize(600, 440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel(STRINGS.OPEN_TITLE, self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        subtitle = QLabel(STRINGS.OPEN_SUBTITLE, self)
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        self.list = QListWidget(self)
        self.list.setSpacing(4)
        self.list.setTextElideMode(Qt.ElideMiddle)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.list)
        self.empty_label = QLabel(STRINGS.OPEN_EMPTY, self)
        self.empty_label.setObjectName("muted")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        buttons = QDialogButtonBox(self)
        self.pick_btn = buttons.addButton(
            STRINGS.OPEN_PICK, QDialogButtonBox.ActionRole
        )
        self.open_btn = buttons.addButton(
            STRINGS.MAIN_OPEN, QDialogButtonBox.AcceptRole
        )
        set_button_role(self.open_btn, "primary")
        cancel_btn = buttons.addButton(
            STRINGS.SET_CANCEL, QDialogButtonBox.RejectRole
        )
        self.pick_btn.clicked.connect(self._on_pick_folder)
        self.open_btn.clicked.connect(self._on_open)
        cancel_btn.clicked.connect(self.reject)
        self.list.itemDoubleClicked.connect(lambda _item: self._on_open())
        layout.addWidget(buttons)

        self._reload_list()

    def _reload_list(self, select: str = "") -> None:
        """Rebuild project rows; optionally select a config name."""
        self.list.clear()
        for config, pj in self._store.list_named():
            folder = pj.folder or STRINGS.OPEN_NO_FOLDER
            item = QListWidgetItem(f"{config}  —  {folder}", self.list)
            item.setData(Qt.UserRole, config)
        count = self.list.count()
        self.list.setEnabled(count > 0)
        self.empty_label.setVisible(count == 0)
        self.open_btn.setEnabled(count > 0)
        if count:
            row = next(
                (
                    i
                    for i in range(count)
                    if self.list.item(i).data(Qt.UserRole) == select
                ),
                0,
            )
            self.list.setCurrentRow(row)

    def _on_pick_folder(self) -> None:
        """Import configs from a folder, or prefill creation from its layout."""
        folder = QFileDialog.getExistingDirectory(self, STRINGS.OPEN_PICK)
        if not folder:
            return
        report = self._store.import_configs(folder)
        if report.imported:
            text = STRINGS.OPEN_IMPORTED.format(count=len(report.imported))
            if report.failed:
                text += "\n" + STRINGS.OPEN_IMPORT_ERRORS.format(
                    count=len(report.failed)
                )
            if report.missing_folder:
                text += "\n" + STRINGS.OPEN_IMPORT_MISSING.format(
                    names=", ".join(report.missing_folder)
                )
            QMessageBox.information(self, STRINGS.OPEN_TITLE, text)
            self._reload_list(report.imported[0])
            return
        if report.failed:
            QMessageBox.warning(self, STRINGS.OPEN_TITLE, STRINGS.OPEN_FAILED)
            return
        layout = detect_project_layout(folder)
        if layout is None:
            QMessageBox.warning(self, STRINGS.OPEN_TITLE, STRINGS.OPEN_FAILED)
            return
        self._create_from_layout(layout)

    def _create_from_layout(self, layout: ProjectLayout) -> None:
        """Open the create dialog prefilled from an existing project folder."""
        dialog = ProjectCheckDialog(
            self._store, layout.folder, layout.folder.name, True, self
        )
        if not dialog.exec_():
            return
        self.created_config = dialog.project_name
        self.selected_config = dialog.project_name
        self.accept()

    def _on_open(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        self.selected_config = item.data(Qt.UserRole)
        self.accept()
