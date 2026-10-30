# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 1 tool: shared counters for all projects (026)."""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..engine.resolve import COUNTER_WIDTHS
from ..services.storage import ProjectStore, StorageError
from .dialogs import ask_text, ask_yes_no
from .strings import STRINGS
from .theme import set_button_role

logger = logging.getLogger(__name__)

MAX_VALUE = 1_000_000_000


class AddSharedCounterDialog(QDialog):
    """Name, format and start value of a new shared counter."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(STRINGS.GCNT_ADD_TITLE)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)
        layout.addWidget(QLabel(STRINGS.GCNT_NAME, self))
        self.name_edit = QLineEdit(self)
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel(STRINGS.GCNT_FORMAT, self))
        self.format_combo = QComboBox(self)
        for width in COUNTER_WIDTHS:
            self.format_combo.addItem(width, width)
        layout.addWidget(self.format_combo)
        layout.addWidget(QLabel(STRINGS.GCNT_START, self))
        self.start_spin = QSpinBox(self)
        self.start_spin.setRange(0, MAX_VALUE)
        layout.addWidget(self.start_spin)

        buttons = QDialogButtonBox(self)
        ok_btn = buttons.addButton(STRINGS.BTN_OK, QDialogButtonBox.AcceptRole)
        set_button_role(ok_btn, "primary")
        cancel_btn = buttons.addButton(STRINGS.CRT_CANCEL, QDialogButtonBox.RejectRole)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def name(self) -> str:
        return self.name_edit.text()

    def fmt(self) -> str:
        return self.format_combo.currentData()

    def start(self) -> int:
        return self.start_spin.value()


class GlobalCountersDialog(QDialog):
    """Create, set and remove shared counters; projects reference them by name."""

    def __init__(self, store: ProjectStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self.setWindowTitle(STRINGS.GCNT_TITLE)
        self.setMinimumWidth(680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(9)

        title = QLabel(STRINGS.GCNT_TITLE, self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        hint = QLabel(STRINGS.GCNT_HINT, self)
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [
                STRINGS.GCNT_COL_NAME,
                STRINGS.GCNT_COL_FORMAT,
                STRINGS.GCNT_COL_VALUE,
                STRINGS.GCNT_COL_USERS,
                "",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._on_name_double_clicked)
        header = self.table.horizontalHeader()
        # Fixed widths for the controls: a spin box or button wider than its
        # column pushes the row out of line, so only the text columns stretch.
        self.table.verticalHeader().setDefaultSectionSize(48)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        for col, width in ((1, 90), (2, 190), (4, 120)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            header.resizeSection(col, width)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        add_btn = QPushButton(STRINGS.GCNT_ADD, self)
        add_btn.clicked.connect(self._on_add)
        buttons.addWidget(add_btn)
        close_btn = QPushButton(STRINGS.START_CLOSE, self)
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)
        self._reload()

    def _reload(self) -> None:
        counters = self._store.global_counters()
        self.table.setRowCount(len(counters))
        for row, name in enumerate(sorted(counters)):
            cdef = counters[name]
            self._set_text(row, 0, name)
            self._set_text(row, 1, cdef.format)
            spin = QSpinBox(self.table)
            spin.setFixedWidth(140)
            spin.setRange(0, MAX_VALUE)
            spin.setValue(cdef.pos)
            spin.editingFinished.connect(
                lambda n=name, s=spin: self._on_value_changed(n, s.value())
            )
            self.table.setCellWidget(row, 2, self._centered(spin))
            users = self._store.global_counter_users(name)
            self._set_text(row, 3, ", ".join(users) or STRINGS.GCNT_NO_USERS)
            remove_btn = QPushButton(STRINGS.GCNT_REMOVE, self.table)
            remove_btn.clicked.connect(lambda _checked=False, n=name: self._on_remove(n))
            self.table.setCellWidget(row, 4, self._centered(remove_btn))

    def _on_name_double_clicked(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        old = item.text()
        text, ok = ask_text(self, STRINGS.GCNT_RENAME, STRINGS.GCNT_NAME, text=old)
        if not ok or text.strip() == old:
            return
        try:
            self._store.rename_global_counter(old, text)
        except StorageError as e:
            self._warn(e)
            return
        QTimer.singleShot(0, self._reload)  # rebuild after the click has finished

    def _centered(self, widget: QWidget) -> QWidget:
        """Wrap a control so it sits in the middle of its cell with a small margin."""
        box = QWidget(self.table)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(widget)
        return box

    def _set_text(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _warn(self, error: StorageError) -> None:
        logger.warning(f"shared counter: {error}", exc_info=True)
        QMessageBox.warning(self, STRINGS.GCNT_TITLE, str(error))

    def _on_add(self) -> None:
        dialog = AddSharedCounterDialog(self)
        if not dialog.exec_():
            return
        try:
            self._store.add_global_counter(dialog.name(), dialog.fmt(), dialog.start())
        except StorageError as e:
            self._warn(e)
            return
        self._reload()

    def _on_value_changed(self, name: str, value: int) -> None:
        # Rebuilding here would delete the spin box that sent editingFinished,
        # so a failed write defers the rebuild to the next event-loop turn.
        current = self._store.global_counters().get(name)
        if current is None or current.pos == value:
            return
        try:
            self._store.set_global_counter_pos(name, value)
        except StorageError as e:
            self._warn(e)
            QTimer.singleShot(0, self._reload)

    def _on_remove(self, name: str) -> None:
        if not ask_yes_no(
            self, STRINGS.GCNT_TITLE, STRINGS.GCNT_REMOVE_ASK.format(name=name)
        ):
            return
        try:
            self._store.remove_global_counter(name)
        except StorageError as e:
            self._warn(e)
            return
        QTimer.singleShot(0, self._reload)  # the remove button is the sender
