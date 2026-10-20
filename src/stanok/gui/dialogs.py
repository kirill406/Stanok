# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Message dialogs with explicit Russian button labels.

Qt's standard buttons are localized only when a Qt translation is installed.
The frozen build may lack ``qtbase_ru.qm``, so every choice dialog labels its
buttons from ``STRINGS`` instead of relying on it.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QInputDialog, QMessageBox, QWidget

from .strings import STRINGS


def _label(box: QMessageBox, button: QMessageBox.StandardButton, text: str) -> None:
    btn = box.button(button)
    if btn is not None:
        btn.setText(text)


def ask_yes_no(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    default_yes: bool = True,
) -> bool:
    """Ask a Yes/No question; True only when the user chooses «Да»."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    _label(box, QMessageBox.Yes, STRINGS.BTN_YES)
    _label(box, QMessageBox.No, STRINGS.BTN_NO)
    box.setDefaultButton(QMessageBox.Yes if default_yes else QMessageBox.No)
    box.setEscapeButton(QMessageBox.No)
    return box.exec_() == QMessageBox.Yes


def ask_save_discard_cancel(parent: QWidget | None, title: str, text: str) -> int:
    """Ask about unsaved changes; returns QMessageBox.Save/Discard/Cancel."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(
        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
    )
    _label(box, QMessageBox.Save, STRINGS.BTN_SAVE)
    _label(box, QMessageBox.Discard, STRINGS.BTN_DISCARD)
    _label(box, QMessageBox.Cancel, STRINGS.MAIN_CANCEL)
    box.setDefaultButton(QMessageBox.Save)
    box.setEscapeButton(QMessageBox.Cancel)
    return box.exec_()


def ask_text(
    parent: QWidget | None, title: str, label: str, *, text: str = ""
) -> tuple[str, bool]:
    """Single-line text input with Russian OK/Cancel buttons."""
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextValue(text)
    dialog.setOkButtonText(STRINGS.BTN_OK)
    dialog.setCancelButtonText(STRINGS.MAIN_CANCEL)
    accepted = dialog.exec_() == QInputDialog.Accepted
    return dialog.textValue(), accepted
