# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Thin Qt adapter (no business logic). No heavy imports here."""

from __future__ import annotations

import sys
from pathlib import Path


def icon_path() -> Path:
    """Filesystem path of the bundled app icon (dev, onedir and onefile)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        return Path(meipass) / "stanok" / "gui" / "icon.png"
    return Path(__file__).resolve().parent / "icon.png"


def apply_app_icon(app) -> None:
    """Set application + main-window icon (Qt import stays lazy)."""
    from PyQt5.QtGui import QIcon

    path = icon_path()
    if path.is_file():
        app.setWindowIcon(QIcon(str(path)))
