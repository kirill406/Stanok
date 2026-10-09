# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 3: edit template constant fields, persist to PJ on Save."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.storage import ProjectStore
from ..tables.excel import ExcelReader
from .strings import STRINGS

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "constant": STRINGS.FLD_SRC_CONSTANT,
    "table": STRINGS.FLD_SRC_TABLE,
    "counter": STRINGS.FLD_SRC_COUNTER,
    "today": STRINGS.FLD_SRC_TODAY,
}


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
        self._editors: dict[str, QLineEdit] = {}
        pj, config_path = self._store.resolve_project(project_ref)
        self._pj = pj
        self._config_name = config_path.stem
        self._template_def = pj.templates[template_name]
        self._preview_row = self._read_first_row(pj)
        self._build_ui()

    # -- data -----------------------------------------------------------------
    def _read_first_row(self, pj) -> dict:
        """First data row for previews; empty dict when unreadable."""
        ref_path = Path(self._project_ref)
        if not (ref_path.exists() and ref_path.is_dir()):
            return {}
        if not pj.data_sources:
            return {}
        try:
            rows = ExcelReader().read(ref_path / pj.data_sources[0].file)
            return next((r for r in rows if any(v not in (None, "") for v in r.values())), {})
        except Exception as e:
            logger.warning(f"preview row for {self._project_ref}: {e}", exc_info=True)
            return {}

    def _preview_text(self, field_name: str, field_def) -> str:
        source = str(field_def.source.value if hasattr(field_def.source, "value") else field_def.source)
        if source == "constant":
            return str(field_def.value)
        if source == "table":
            column = str(field_def.value)
            value = self._preview_row.get(column, "")
            return f"{column} → {value}" if value != "" else column
        if source == "counter":
            last = self._pj.counters.get(str(field_def.value))
            return STRINGS.FLD_PREVIEW_COUNTER.format(
                name=field_def.value, last=last.last if last else 0
            )
        if source == "today":
            return STRINGS.FLD_PREVIEW_TODAY.format(today=date.today().isoformat())
        return str(field_def.value)

    # -- UI construction --------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.FLD_TITLE.format(name=self._template_name))
        layout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            [STRINGS.FLD_COL_FIELD, STRINGS.FLD_COL_SOURCE, STRINGS.FLD_COL_VALUE]
        )
        fields = list(self._template_def.fields.items())
        self.table.setRowCount(len(fields))
        for row, (name, fdef) in enumerate(fields):
            source = str(fdef.source.value if hasattr(fdef.source, "value") else fdef.source)
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            source_item = QTableWidgetItem(SOURCE_LABELS.get(source, source))
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, source_item)
            if source == "constant":
                editor = QLineEdit(str(fdef.value), self.table)
                editor.textChanged.connect(self._mark_dirty)
                self.table.setCellWidget(row, 2, editor)
                self._editors[name] = editor
            else:
                preview = QTableWidgetItem(self._preview_text(name, fdef))
                preview.setFlags(preview.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 2, preview)
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

    # -- save + dirty check -------------------------------------------------------
    def _mark_dirty(self) -> None:
        self._dirty = True

    def _on_save(self) -> None:
        try:
            self._save()
        except Exception as e:
            logger.error(f"save fields {self._template_name}: {e}", exc_info=True)
            QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, str(e))

    def _save(self) -> None:
        for name, editor in self._editors.items():
            self._pj.templates[self._template_name].fields[name].value = editor.text()
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
            except Exception as e:
                logger.error(f"save fields {self._template_name}: {e}", exc_info=True)
                QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, str(e))
                return
            super().accept()
        elif answer == QMessageBox.Discard:
            super().reject()
        # Cancel: stay open
