# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 2: project templates, sources, per-template runs (021)."""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services.generate import GenerateCommand, GenerateReport
from ..services.storage import ProjectStore, StorageError, project_folder
from .blink import GreenBlink
from .dialogs import ask_yes_no
from .fields_dialog import FieldsDialog
from .report_text import done_text
from .strings import STRINGS
from .theme import set_button_role
from .widgets import fit_table_rows
from .worker import GenerateWorker

logger = logging.getLogger(__name__)

MODE_LABELS = (
    ("sequential", STRINGS.MODE_SEQUENTIAL),
    ("circular", STRINGS.MODE_CIRCULAR),
    ("constant", STRINGS.MODE_CONSTANT),
)


class HintComboBox(QComboBox):
    """Source-type combo that reports popup opening to stop the pulse."""

    popup_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        view = self.view()
        if view is not None:
            view.setStyleSheet(
                "background-color: white; color: black;"
                " selection-background-color: #c8e6c9;"
                " selection-color: black;"
            )

    def showPopup(self) -> None:
        self.popup_requested.emit()
        super().showPopup()


class ProjectDialog(QDialog):
    """Modal project view: sources table + template table with runs (021)."""

    def __init__(
        self,
        project_ref: str,
        store: ProjectStore | None = None,
        parent=None,
        *,
        highlight_new: bool = False,
    ) -> None:
        super().__init__(parent)
        self._store = store or ProjectStore()
        self._project_ref = project_ref
        self._worker: GenerateWorker | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._running = False
        self._highlight_new = highlight_new
        self._edit_buttons: dict[str, QPushButton] = {}
        self._source_blinks: list[GreenBlink] = []
        self._edit_blinks: dict[str, GreenBlink] = {}
        self._store.sync_template_fields(project_ref)
        pj, config_path = self._store.resolve_project(project_ref)
        self._pj = pj
        self._config_name = config_path.stem
        self._folder = project_folder(project_ref, pj, config_path, self._store)
        self._template_names = list(pj.templates)
        self._default_group = QButtonGroup(self)
        self._default_group.setExclusive(True)
        self._build_ui()
        self.finished.connect(self._stop_hints)
        if self._highlight_new:
            self._start_hints()

    # -- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.PROJ_TITLE.format(name=self._config_name))
        self.resize(920, 700)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel(STRINGS.PROJ_TITLE.format(name=self._config_name), self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        folder = QLabel(STRINGS.PROJ_FOLDER.format(path=self._folder), self)
        folder.setObjectName("pageSubtitle")
        folder.setWordWrap(True)
        layout.addWidget(folder)

        sources_title = QLabel(STRINGS.PROJ_SOURCES_TITLE, self)
        sources_title.setObjectName("sectionTitle")
        layout.addWidget(sources_title)
        self.sources_table = QTableWidget(self)
        self.sources_table.setColumnCount(3)
        self.sources_table.setHorizontalHeaderLabels(
            [STRINGS.PROJ_SRC_COL_FILE, STRINGS.PROJ_SRC_COL_TYPE, ""]
        )
        self.sources_table.verticalHeader().setVisible(False)
        self.sources_table.verticalHeader().setDefaultSectionSize(40)
        self.sources_table.setAlternatingRowColors(True)
        self.sources_table.setShowGrid(False)
        src_header = self.sources_table.horizontalHeader()
        src_header.setSectionResizeMode(0, QHeaderView.Stretch)
        src_header.setSectionResizeMode(1, QHeaderView.Fixed)
        src_header.resizeSection(1, 200)
        src_header.setSectionResizeMode(2, QHeaderView.Fixed)
        src_header.resizeSection(2, 110)
        src_header.sectionResized.connect(self._fit_source_rows)
        self._reload_sources()
        layout.addWidget(self.sources_table)
        hint = QLabel(STRINGS.PROJ_SRC_TYPES_HINT, self)
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        tpl_title = QLabel(STRINGS.PROJ_TEMPLATES_TITLE, self)
        tpl_title.setObjectName("sectionTitle")
        layout.addWidget(tpl_title)
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setHorizontalHeaderLabels(
            [
                STRINGS.PROJ_TPL_COL,
                STRINGS.PROJ_DEFAULT_COL,
                STRINGS.PROJ_COUNT_COL,
                STRINGS.PROJ_RUN,
                STRINGS.PROJ_EDIT,
                STRINGS.TPL_REMOVE,
            ]
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(6):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        for col, width in (
            (0, 215),
            (1, 160),
            (2, 90),
            (3, 155),
            (4, 152),
            (5, 90),
        ):
            header.resizeSection(col, width)
        header.sectionResized.connect(self._fit_template_rows)
        self._reload_templates()
        layout.addWidget(self.table)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.add_tpl_btn = QPushButton(STRINGS.TPL_ADD, self)
        self.add_tpl_btn.clicked.connect(self._on_add_template)
        add_row.addWidget(self.add_tpl_btn)
        self.add_src_btn = QPushButton(STRINGS.PROJ_SRC_ADD, self)
        self.add_src_btn.clicked.connect(self._on_add_source)
        add_row.addWidget(self.add_src_btn)
        self.settings_btn = QPushButton(STRINGS.PROJ_SETTINGS, self)
        self.settings_btn.clicked.connect(self._on_settings)
        add_row.addWidget(self.settings_btn)
        add_row.addStretch(1)
        layout.addLayout(add_row)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.delete_btn = QPushButton(STRINGS.PROJ_DELETE, self)
        set_button_role(self.delete_btn, "danger")
        self.delete_btn.clicked.connect(self._on_delete_project)
        footer.addWidget(self.delete_btn)
        footer.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        close_btn = buttons.button(QDialogButtonBox.Close)
        if close_btn is not None:
            close_btn.setText(STRINGS.FLD_CLOSE)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)

    def _reload_sources(self) -> None:
        """Rebuild source rows: file (read-only) + editable mode combo (021)."""
        for blink in self._source_blinks:
            blink.stop()
        self._source_blinks.clear()
        self._pj, _ = self._store.resolve_project(self._project_ref)
        self.sources_table.setRowCount(len(self._pj.data_sources))
        for row, ds in enumerate(self._pj.data_sources):
            file_item = QTableWidgetItem(ds.file)
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            self.sources_table.setItem(row, 0, file_item)
            combo = HintComboBox(self.sources_table)
            for key, label in MODE_LABELS:
                combo.addItem(label, key)
            combo.blockSignals(True)
            idx = combo.findData(ds.mode)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)
            combo.currentIndexChanged.connect(
                lambda _i=0, file=ds.file: self._on_mode_changed(file)
            )
            self.sources_table.setCellWidget(row, 1, combo)
            remove_btn = QPushButton(STRINGS.PROJ_SRC_REMOVE, self.sources_table)
            remove_btn.clicked.connect(
                lambda _checked=False, file=ds.file: self._on_remove_source(file)
            )
            self.sources_table.setCellWidget(row, 2, remove_btn)
        self._fit_source_rows()

    def _fit_source_rows(self, *_args) -> None:
        fit_table_rows(self.sources_table, minimum=40)

    def _reload_templates(self) -> None:
        """Re-resolve PJ and rebuild template rows (015/021).

        Broken config mid-session → warning, existing rows stay (016/FR-10).
        """
        try:
            self._pj, _ = self._store.resolve_project(self._project_ref)
        except Exception as e:
            logger.warning(f"reload templates failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        for blink in self._edit_blinks.values():
            blink.stop()
        self._edit_blinks.clear()
        self._edit_buttons.clear()
        self._template_names = list(self._pj.templates)
        for btn in list(self._default_group.buttons()):
            self._default_group.removeButton(btn)
        self.table.setRowCount(len(self._template_names))
        for row, name in enumerate(self._template_names):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            tdef = self._pj.templates[name]
            radio = QRadioButton(self.table)
            radio.setToolTip(STRINGS.PROJ_DEFAULT_TIP)
            radio.blockSignals(True)
            radio.setChecked(name == self._pj.default_template)
            radio.blockSignals(False)
            radio.toggled.connect(
                lambda checked=False, template=name: checked
                and self._on_default_changed(template)
            )
            self._default_group.addButton(radio)
            self.table.setCellWidget(row, 1, radio)
            spin = QSpinBox(self.table)
            spin.setRange(0, 1_000_000)
            spin.setValue(tdef.limit)
            spin.setToolTip(STRINGS.PROJ_COUNT_TIP)
            spin.valueChanged.connect(
                lambda value, template=name: self._on_template_limit_changed(
                    template, value
                )
            )
            self.table.setCellWidget(row, 2, spin)
            btn = QPushButton(STRINGS.PROJ_RUN, self.table)
            btn.clicked.connect(
                lambda _checked=False, template=name: self._on_run_template(template)
            )
            self.table.setCellWidget(row, 3, btn)
            edit_btn = QPushButton(STRINGS.PROJ_EDIT, self.table)
            edit_btn.setToolTip(STRINGS.PROJ_EDIT_TIP)
            edit_btn.clicked.connect(
                lambda _checked=False, template=name: self._open_fields_dialog(
                    template
                )
            )
            self.table.setCellWidget(row, 4, edit_btn)
            self._edit_buttons[name] = edit_btn
            rm_btn = QPushButton(STRINGS.TPL_REMOVE, self.table)
            rm_btn.clicked.connect(
                lambda _checked=False, template=name: self._on_remove_template(
                    template
                )
            )
            self.table.setCellWidget(row, 5, rm_btn)
        self._fit_template_rows()

    def _fit_template_rows(self, *_args) -> None:
        fit_table_rows(self.table, minimum=42)

    # -- onboarding hints ---------------------------------------------------
    def _start_hints(self) -> None:
        """Pulse source types and edit buttons after project creation."""
        for row in range(self.sources_table.rowCount()):
            combo = self.sources_table.cellWidget(row, 1)
            if combo is not None:
                blink = GreenBlink(combo)
                combo.popup_requested.connect(
                    lambda b=blink: self._stop_source_hint(b)
                )
                blink.start()
                self._source_blinks.append(blink)
        for name, button in self._edit_buttons.items():
            blink = GreenBlink(button)
            blink.start()
            self._edit_blinks[name] = blink

    def _stop_source_hint(self, blink: GreenBlink) -> None:
        blink.stop()
        if blink in self._source_blinks:
            self._source_blinks.remove(blink)

    def _stop_source_hints(self) -> None:
        for blink in self._source_blinks:
            blink.stop()
        self._source_blinks.clear()

    def _stop_hints(self, *_args) -> None:
        self._stop_source_hints()
        for blink in self._edit_blinks.values():
            blink.stop()
        self._edit_blinks.clear()

    def closeEvent(self, event) -> None:
        self._stop_hints()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "table"):
            self._fit_template_name_column()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, "table"):
            self._fit_template_name_column()

    def _fit_template_name_column(self) -> None:
        """Let the template name use the spare width without a Stretch mode."""
        header = self.table.horizontalHeader()
        used = sum(header.sectionSize(col) for col in range(1, header.count()))
        width = max(160, self.table.viewport().width() - used)
        if header.sectionSize(0) != width:
            header.resizeSection(0, width)

    # -- window 3 hook ------------------------------------------------------
    def _open_fields_dialog(self, template_name: str) -> None:
        """Open window 3 (FieldsDialog, 010); broken config → dialog (016)."""
        blink = self._edit_blinks.pop(template_name, None)
        if blink is not None:
            blink.stop()
        try:
            dialog = FieldsDialog(self._project_ref, template_name, self._store, self)
        except Exception as e:
            logger.warning(f"open fields dialog failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        dialog.exec_()

    # -- sources / templates management ------------------------------------
    def _on_mode_changed(self, file: str) -> None:
        if self._running:
            return
        row = next(
            (i for i, ds in enumerate(self._pj.data_sources) if ds.file == file), None
        )
        if row is None:
            return
        combo = self.sources_table.cellWidget(row, 1)
        mode = combo.currentData()
        try:
            self._store.set_source_mode(self._project_ref, file, mode)
        except Exception as e:
            logger.warning(f"set source mode failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        self._stop_source_hints()
        self._pj, _ = self._store.resolve_project(self._project_ref)

    def _on_default_changed(self, template_name: str) -> None:
        if self._running:
            return
        try:
            self._store.set_default_template(self._project_ref, template_name)
        except Exception as e:
            logger.warning(f"set default template failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        self._pj, _ = self._store.resolve_project(self._project_ref)

    def _on_template_limit_changed(self, template_name: str, value: int) -> None:
        """Persist a template's limit as soon as the spinbox changes (021)."""
        if self._running:
            return
        try:
            self._store.set_template_limit(self._project_ref, template_name, value)
            self._pj, _ = self._store.resolve_project(self._project_ref)
        except Exception as e:
            logger.warning(f"set template limit failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))

    def _on_add_source(self) -> None:
        if self._running:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, STRINGS.PROJ_SRC_ADD, "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            self._store.add_source(self._project_ref, path)
        except Exception as e:
            logger.warning(f"add source failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        self._reload_sources()

    def _on_remove_source(self, file: str) -> None:
        if self._running:
            return
        if not ask_yes_no(
            self, STRINGS.PROJ_SRC_REMOVE, STRINGS.PROJ_SRC_REMOVE_ASK.format(name=file)
        ):
            return
        try:
            self._store.remove_source(self._project_ref, file)
        except (StorageError, OSError) as e:
            logger.warning(f"remove source failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        self._reload_sources()

    def _on_add_template(self) -> None:
        if self._running:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, STRINGS.TPL_ADD, "", "Word (*.docx)"
        )
        if not path:
            return
        try:
            self._store.add_template(self._project_ref, path)
        except Exception as e:
            logger.warning(f"add template failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        self._reload_templates()

    def _on_settings(self) -> None:
        """Open the create dialog in edit mode (021, §2.7)."""
        if self._running:
            return
        from .create_dialog import CreateDialog

        dialog = CreateDialog(
            self._store, str(self._folder), self, edit_ref=self._project_ref
        )
        if dialog.exec_():
            self._pj, _ = self._store.resolve_project(self._project_ref)
            self._reload_sources()
            self._reload_templates()

    def _on_remove_template(self, template_name: str) -> None:
        if self._running:
            return
        if len(self._template_names) == 1:
            QMessageBox.information(self, STRINGS.TPL_REMOVE, STRINGS.TPL_LAST_KEPT)
            return
        if template_name == self._pj.default_template:
            QMessageBox.information(
                self, STRINGS.TPL_REMOVE, STRINGS.TPL_DEFAULT_LOCKED
            )
            return
        if not ask_yes_no(
            self, STRINGS.TPL_REMOVE, STRINGS.TPL_REMOVE_ASK.format(name=template_name)
        ):
            return
        try:
            self._store.remove_template(self._project_ref, template_name)
        except Exception as e:
            logger.warning(f"remove template failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        self._reload_templates()

    def _on_delete_project(self) -> None:
        if self._running:
            return
        name = self._config_name
        box = QMessageBox(self)
        box.setWindowTitle(STRINGS.PROJ_DELETE)
        box.setText(STRINGS.PROJ_DELETE_ASK.format(name=name))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText(STRINGS.BTN_YES)
        box.button(QMessageBox.No).setText(STRINGS.BTN_NO)
        check = QCheckBox(STRINGS.PROJ_DELETE_FOLDER, box)
        box.setCheckBox(check)
        if box.exec_() != QMessageBox.Yes:
            return
        try:
            self._store.delete_project(
                self._project_ref, delete_folder=check.isChecked()
            )
        except Exception as e:
            logger.warning(f"delete project failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            return
        QMessageBox.information(
            self, STRINGS.PROJ_DELETE, STRINGS.PROJ_DELETED.format(name=name)
        )
        self.accept()

    # -- per-template run ----------------------------------------------------
    def _on_run_template(self, template_name: str) -> None:
        if self._running:
            return
        self._running = True
        row = self._template_names.index(template_name)
        spin = self.table.cellWidget(row, 2)
        limit = spin.value()
        try:
            self._store.set_template_limit(self._project_ref, template_name, limit)
        except Exception as e:
            logger.warning(f"save template limit failed: {e}", exc_info=True)
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
            self._running = False
            return
        cmd = GenerateCommand(
            project_ref=self._project_ref, template=template_name
        )
        self._progress_dialog = QProgressDialog(
            STRINGS.MAIN_PROGRESS_TITLE, STRINGS.MAIN_CANCEL, 0, 0, self
        )
        self._progress_dialog.canceled.connect(self._on_cancel)
        self._progress_dialog.show()
        self._worker = GenerateWorker(cmd, store=self._store, parent=self)
        self._worker.progressed.connect(self._on_progressed)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()

    def _on_progressed(self, created: int, total: int) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.setLabelText(
                STRINGS.MAIN_STATUS_RUNNING.format(created=created, total=total)
            )

    def _finish_run(self) -> None:
        self._running = False
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None

    def _on_finished(self, report: GenerateReport) -> None:
        self._finish_run()
        text = done_text(report)
        if report.errors:
            details = "\n".join(f"{i}: {msg}" for i, msg in report.errors)
            QMessageBox.information(
                self, STRINGS.MAIN_DONE_TITLE, f"{text}\n\n{details}"
            )
        else:
            QMessageBox.information(self, STRINGS.MAIN_DONE_TITLE, text)

    def _on_failed(self, message: str) -> None:
        self._finish_run()
        QMessageBox.critical(self, STRINGS.MAIN_ERROR_TITLE, message)
