# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window: pick an existing project by config name (020)."""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ..services.storage import ProjectStore
from .strings import STRINGS

logger = logging.getLogger(__name__)


class OpenProjectDialog(QDialog):
    """List known projects (config + folder); open by config name."""

    def __init__(self, store: ProjectStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self.selected_config: str = ""
        self.setWindowTitle(STRINGS.OPEN_TITLE)
        self.resize(560, 400)
        layout = QVBoxLayout(self)

        self.list = QListWidget(self)
        for config, pj in self._store.list_named():
            folder = pj.folder or STRINGS.OPEN_NO_FOLDER
            item = QListWidgetItem(f"{config}  —  {folder}", self.list)
            item.setData(Qt.UserRole, config)
        layout.addWidget(self.list)

        if self.list.count() == 0:
            layout.addWidget(QLabel(STRINGS.OPEN_EMPTY))
            self.list.setEnabled(False)
        else:
            self.list.setCurrentRow(0)

        buttons = QDialogButtonBox(self)
        self.open_btn = buttons.addButton(
            STRINGS.MAIN_OPEN, QDialogButtonBox.AcceptRole
        )
        cancel_btn = buttons.addButton(
            STRINGS.SET_CANCEL, QDialogButtonBox.RejectRole
        )
        self.open_btn.setEnabled(self.list.count() > 0)
        self.open_btn.clicked.connect(self._on_open)
        cancel_btn.clicked.connect(self.reject)
        self.list.itemDoubleClicked.connect(lambda _item: self._on_open())
        layout.addWidget(buttons)

    def _on_open(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        self.selected_config = item.data(Qt.UserRole)
        self.accept()
