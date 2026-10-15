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
COUNTER_FORMATS = (("plain", STRINGS.FLD_FMT_PLAIN), ("month", STRINGS.FLD_FMT_MONTH))


class _FieldError(Exception):
    """Save-blocking validation error naming the field."""

    def __init__(self, field: str):
        super().__init__(field)
        self.field = field


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
        self._headers_cache: dict[str | None, list[str]] = {}
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
    def _read_headers(self, source_file: str | None) -> list[str]:
        """Column headers for one source (None = union of all); [] + warning on failure."""
        if source_file in self._headers_cache:
            return self._headers_cache[source_file]
        ref_path = Path(self._project_ref)
        files = (
            [source_file]
            if source_file
            else [ds.file for ds in self._pj.data_sources]
        )
        headers: list[str] = []
        if ref_path.exists() and ref_path.is_dir():
            for f in files:
                try:
                    rows = ExcelReader().read(ref_path / f)
                except Exception as e:
                    logger.warning(f"headers for {f} failed: {e}", exc_info=True)
                    if f not in self._headers_warned:
                        self._headers_warned.add(f)
                        QMessageBox.warning(
                            self, STRINGS.MAIN_ERROR_TITLE, f"{f}: {e}"
                        )
                    continue
                for r in rows:
                    for h in r.keys():
                        if h not in headers:
                            headers.append(h)
        self._headers_cache[source_file] = headers
        return headers

    # -- UI construction --------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.FLD_TITLE.format(name=self._template_name))
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            [STRINGS.FLD_COL_FIELD, STRINGS.FLD_COL_SOURCE, STRINGS.FLD_COL_VALUE]
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
        self.save_btn.clicked.connect(self._on_save)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        close_btn.clicked.connect(self.reject)
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
        for key in ("const", "file", "col", "counter", "fmt", "preview"):
            st.pop(key, None)
        if kind == "constant":
            editor = QLineEdit(
                f"{{{{{name}}}}}" if fdef is None else str(stored.value), box
            )
            editor.textChanged.connect(self._mark_dirty)
            layout.addWidget(editor)
            st["const"] = editor
        elif kind == "table":
            file_combo = QComboBox(box)
            file_combo.addItem(STRINGS.FLD_TABLE_ANY, None)
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
            self._refill_columns(name, select=stored.value)
        elif kind == "counter":
            editor = QLineEdit(str(stored.value or ""), box)
            editor.textChanged.connect(self._mark_dirty)
            layout.addWidget(editor)
            st["counter"] = editor
            fmt_combo = QComboBox(box)
            for value, label in COUNTER_FORMATS:
                fmt_combo.addItem(label, value)
            current = self._pj.counters.get(str(stored.value or ""))
            fmt_combo.setCurrentIndex(
                1
                if current is not None and current.format == "month"
                else 0
            )
            fmt_combo.currentIndexChanged.connect(self._mark_dirty)
            layout.addWidget(fmt_combo)
            st["fmt"] = fmt_combo
        else:  # today: readonly preview
            preview = QLabel(
                STRINGS.FLD_PREVIEW_TODAY.format(today=date.today().isoformat()),
                box,
            )
            layout.addWidget(preview)
            st["preview"] = preview
        self.table.setCellWidget(row, 2, box)
        st["box"] = box

    def _on_type_changed(self, name: str) -> None:
        row = list(self._rows).index(name)
        old = self.table.cellWidget(row, 2)
        self._build_value_cell(row, name, fdef=None)
        if old is not None:
            old.deleteLater()
        self._mark_dirty()

    def _on_table_file_changed(self, name: str) -> None:
        self._refill_columns(name, select=None)
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

    def _on_save(self) -> None:
        try:
            self._save()
        except _FieldError as e:
            logger.warning(f"save fields blocked: empty {e.field}", exc_info=True)
            QMessageBox.warning(
                self,
                STRINGS.MAIN_ERROR_TITLE,
                STRINGS.FLD_EMPTY_VALUE.format(name=e.field),
            )
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
                if not column:
                    raise _FieldError(name)
                f.source = FieldSource.TABLE
                f.value = column
                f.table = st["file"].currentData()
            elif kind == "counter":
                cname = st["counter"].text().strip()
                if not cname:
                    raise _FieldError(name)
                fmt = st["fmt"].currentData()
                existing = self._pj.counters.get(cname)
                if existing is None:
                    self._pj.counters[cname] = CounterDef(last=0, format=fmt)
                else:
                    existing.format = fmt
                f.source = FieldSource.COUNTER
                f.value = cname
                f.table = None
            else:
                f.source = FieldSource.TODAY
                f.value = None
                f.table = None
        self._store.save(self._pj, name=self._config_name)
        self._dirty = False
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
                logger.warning(f"save fields blocked: empty {e.field}")
                QMessageBox.warning(
                    self,
                    STRINGS.MAIN_ERROR_TITLE,
                    STRINGS.FLD_EMPTY_VALUE.format(name=e.field),
                )
                return
            except Exception as e:
                logger.error(f"save fields {self._template_name}: {e}", exc_info=True)
                QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, str(e))
                return
            super().accept()
        elif answer == QMessageBox.Discard:
            super().reject()
        # Cancel: stay open
