# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 3 (027): the template page on full screen, fields as buttons.

A click on a field button opens FieldEditDialog. The project stays in
memory until Save; the window tracks edits through `dirty`.
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..engine.schema import FieldSource, validate_pj
from ..services.generate import TemplateError
from ..services.storage import ProjectStore, project_folder
from ..services.template_layout import Layout, TemplateLayoutError, load_template_layout
from .dialogs import ask_save_discard_cancel
from .field_editor import FieldEditDialog
from .source_data import SourceData
from .strings import STRINGS
from .template_sheet import FlowLayout, TemplateSheet
from .theme import set_button_role

logger = logging.getLogger(__name__)


class FieldsDialog(QDialog):
    """Template page with field buttons; saves the project on Save."""

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
        self._sheet: TemplateSheet | None = None
        self._layout_error = ""
        pj, config_path = self._store.resolve_project(project_ref)
        self._pj = pj
        self._config_name = config_path.stem
        self._folder = project_folder(project_ref, pj, config_path, self._store)
        try:
            self._template_def = pj.templates[template_name]
        except KeyError:
            raise TemplateError(f"template not found: {template_name}") from None
        self._sources = SourceData(pj, self._folder, self._store, self._config_name, self)
        self._layout = self._load_layout()
        self._build_ui()
        # Window 3 works on the whole screen: the page is long, the fields are many.
        self.setWindowState(self.windowState() | Qt.WindowMaximized)
        logger.debug(f"window 3 opened: {self._config_name}/{template_name}")

    # -- template ---------------------------------------------------------------
    def _load_layout(self) -> Layout | None:
        """The page model of the template file; a failure leaves the page empty."""
        path = self._folder / self._template_def.file
        if not path.is_file():
            self._layout_error = STRINGS.TPL_LOAD_FAILED.format(
                error=STRINGS.TPL_FILE_MISSING.format(file=self._template_def.file)
            )
            logger.warning(f"template file missing: {path}")
            return None
        try:
            return load_template_layout(path)
        except TemplateLayoutError as e:
            self._layout_error = STRINGS.TPL_LOAD_FAILED.format(error=e)
            return None

    def _field_names(self) -> list[str]:
        """Every name that can be edited: placeholders of the page, then the saved fields."""
        in_page = self._layout.placeholders() if self._layout is not None else []
        return list(dict.fromkeys([*in_page, *self._template_def.fields]))

    def _unused_names(self) -> list[str]:
        """Saved fields that the page does not show (still editable)."""
        if self._layout is None:
            return list(self._template_def.fields)
        in_page = set(self._layout.placeholders())
        return [name for name in self._template_def.fields if name not in in_page]

    def _is_configured(self, name: str) -> bool:
        return name in self._template_def.fields

    def _describe(self, name: str) -> str:
        """Tooltip of a field button: what the field reads now."""
        fdef = self._template_def.fields.get(name)
        if fdef is None:
            return STRINGS.FLD_DESC_UNSET
        if fdef.source == FieldSource.CONSTANT:
            return STRINGS.FLD_DESC_CONSTANT.format(value=fdef.value)
        if fdef.source == FieldSource.TABLE:
            return STRINGS.FLD_DESC_TABLE.format(column=fdef.value, counter=fdef.counter_name)
        if fdef.source == FieldSource.COUNTER:
            return STRINGS.FLD_DESC_COUNTER.format(counter=fdef.value)
        return STRINGS.FLD_DESC_TODAY.format(value=fdef.value or "")

    # -- UI ---------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.FLD_TITLE.format(name=self._template_name))
        self.resize(1000, 760)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(8)
        title = QLabel(STRINGS.FLD_TITLE.format(name=self._template_name), self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        fname_row = QHBoxLayout()
        fname_row.addWidget(QLabel(STRINGS.FLD_FNAME_TITLE, self))
        self.fname_edit = QLineEdit(self._pj.filename_template or "", self)
        self.fname_edit.textChanged.connect(self._mark_dirty)
        fname_row.addWidget(self.fname_edit, 1)
        self.fname_insert_btn = QPushButton(STRINGS.FLD_INSERT_FIELD, self)
        self.fname_insert_btn.clicked.connect(self._on_insert_field)
        fname_row.addWidget(self.fname_insert_btn)
        layout.addLayout(fname_row)

        if self._layout is not None:
            self._sheet = TemplateSheet(self._layout, self._describe, self._is_configured, self)
            self._sheet.fieldClicked.connect(self._open_field)
            layout.addWidget(self._sheet, 1)
        else:
            error = QLabel(self._layout_error, self)
            error.setObjectName("muted")
            error.setWordWrap(True)
            layout.addWidget(error)
            layout.addStretch(1)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, self._layout_error)

        self._unused = QWidget(self)
        self._unused_flow = FlowLayout(self._unused)
        self._unused_flow.setContentsMargins(0, 0, 0, 0)
        self._unused_title = QLabel(STRINGS.FLD_UNUSED_TITLE, self)
        self._unused_title.setObjectName("sectionTitle")
        layout.addWidget(self._unused_title)
        layout.addWidget(self._unused)
        self._refresh_unused()

        buttons = QDialogButtonBox(self)
        self.save_btn = buttons.addButton(STRINGS.FLD_SAVE, QDialogButtonBox.ActionRole)
        set_button_role(self.save_btn, "primary")
        self.save_btn.clicked.connect(self._on_save)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        close_btn.setText(STRINGS.FLD_CLOSE)
        close_btn.clicked.connect(self.reject)
        # Hide AFTER all buttons are added: QDialogButtonBox unhides on add.
        self.save_btn.setVisible(False)
        layout.addWidget(buttons)
        hint = QLabel(STRINGS.FLD_HINT, self)
        hint.setObjectName("muted")
        layout.addWidget(hint)

    def _refresh_unused(self) -> None:
        """Rebuild the buttons of fields that the page does not show."""
        names = self._unused_names()
        self._unused_title.setVisible(bool(names))
        self._unused.setVisible(bool(names))
        while self._unused_flow.count():
            item = self._unused_flow.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for name in names:
            button = QPushButton(name, self._unused)
            button.setObjectName("fieldButton")
            button.setToolTip(self._describe(name))
            button.setProperty("state", "set" if self._is_configured(name) else "unset")
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _c=False, n=name: self._open_field(n))
            self._unused_flow.addWidget(button)

    # -- slots ------------------------------------------------------------------
    def _open_field(self, name: str) -> None:
        """Edit one field; the window follows the change when the editor reports one."""
        logger.debug(f"field opened: {name} in {self._template_name}")
        dialog = FieldEditDialog(
            self._pj, self._template_name, name, self._sources, self._store, self
        )
        dialog.exec_()
        if not dialog.changed:
            return
        self._mark_dirty()
        if self._sheet is not None:
            self._sheet.refresh()
        self._refresh_unused()

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.save_btn.setVisible(True)

    def _on_insert_field(self) -> None:
        menu = QMenu(self)
        for field_name in self._field_names():
            menu.addAction(
                field_name,
                lambda _checked=False, name=field_name: self.fname_edit.insert(f"{{{name}}}"),
            )
        menu.addSeparator()
        for var in ("{i}", "{template}"):
            menu.addAction(
                var,
                lambda _checked=False, text=var: self.fname_edit.insert(text),
            )
        menu.exec_(self.fname_insert_btn.mapToGlobal(self.fname_insert_btn.rect().bottomLeft()))

    def _on_save(self) -> None:
        try:
            self._save()
        except Exception as e:
            logger.error(f"save fields {self._template_name}: {e}", exc_info=True)
            QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, str(e))

    def _save(self) -> None:
        fname = self.fname_edit.text().strip()
        if not fname:
            QMessageBox.warning(
                self,
                STRINGS.MAIN_ERROR_TITLE,
                STRINGS.FLD_EMPTY_VALUE.format(name=self._template_name),
            )
            return
        self._pj.filename_template = fname
        validate_pj(self._pj.model_dump(mode="json"))
        self._store.save(self._pj, name=self._config_name)
        self._dirty = False
        self.save_btn.setVisible(False)
        logger.info(f"saved fields of {self._template_name} to {self._config_name}")

    def reject(self) -> None:
        if not self._dirty:
            super().reject()
            return
        answer = ask_save_discard_cancel(self, STRINGS.MAIN_TITLE, STRINGS.FLD_DIRTY_ASK)
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

