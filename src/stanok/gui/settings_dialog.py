# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings dialog: log level + data-folder info (018)."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QUrl
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
        self.resize(420, 220)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(STRINGS.SET_LOG_LEVEL))
        self.level_combo = QComboBox(self)
        self.level_combo.addItems(LOG_LEVELS)
        current = str(self._store.get_setting("log_level", "INFO")).upper()
        if current in LOG_LEVELS:
            self.level_combo.setCurrentText(current)
        layout.addWidget(self.level_combo)

        layout.addWidget(
            QLabel(f"{STRINGS.SET_HOME} {self._store.home_dir}")
        )
        layout.addWidget(
            QLabel(f"{STRINGS.SET_LOG_FILE} {self._store.home_dir / 'stanok.log'}")
        )
        layout.addWidget(QLabel(f"{STRINGS.SET_VERSION} {__version__}"))

        folder_btn = QPushButton(STRINGS.SET_OPEN_FOLDER, self)
        folder_btn.clicked.connect(self._on_open_folder)
        layout.addWidget(folder_btn)

        buttons = QDialogButtonBox(self)
        save_btn = buttons.addButton(
            STRINGS.SET_SAVE, QDialogButtonBox.AcceptRole
        )
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
