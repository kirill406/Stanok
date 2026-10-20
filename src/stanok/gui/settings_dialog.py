# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings dialog: log level + data-folder info (018)."""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..services.storage import ProjectStore
from .strings import STRINGS
from .theme import set_button_role
from .widgets import ElidedLabel

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class SettingsDialog(QDialog):
    """Modal settings view: log level persisted to AJ, applied live."""

    def __init__(
        self, store: ProjectStore | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._build_ui()

    def _build_ui(self) -> None:
        from .. import __version__

        self.setWindowTitle(STRINGS.SET_TITLE)
        self.resize(500, 380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)

        title = QLabel(STRINGS.SET_TITLE, self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addWidget(QLabel(STRINGS.SET_LOG_LEVEL))
        self.level_combo = QComboBox(self)
        self.level_combo.addItems(LOG_LEVELS)
        current = str(self._store.get_setting("log_level", "INFO")).upper()
        if current in LOG_LEVELS:
            self.level_combo.setCurrentText(current)
        layout.addWidget(self.level_combo)

        layout.addWidget(QLabel(STRINGS.SET_HOME, self))
        home = ElidedLabel(str(self._store.home_dir), self, Qt.ElideMiddle)
        home.setObjectName("muted")
        layout.addWidget(home)
        layout.addWidget(QLabel(STRINGS.SET_LOG_FILE, self))
        log_file = ElidedLabel(
            str(self._store.home_dir / "stanok.log"), self, Qt.ElideMiddle
        )
        log_file.setObjectName("muted")
        layout.addWidget(log_file)
        version = QLabel(self)
        version.setObjectName("muted")
        version.setText(f"{STRINGS.SET_VERSION} {__version__}")
        layout.addWidget(version)

        folder_btn = QPushButton(STRINGS.SET_OPEN_FOLDER, self)
        folder_btn.clicked.connect(self._on_open_folder)
        layout.addWidget(folder_btn)

        buttons = QDialogButtonBox(self)
        save_btn = buttons.addButton(
            STRINGS.SET_SAVE, QDialogButtonBox.AcceptRole
        )
        set_button_role(save_btn, "primary")
        cancel_btn = buttons.addButton(
            STRINGS.SET_CANCEL, QDialogButtonBox.RejectRole
        )
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _on_open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._store.home_dir)))

    def _on_save(self) -> None:
        level = self.level_combo.currentText()
        self._store.set_setting("log_level", level)
        logging.getLogger().setLevel(level)
        self.accept()
