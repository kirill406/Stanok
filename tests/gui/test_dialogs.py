# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for Russian-labelled message dialogs."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox

from stanok.gui import dialogs


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_ask_yes_no_shows_russian_buttons(qapp, monkeypatch):
    seen = {}

    def fake_exec(box):
        seen["yes"] = box.button(QMessageBox.Yes).text()
        seen["no"] = box.button(QMessageBox.No).text()
        seen["default"] = box.defaultButton().text()
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "exec_", fake_exec)
    assert dialogs.ask_yes_no(None, "t", "x") is False
    assert seen == {"yes": "Да", "no": "Нет", "default": "Да"}


def test_ask_yes_no_yes_returns_true(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: QMessageBox.Yes)
    assert dialogs.ask_yes_no(None, "t", "x", default_yes=False) is True


def test_ask_save_discard_cancel_shows_russian_buttons(qapp, monkeypatch):
    seen = {}

    def fake_exec(box):
        for key, button in (
            ("save", QMessageBox.Save),
            ("discard", QMessageBox.Discard),
            ("cancel", QMessageBox.Cancel),
        ):
            seen[key] = box.button(button).text()
        return QMessageBox.Discard

    monkeypatch.setattr(QMessageBox, "exec_", fake_exec)
    answer = dialogs.ask_save_discard_cancel(None, "t", "x")
    assert answer == QMessageBox.Discard
    assert seen == {
        "save": "Сохранить",
        "discard": "Не сохранять",
        "cancel": "Отмена",
    }


def test_ask_text_shows_russian_buttons(qapp, monkeypatch):
    seen = {}

    def fake_exec(dialog):
        seen["ok"] = dialog.okButtonText()
        seen["cancel"] = dialog.cancelButtonText()
        dialog.setTextValue("doc")
        return QInputDialog.Accepted

    monkeypatch.setattr(QInputDialog, "exec_", fake_exec)
    text, ok = dialogs.ask_text(None, "Создать счётчик", "Название")
    assert (text, ok) == ("doc", True)
    assert seen == {"ok": "ОК", "cancel": "Отмена"}


def test_ask_text_cancelled_returns_empty(qapp, monkeypatch):
    monkeypatch.setattr(QInputDialog, "exec_", lambda self: QInputDialog.Rejected)
    assert dialogs.ask_text(None, "t", "l") == ("", False)
