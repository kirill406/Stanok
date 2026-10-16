# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 3: edit template field sources and values, persist to PJ on Save."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.generate import TemplateError
from ..services.storage import ProjectStore
from ..engine.schema import CounterDef, FieldDef, FieldSource, ProjectJSON
from ..engine.resolve import TODAY_PRESETS, format_today
from ..tables.excel import ExcelReader
from .strings import STRINGS

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "constant": STRINGS.FLD_SRC_CONSTANT,
    "table": STRINGS.FLD_SRC_TABLE,
    "counter": STRINGS.FLD_SRC_COUNTER,
    "today": STRINGS.FLD_SRC_TODAY,
}
SOURCE_ORDER = ("constant", "table", "counter", "today")
COUNTER_WIDTHS = ("1", "01", "001", "0001")
DATE_PRESETS = (
    ("dmy", STRINGS.FLD_DATE_DMY),
    ("day", STRINGS.FLD_DATE_DAY),
    ("month_ru", STRINGS.FLD_DATE_MONTH),
    ("year", STRINGS.FLD_DATE_YEAR),
    ("ru_long", STRINGS.FLD_DATE_RU),
)
NEW_COUNTER_TAG = "__new__"


class _FieldError(Exception):
    """Save-blocking validation error: field + STRINGS message key."""

    def __init__(self, field: str, msg: str):
        super().__init__(f"{msg}: {field}")
        self.field = field
        self.msg = msg


