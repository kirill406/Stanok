# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Field editor (027): one template field and, for table/counter fields, its counter.

OK writes the field and the counter's source, format, position and resume
into the live project. Cancel leaves the field as it was. Creating or
removing a counter is immediate, as it always was, and sets `changed`.
"""

from __future__ import annotations

import logging
from datetime import date

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from ..engine.resolve import COUNTER_WIDTHS, TODAY_PRESETS, format_today
from ..engine.schema import CounterDef, FieldDef, FieldSource, ProjectJSON
from ..services.storage import ProjectStore
from .dialogs import ask_text, ask_yes_no
from .source_data import SourceData
from .strings import STRINGS
from .table_picker import eye_icon, open_picker, picker_available
from .theme import set_button_role

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "constant": STRINGS.FLD_SRC_CONSTANT,
    "table": STRINGS.FLD_SRC_TABLE,
    "counter": STRINGS.FLD_SRC_COUNTER,
    "today": STRINGS.FLD_SRC_TODAY,
}
SOURCE_ORDER = ("constant", "table", "counter", "today")
MAX_VALUE = 1_000_000_000


class _FieldError(Exception):
    """Blocks OK: a message from STRINGS, formatted with the field or counter name."""

    def __init__(self, key: str, name: str) -> None:
        super().__init__(f"{key}: {name}")
        self.key = key
        self.name = name


def _clear(layout: QLayout) -> None:
    """Delete every widget of a layout, including nested layouts."""
    while layout.count():
        item = layout.takeAt(0)
        if item.layout() is not None:
            _clear(item.layout())
        if item.widget() is not None:
            item.widget().hide()
            item.widget().deleteLater()


class FieldEditDialog(QDialog):
    """Edit the source of one field and the counter it reads (OK applies)."""

    def __init__(
        self,
        pj: ProjectJSON,
        template_name: str,
        field_name: str,
        sources: SourceData,
        store: ProjectStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pj = pj
        self._template_name = template_name
        self._field = field_name
        self._sources = sources
        self._store = store
        self._saved: FieldDef | None = pj.templates[template_name].fields.get(field_name)
        # Shared counters cannot change while this modal dialog is open.
        self._shared_defs = store.global_counters()
        self.changed = False
        self.type_combo: QComboBox | None = None
        self._forget_widgets()
        self._build_ui()

    # -- construction -----------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.FLD_EDIT_TITLE.format(name=self._field))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        title = QLabel(STRINGS.FLD_EDIT_TITLE.format(name=self._field), self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        head = QFormLayout()
        self.type_combo = QComboBox(self)
        for key in SOURCE_ORDER:
            self.type_combo.addItem(SOURCE_LABELS[key], key)
        head.addRow(STRINGS.FLD_EDIT_TYPE, self.type_combo)
        layout.addLayout(head)
        self._body = QVBoxLayout()
        self._body.setSpacing(10)
        layout.addLayout(self._body)

        kind = self._saved.source.value if self._saved else "constant"
        self.type_combo.setCurrentIndex(SOURCE_ORDER.index(kind))
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._build_body(kind)

        buttons = QDialogButtonBox(self)
        ok_btn = buttons.addButton(STRINGS.BTN_OK, QDialogButtonBox.AcceptRole)
        set_button_role(ok_btn, "primary")
        cancel_btn = buttons.addButton(STRINGS.CRT_CANCEL, QDialogButtonBox.RejectRole)
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _forget_widgets(self) -> None:
        """Drop every reference to the widgets of the previous value editor."""
        self._counter_combo = self._column_combo = self._preview = None
        self._const_edit = self._date_combo = self._block = None
        self._blk_head = self._blk_src = self._blk_fmt = self._blk_pos = None
        self._blk_resume = self._blk_pick = self._blk_remove = self._blk_note = None

    def _build_body(self, kind: str) -> None:
        """Rebuild the value editor for `kind`; the saved value shows if the type is unchanged."""
        _clear(self._body)
        self._forget_widgets()
        initial = self._saved if self._saved and self._saved.source.value == kind else None
        form = QFormLayout()
        form.setSpacing(8)
        self._body.addLayout(form)
        if kind == "constant":
            self._const_edit = QLineEdit(
                str(initial.value) if initial and initial.value is not None else "",
                self,
            )
            form.addRow(STRINGS.FLD_EDIT_VALUE, self._const_edit)
        elif kind == "today":
            self._build_today(form, initial)
        else:
            # Order matters: the column list reads the counter block's source.
            self._build_counter_row(form, kind, initial)
            self._build_counter_block()
            self._load_block(self._selected())
            self._column_row(form, kind, initial)
            self._refresh_preview()

    def _build_today(self, form: QFormLayout, initial: FieldDef | None) -> None:
        self._date_combo = QComboBox(self)
        if initial is not None and initial.value is None:
            self._date_combo.addItem(STRINGS.FLD_DATE_KEEP, None)
        today = date.today()
        for key in TODAY_PRESETS:
            self._date_combo.addItem(str(format_today(key, today)), key)
        if initial is not None and initial.value in TODAY_PRESETS:
            self._date_combo.setCurrentIndex(self._date_combo.findData(initial.value))
        self._date_combo.currentIndexChanged.connect(lambda _i=0: self._refresh_preview())
        form.addRow(STRINGS.FLD_EDIT_FORMAT, self._date_combo)
        self._preview = QLabel(self)
        form.addRow(STRINGS.FLD_EDIT_RESULT, self._preview)

    def _build_counter_row(self, form: QFormLayout, kind: str, initial: FieldDef | None) -> None:
        """Counter combo with a button that creates a new project counter."""
        row = QHBoxLayout()
        self._counter_combo = QComboBox(self)
        self._counter_combo.currentIndexChanged.connect(lambda _i=0: self._on_counter_changed())
        row.addWidget(self._counter_combo, 1)
        add_btn = QPushButton(STRINGS.FLD_COUNTER_CREATE, self)
        add_btn.clicked.connect(self._on_create_counter)
        row.addWidget(add_btn)
        form.addRow(STRINGS.FLD_EDIT_COUNTER, row)
        self._fill_counters(kind, initial)

    def _fill_counters(self, kind: str, initial: FieldDef | None, select: str | None = None) -> None:
        """Project counters first; shared ones follow, tagged; clashing names are disabled."""
        combo = self._counter_combo
        shared = self._shared()
        wanted = select
        if wanted is None and initial is not None:
            wanted = initial.counter_name if kind == "table" else initial.value
        combo.blockSignals(True)
        combo.clear()
        for cname in self._pj.counters:
            combo.addItem(cname, cname)
        for cname in shared:
            if cname in self._pj.counters:
                combo.addItem(f"{cname} ({STRINGS.GCNT_CLASH_TAG})", cname)
                combo.model().item(combo.count() - 1).setEnabled(False)
            elif kind != "table":  # a table field reads only project counters (021)
                combo.addItem(f"{cname} ({STRINGS.GCNT_SHARED_TAG})", cname)
        if wanted and combo.findData(wanted) < 0:
            combo.addItem(str(wanted), wanted)  # stale name: keep it visible
        index = combo.findData(wanted) if wanted else -1
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _column_row(self, form: QFormLayout, kind: str, initial: FieldDef | None) -> None:
        if kind == "table":
            self._column_combo = QComboBox(self)
            self._column_combo.currentIndexChanged.connect(lambda _i=0: self._refresh_preview())
            form.addRow(STRINGS.FLD_EDIT_COLUMN, self._column_combo)
            self._refill_columns(initial.value if initial else None)
        self._preview = QLabel(self)
        form.addRow(STRINGS.FLD_EDIT_RESULT, self._preview)

    def _build_counter_block(self) -> None:
        """Position, format, source and resume of the selected counter."""
        block = QFrame(self)
        block.setObjectName("counterBlock")
        box = QVBoxLayout(block)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(8)
        head = QLabel(self)
        head.setObjectName("sectionTitle")
        box.addWidget(head)
        self._blk_head = head
        form = QFormLayout()
        form.setSpacing(8)

        self._blk_src = QComboBox(block)
        self._blk_src.setToolTip(STRINGS.FLD_CNT_SOURCE_TIP)
        self._blk_src.addItem(STRINGS.FLD_NONE, None)
        for ds in self._pj.data_sources:
            self._blk_src.addItem(ds.file, ds.file)
        self._blk_src.currentIndexChanged.connect(lambda _i=0: self._on_block_source_changed())
        form.addRow(STRINGS.FLD_CNT_SOURCE, self._blk_src)

        self._blk_fmt = QComboBox(block)
        self._blk_fmt.setToolTip(STRINGS.FLD_CNT_FORMAT_TIP)
        for width in COUNTER_WIDTHS:
            self._blk_fmt.addItem(width, width)
        self._blk_fmt.currentIndexChanged.connect(lambda _i=0: self._refresh_preview())
        form.addRow(STRINGS.FLD_CNT_FORMAT, self._blk_fmt)

        pos_row = QHBoxLayout()
        self._blk_pos = QLineEdit(block)
        self._blk_pos.setToolTip(STRINGS.FLD_POS_TIP)
        self._blk_pos.textChanged.connect(lambda _t="": self._refresh_preview())
        pos_row.addWidget(self._blk_pos, 1)
        self._blk_pick = QToolButton(block)
        self._blk_pick.setIcon(eye_icon())
        self._blk_pick.setAutoRaise(True)
        self._blk_pick.setCursor(Qt.PointingHandCursor)
        self._blk_pick.setAccessibleName(STRINGS.FLD_PICK_DATA)
        self._blk_pick.clicked.connect(lambda _c=False: self._on_pick())
        pos_row.addWidget(self._blk_pick)
        form.addRow(STRINGS.FLD_CNT_POS, pos_row)

        self._blk_resume = QCheckBox(block)
        self._blk_resume.setToolTip(STRINGS.FLD_CNT_RESUME_TIP)
        form.addRow(STRINGS.FLD_CNT_RESUME, self._blk_resume)
        box.addLayout(form)

        self._blk_note = QLabel(STRINGS.FLD_SHARED_NOTE, block)
        self._blk_note.setObjectName("muted")
        self._blk_note.setWordWrap(True)
        box.addWidget(self._blk_note)

        self._blk_remove = QPushButton(STRINGS.FLD_CNT_REMOVE, block)
        self._blk_remove.setToolTip(STRINGS.FLD_CNT_REMOVE_TIP)
        self._blk_remove.clicked.connect(lambda _c=False: self._on_remove_counter())
        box.addWidget(self._blk_remove, 0, Qt.AlignLeft)
        self._block = block
        self._body.addWidget(block)

    # -- counter state ----------------------------------------------------------
    def _shared(self) -> dict[str, CounterDef]:
        return self._shared_defs

    def _selected(self) -> str | None:
        return self._counter_combo.currentData() if self._counter_combo else None

    def _is_project(self, cname: str | None) -> bool:
        return cname is not None and cname in self._pj.counters

    def _mode_of(self, table: str | None) -> str | None:
        if not table:
            return None
        for ds in self._pj.data_sources:
            if ds.file == table:
                return ds.mode
        return None

    def _load_block(self, cname: str | None) -> None:
        """Show the counter's own values; a shared counter is read-only here."""
        if self._block is None:
            return
        project = self._is_project(cname)
        cdef = self._pj.counters.get(cname) if project else self._shared().get(cname or "")
        self._blk_head.setText(
            STRINGS.FLD_EDIT_COUNTER_BLOCK.format(name=cname or STRINGS.FLD_NONE)
        )
        self._blk_src.setVisible(project)
        self._blk_fmt.setVisible(project)
        self._blk_pos.setVisible(project or cdef is not None)
        self._blk_pos.setReadOnly(not project)  # a shared position is edited in window 1
        self._blk_pick.setVisible(project)
        self._blk_resume.setVisible(project)
        self._blk_remove.setVisible(project)
        self._blk_note.setVisible(cdef is not None and not project)
        if cdef is None:
            self._blk_pos.setText("")
            return
        self._blk_src.blockSignals(True)
        self._blk_src.setCurrentIndex(max(0, self._blk_src.findData(cdef.table)))
        self._blk_src.blockSignals(False)
        self._blk_fmt.blockSignals(True)
        if self._blk_fmt.findData(cdef.format) < 0:
            self._blk_fmt.addItem(cdef.format, cdef.format)
        self._blk_fmt.setCurrentIndex(self._blk_fmt.findData(cdef.format))
        self._blk_fmt.blockSignals(False)
        self._blk_pos.setText(str(cdef.pos))
        self._blk_resume.setChecked(not bool(cdef.resume))
        self._refresh_block_state()

    def _refresh_block_state(self) -> None:
        """Constant sources keep their position; the picker needs a bound table."""
        cname = self._selected()
        if self._block is None or not self._is_project(cname):
            return
        table = self._blk_src.currentData()
        constant = self._mode_of(table) == "constant"
        self._blk_pos.setReadOnly(constant)
        self._blk_pos.setToolTip(STRINGS.FLD_POS_CONST_TIP if constant else STRINGS.FLD_POS_TIP)
        bound = table is not None and not constant
        self._blk_resume.setEnabled(bound)
        self._blk_resume.setToolTip(STRINGS.FLD_CNT_RESUME_TIP if bound else STRINGS.FLD_CNT_RESUME_NA_TIP)
        # Only a numeric counter can go: a bound one is removed with its source.
        self._blk_remove.setEnabled(table is None)
        self._blk_remove.setToolTip(STRINGS.FLD_CNT_REMOVE_TIP if table is None else STRINGS.FLD_CNT_REMOVE_BOUND)
        self._blk_pick.setEnabled(table is not None and picker_available())
        if table is None:
            self._blk_pick.setToolTip(STRINGS.FLD_PICK_NO_SOURCE_TIP)
        elif not picker_available():
            self._blk_pick.setToolTip(STRINGS.FLD_PICK_DISABLED_TIP)
        else:
            self._blk_pick.setToolTip(STRINGS.FLD_PICK_TIP)

    def _on_block_source_changed(self) -> None:
        self._refresh_block_state()
        self._refill_columns(self._column_combo.currentText() if self._column_combo else None)
        self._refresh_preview()

    def _on_counter_changed(self) -> None:
        cname = self._selected()
        self._load_block(cname)
        if self._column_combo is not None:
            self._refill_columns(None)
        self._refresh_preview()

    def _refill_columns(self, select: str | None) -> None:
        """Columns of the counter's source; None (no source) lists every header."""
        if self._column_combo is None:
            return
        table = self._blk_src.currentData() if self._block is not None else None
        headers = self._sources.headers(table)
        self._column_combo.blockSignals(True)
        self._column_combo.clear()
        self._column_combo.addItems(headers)
        if select is not None and select in headers:
            self._column_combo.setCurrentText(select)
        else:
            self._column_combo.setCurrentIndex(-1)
        self._column_combo.blockSignals(False)

    def _current_pos(self, cname: str | None) -> int | None:
        if cname is None:
            return None
        if self._is_project(cname) and self._blk_pos is not None and cname == self._selected():
            try:
                return int(self._blk_pos.text())
            except ValueError:
                return None
        cdef = self._pj.counters.get(cname) or self._shared().get(cname)
        return cdef.pos if cdef is not None else None

    def _row_index(self, cname: str | None) -> tuple[list[dict], int | None]:
        """Rows of the counter's source and the row its position points at."""
        table = self._blk_src.currentData() if self._block is not None else None
        rows = self._sources.rows(table)
        pos = self._current_pos(cname)
        if table is None or pos is None or pos < 0 or not rows:
            return rows, None
        mode = self._mode_of(table) or "sequential"
        idx = pos % len(rows) if mode == "circular" else pos
        return rows, idx if 0 <= idx < len(rows) else None

    def _refresh_preview(self) -> None:
        if self._preview is None:
            return
        kind = self.type_combo.currentData()
        if kind == "today":
            value = format_today(self._date_combo.currentData(), date.today())
            self._preview.setText(str(value))
        elif kind == "counter":
            pos = self._current_pos(self._selected())
            width = self._width_of(self._selected())
            self._preview.setText("" if pos is None or pos < 0 else str(pos).zfill(len(width)))
        elif kind == "table":
            rows, idx = self._row_index(self._selected())
            row = rows[idx] if idx is not None else {}
            column = self._column_combo.currentText()
            if row and any(v not in (None, "") for v in row.values()):
                key = column if column in row else next(iter(row))
                self._preview.setText(str(row[key]))
            else:
                self._preview.setText("")

    def _width_of(self, cname: str | None) -> str:
        if self._block is not None and self._is_project(cname) and cname == self._selected():
            return self._blk_fmt.currentData() or "1"
        cdef = self._pj.counters.get(cname) or self._shared().get(cname or "")
        return cdef.format if cdef is not None else "1"

    # -- slots ------------------------------------------------------------------
    def _on_type_changed(self, _index: int = 0) -> None:
        kind = self.type_combo.currentData()
        logger.debug(f"field {self._field}: type changed to {kind}")
        self._build_body(kind)

    def _on_create_counter(self) -> None:
        text, ok = ask_text(self, STRINGS.FLD_COUNTER_CREATE, STRINGS.FLD_COUNTER_NAME)
        cname = text.strip()
        if not ok or not cname:
            return
        if cname in self._pj.counters or cname in self._shared():
            QMessageBox.warning(
                self, STRINGS.MAIN_ERROR_TITLE, STRINGS.FLD_DUP_COUNTER.format(name=cname)
            )
            return
        logger.debug(f"counter created: {cname} in {self._template_name}")
        self._pj.counters[cname] = CounterDef()
        self.changed = True
        self._fill_counters(self.type_combo.currentData(), None, select=cname)
        self._on_counter_changed()

    def _on_remove_counter(self) -> None:
        cname = self._selected()
        if not self._is_project(cname):
            return
        if self._pj.counters[cname].table is not None:
            QMessageBox.information(self, STRINGS.FLD_CNT_REMOVE, STRINGS.FLD_CNT_REMOVE_BOUND)
            return
        users = self._users(cname)
        if users:
            QMessageBox.information(
                self,
                STRINGS.FLD_CNT_REMOVE,
                STRINGS.FLD_CNT_REMOVE_USED.format(name=cname, fields=", ".join(users)),
            )
            return
        if not ask_yes_no(self, STRINGS.FLD_CNT_REMOVE, STRINGS.FLD_CNT_REMOVE_ASK.format(name=cname)):
            return
        logger.debug(f"counter removed: {cname} in {self._template_name}")
        del self._pj.counters[cname]
        self.changed = True
        self._fill_counters(self.type_combo.currentData(), None)
        self._on_counter_changed()

    def _users(self, cname: str) -> list[str]:
        """Saved fields of any template that read counter `cname`, this field included."""
        users: list[str] = []
        for tname, tdef in self._pj.templates.items():
            for fname, fdef in tdef.fields.items():
                if (fdef.source == FieldSource.TABLE and fdef.counter_name == cname) or (
                    fdef.source == FieldSource.COUNTER and fdef.value == cname
                ):
                    users.append(f"{tname}: {fname}")
        return users

    def _on_pick(self) -> None:
        cname = self._selected()
        table = self._blk_src.currentData()
        if table is None:
            return
        value = open_picker(self, self._sources.folder, table, self._current_pos(cname))
        if value is not None:
            self._blk_pos.setText(str(value))

    def _on_ok(self) -> None:
        try:
            field, counter = self._collect()
        except _FieldError as e:
            logger.warning(f"field edit blocked: {e.key} {e.name}")
            QMessageBox.warning(
                self, STRINGS.MAIN_ERROR_TITLE, getattr(STRINGS, e.key).format(name=e.name)
            )
            return
        before = self._pj.model_dump(mode="json")
        self._apply(field, counter)
        if self._pj.model_dump(mode="json") != before:
            self.changed = True
        logger.debug(f"field {self._field} set to {field.source.value} in {self._template_name}")
        self.accept()

    # -- collect and apply ------------------------------------------------------
    def _collect(self) -> tuple[FieldDef, tuple[str, dict] | None]:
        """Validated field and, for a project counter, the counter's new values."""
        kind = self.type_combo.currentData()
        counter = None
        if kind == "constant":
            field = FieldDef(source=FieldSource.CONSTANT, value=self._const_edit.text())
        elif kind == "today":
            value = self._date_combo.currentData()
            if value is None:
                raise _FieldError("FLD_EMPTY_VALUE", self._field)
            field = FieldDef(source=FieldSource.TODAY, value=value)
        else:
            cname = self._selected()
            if cname is None:
                raise _FieldError("FLD_NO_COUNTER", self._field)
            if kind == "table":
                column = self._column_combo.currentText()
                if not column:
                    raise _FieldError("FLD_EMPTY_VALUE", self._field)
                field = FieldDef(source=FieldSource.TABLE, value=column, counter_name=cname)
            else:
                field = FieldDef(source=FieldSource.COUNTER, value=cname)
            if self._is_project(cname):
                counter = (cname, self._counter_values(cname))
        return field, counter

    def _counter_values(self, cname: str) -> dict:
        try:
            pos = int(self._blk_pos.text())
        except ValueError:
            raise _FieldError("FLD_CNT_POS_BAD", cname) from None
        if pos < 0:
            raise _FieldError("FLD_CNT_POS_BAD", cname)
        return {
            "table": self._blk_src.currentData(),
            "format": self._blk_fmt.currentData() or "1",
            "pos": pos,
            "resume": 0 if self._blk_resume.isChecked() else 1,
        }

    def _apply(self, field: FieldDef, counter: tuple[str, dict] | None) -> None:
        self._pj.templates[self._template_name].fields[self._field] = field
        if counter is None:
            return
        cname, values = counter
        cdef = self._pj.counters[cname]
        cdef.table = values["table"]
        cdef.format = values["format"]
        cdef.pos = values["pos"]
        cdef.resume = values["resume"]