class FieldsDialog(QDialog):
    """Modal field editor: constants editable, rest readonly with preview."""

    def __init__(
        self,
        project_ref: str,
        template_name: str,
        store: ProjectStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._project_ref = project_ref
        self._template_name = template_name
        self._dirty = False
        self._rows: dict[str, dict] = {}
        self._rows_cache: dict[str, list[dict]] = {}
        self._headers_warned: set[str] = set()
        pj, config_path = self._store.resolve_project(project_ref)
        self._pj = pj
        self._config_name = config_path.stem
        try:
            self._template_def = pj.templates[template_name]
        except KeyError:
            raise TemplateError(f"template not found: {template_name}") from None
        self._build_ui()

    # -- data -----------------------------------------------------------------
    def _read_table_rows(self, source_file: str | None) -> list[dict]:
        """Rows for one source (None = all sources concatenated); warns once."""
        key = source_file or "__all__"
        if key in self._rows_cache:
            return self._rows_cache[key]
        ref_path = Path(self._project_ref)
        files = (
            [source_file]
            if source_file
            else [ds.file for ds in self._pj.data_sources]
        )
        rows: list[dict] = []
        if ref_path.exists() and ref_path.is_dir():
            for f in files:
                try:
                    rows.extend(ExcelReader().read(ref_path / f))
                except Exception as e:
                    logger.warning(f"headers for {f} failed: {e}", exc_info=True)
                    if f not in self._headers_warned:
                        self._headers_warned.add(f)
                        QMessageBox.warning(
                            self, STRINGS.MAIN_ERROR_TITLE, f"{f}: {e}"
                        )
        self._rows_cache[key] = rows
        return rows

    def _read_headers(self, source_file: str | None) -> list[str]:
        """Column headers for one source (None = union of all)."""
        headers: list[str] = []
        for r in self._read_table_rows(source_file):
            for h in r.keys():
                if h not in headers:
                    headers.append(h)
        return headers

    def _first_row(self, source_file: str | None) -> dict:
        """First non-empty row for one source (None = all); {} when none."""
        return next(
            (
                r
                for r in self._read_table_rows(source_file)
                if any(v not in (None, "") for v in r.values())
            ),
            {},
        )

    # -- UI construction --------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.FLD_TITLE.format(name=self._template_name))
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                STRINGS.FLD_COL_FIELD,
                STRINGS.FLD_COL_SOURCE,
                STRINGS.FLD_COL_DATA,
                STRINGS.FLD_COL_VALUE,
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        fields = list(self._template_def.fields.items())
        self.table.setRowCount(len(fields))
        for row, (name, fdef) in enumerate(fields):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            type_combo = QComboBox(self.table)
            for key in SOURCE_ORDER:
                type_combo.addItem(SOURCE_LABELS[key], key)
            type_combo.setCurrentIndex(
                SOURCE_ORDER.index(fdef.source.value)
            )
            type_combo.blockSignals(True)
            self.table.setCellWidget(row, 1, type_combo)
            type_combo.blockSignals(False)
            type_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._on_type_changed(field)
            )
            self._rows[name] = {"type": type_combo}
            self._build_value_cell(row, name, fdef)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(self)
        self.save_btn = buttons.addButton(
            STRINGS.FLD_SAVE, QDialogButtonBox.ActionRole
        )
        self.save_btn.setStyleSheet("background-color: #2e7d32; color: black;")
        self.save_btn.clicked.connect(self._on_save)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        close_btn.setText(STRINGS.FLD_CLOSE)
        close_btn.clicked.connect(self.reject)
        # Hide AFTER all buttons are added: QDialogButtonBox unhides on add.
        self.save_btn.setVisible(False)
        layout.addWidget(buttons)
        layout.addWidget(QLabel(STRINGS.FLD_HINT, self))

    def _build_value_cell(
        self, row: int, name: str, fdef: FieldDef | None = None
    ) -> None:
        """(Re)build the value cell for the row's current source type."""
        st = self._rows[name]
        kind = st["type"].currentData()
        stored = fdef or self._template_def.fields[name]
        box = QWidget(self.table)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        for key in (
            "const", "file", "col", "clabel",
            "cname", "fmt", "last", "cprev",
            "dfmt", "dlabel", "preview", "result",
        ):
            st.pop(key, None)
        if kind == "constant":
            editor = QLineEdit(
                f"{{{{{name}}}}}" if fdef is None else str(stored.value), box
            )
            editor.textChanged.connect(self._mark_dirty)
            layout.addWidget(editor)
            st["const"] = editor
            result = QLabel(editor.text(), self.table)
            editor.textChanged.connect(result.setText)
            self.table.setCellWidget(row, 3, result)
            st["result"] = result
        elif kind == "table":
            file_combo = QComboBox(box)
            for ds in self._pj.data_sources:
                file_combo.addItem(ds.file, ds.file)
            wanted = stored.table if stored.source.value == "table" else None
            idx = file_combo.findData(wanted)
            file_combo.setCurrentIndex(idx if idx >= 0 else 0)
            file_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._on_table_file_changed(field)
            )
            layout.addWidget(file_combo)
            st["file"] = file_combo
            col_combo = QComboBox(box)
            layout.addWidget(col_combo)
            st["col"] = col_combo
            col_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._update_table_value(field)
            )
            col_combo.currentIndexChanged.connect(self._mark_dirty)
            clabel = QLabel(self.table)
            self.table.setCellWidget(row, 3, clabel)
            st["clabel"] = clabel
            self._refill_columns(name, select=stored.value)
            self._update_table_value(name)
        elif kind == "counter":
            name_combo = QComboBox(box)
            for cname in self._pj.counters:
                name_combo.addItem(cname, cname)
            name_combo.addItem(STRINGS.FLD_COUNTER_NEW, NEW_COUNTER_TAG)
            wanted = str(stored.value or "")
            idx = name_combo.findData(wanted)
            name_combo.setCurrentIndex(idx if idx >= 0 else 0)
            name_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._on_counter_name_changed(field)
            )
            layout.addWidget(name_combo)
            st["cname"] = name_combo
            fmt_combo = QComboBox(box)
            for width in COUNTER_WIDTHS:
                fmt_combo.addItem(width, width)
            for fmt in {c.format for c in self._pj.counters.values()}:
                if fmt not in COUNTER_WIDTHS:
                    fmt_combo.addItem(fmt, fmt)
            current = self._pj.counters.get(wanted)
            fmt_combo.setCurrentIndex(
                fmt_combo.findData(current.format if current else "1")
            )
            fmt_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._mark_row_touched(field)
            )
            layout.addWidget(fmt_combo)
            st["fmt"] = fmt_combo
            last_edit = QLineEdit(
                str(current.last if current else 0), box
            )
            last_edit.textChanged.connect(
                lambda _t="", field=name: self._mark_row_touched(field)
            )
            layout.addWidget(last_edit)
            st["last"] = last_edit
            cprev = QLabel(self.table)
            self.table.setCellWidget(row, 3, cprev)
            st["cprev"] = cprev
            self._update_counter_preview(name)
            last_edit.textChanged.connect(
                lambda _t="", field=name: self._update_counter_preview(field)
            )
            fmt_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._update_counter_preview(field)
            )
        else:  # today ("Дата"): format combo + preview
            dfmt = QComboBox(box)
            if stored.source.value == "today" and stored.value is None:
                dfmt.addItem(STRINGS.FLD_DATE_KEEP, None)
            for key, label in DATE_PRESETS:
                dfmt.addItem(label, key)
            if stored.source.value == "today" and stored.value in TODAY_PRESETS:
                dfmt.setCurrentIndex(dfmt.findData(stored.value))
            dfmt.currentIndexChanged.connect(
                lambda _i=0, field=name: self._update_today_preview(field)
            )
            dfmt.currentIndexChanged.connect(self._mark_dirty)
            layout.addWidget(dfmt)
            st["dfmt"] = dfmt
            dlabel = QLabel(self.table)
            self.table.setCellWidget(row, 3, dlabel)
            st["dlabel"] = dlabel
            self._update_today_preview(name)
        self.table.setCellWidget(row, 2, box)
        st["box"] = box

    def _selected_counter(self, name: str) -> str | None:
        data = self._rows[name]["cname"].currentData()
        return None if data == NEW_COUNTER_TAG else data

    def _on_counter_name_changed(self, name: str) -> None:
        st = self._rows[name]
        if st["cname"].currentData() != NEW_COUNTER_TAG:
            current = self._pj.counters.get(st["cname"].currentData())
            st["last"].blockSignals(True)
            st["last"].setText(str(current.last if current else 0))
            st["last"].blockSignals(False)
            if current is not None:
                st["fmt"].blockSignals(True)
                st["fmt"].setCurrentIndex(st["fmt"].findData(current.format))
                st["fmt"].blockSignals(False)
            self._update_counter_preview(name)
            self._mark_row_touched(name)
            return
        text, ok = QInputDialog.getText(
            self, STRINGS.FLD_NEW_COUNTER_TITLE, STRINGS.FLD_NEW_COUNTER_LABEL
        )
        cname = text.strip()
        combo = st["cname"]
        combo.blockSignals(True)
        if ok and cname and cname not in self._pj.counters:
            combo.insertItem(combo.count() - 1, cname, cname)
            combo.setCurrentIndex(combo.findData(cname))
            st["last"].setText("0")
            st["fmt"].setCurrentIndex(st["fmt"].findData("1"))
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
        self._update_counter_preview(name)
        self._mark_row_touched(name)

    def _update_counter_preview(self, name: str) -> None:
        st = self._rows[name]
        try:
            last = int(st["last"].text())
            width = st["fmt"].currentData() or "1"
            st["cprev"].setText(str(last).zfill(len(width)) if last >= 0 else "")
        except (ValueError, TypeError, AttributeError):
            st["cprev"].setText("")

    def _update_today_preview(self, name: str) -> None:
        st = self._rows[name]
        value = format_today(st["dfmt"].currentData(), date.today())
        st["dlabel"].setText(str(value))

    def _update_table_value(self, name: str) -> None:
        st = self._rows[name]
        row = self._first_row(st["file"].currentData())
        column = st["col"].currentText()
        if column and column in row:
            st["clabel"].setText(str(row[column]))
        elif row:
            first = next(iter(row))
            st["clabel"].setText(str(row[first]))
        else:
            st["clabel"].setText("")

    def _mark_row_touched(self, name: str) -> None:
        self._rows[name]["touched"] = True
        self._mark_dirty()

    def _on_type_changed(self, name: str) -> None:
        row = list(self._rows).index(name)
        old = self.table.cellWidget(row, 2)
        old_result = self.table.cellWidget(row, 3)
        self._build_value_cell(row, name, fdef=None)
        if old is not None:
            old.deleteLater()
        if old_result is not None:
            old_result.deleteLater()
        self._mark_row_touched(name)

    def _on_table_file_changed(self, name: str) -> None:
        self._refill_columns(name, select=None)
        self._update_table_value(name)
        self._mark_dirty()

    def _refill_columns(self, name: str, select: object = None) -> None:
        st = self._rows[name]
        headers = self._read_headers(st["file"].currentData())
        combo = st["col"]
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(headers)
        if select is not None and select in headers:
            combo.setCurrentText(str(select))
        else:
            combo.setCurrentIndex(-1)
        combo.blockSignals(False)

    # -- save + dirty check -------------------------------------------------------
    def _mark_dirty(self) -> None:
        self._dirty = True
        self.save_btn.setVisible(True)

    def _show_field_warning(self, e: _FieldError) -> None:
        logger.warning(f"save fields blocked: {e.msg} {e.field}")
        QMessageBox.warning(
            self,
            STRINGS.MAIN_ERROR_TITLE,
            getattr(STRINGS, e.msg).format(name=e.field),
        )

    def _on_save(self) -> None:
        try:
            self._save()
        except _FieldError as e:
            self._show_field_warning(e)
        except Exception as e:
            logger.error(f"save fields {self._template_name}: {e}", exc_info=True)
            QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, str(e))

    def _save(self) -> None:
        fields = self._pj.templates[self._template_name].fields
        for name, st in self._rows.items():
            f = fields[name]
            kind = st["type"].currentData()
            if kind == "constant":
                f.source = FieldSource.CONSTANT
                f.value = st["const"].text()
                f.table = None
            elif kind == "table":
                column = st["col"].currentText()
                source_file = st["file"].currentData()
                if not column or not source_file:
                    raise _FieldError(name, "FLD_EMPTY_VALUE")
                f.source = FieldSource.TABLE
                f.value = column
                f.table = source_file
            elif kind == "counter":
                cname = self._selected_counter(name)
                if cname is None:
                    raise _FieldError(name, "FLD_EMPTY_VALUE")
                try:
                    last = int(st["last"].text())
                except ValueError:
                    raise _FieldError(name, "FLD_BAD_VALUE") from None
                if last < 0:
                    raise _FieldError(name, "FLD_BAD_VALUE")
                fmt = st["fmt"].currentData() or "1"
                if st.get("touched"):
                    existing = self._pj.counters.get(cname)
                    if existing is None:
                        self._pj.counters[cname] = CounterDef(last=last, format=fmt)
                    else:
                        existing.format = fmt
                        existing.last = last
                f.source = FieldSource.COUNTER
                f.value = cname
                f.table = None
            else:
                value = st["dfmt"].currentData()
                if value is None:
                    raise _FieldError(name, "FLD_EMPTY_VALUE")
                f.source = FieldSource.TODAY
                f.value = value
                f.table = None
        self._store.save(self._pj, name=self._config_name)
        self._dirty = False
        self.save_btn.setVisible(False)
        logger.info(f"saved fields of {self._template_name} to {self._config_name}")

    def reject(self) -> None:
        if not self._dirty:
            super().reject()
            return
        answer = QMessageBox.question(
            self,
            STRINGS.MAIN_TITLE,
            STRINGS.FLD_DIRTY_ASK,
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if answer == QMessageBox.Save:
            try:
                self._save()
            except _FieldError as e:
                self._show_field_warning(e)
                return
            except Exception as e:
                logger.error(f"save fields {self._template_name}: {e}", exc_info=True)
                QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, str(e))
                return
            super().accept()
        elif answer == QMessageBox.Discard:
            super().reject()
        # Cancel: stay open
