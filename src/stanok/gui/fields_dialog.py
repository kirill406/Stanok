# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Window 3: edit template field sources and values, counters, persist on Save.

021: a table field picks a counter (`counter_name`) which owns the source;
the counters table shows source / format / one position / resume.
"""

from __future__ import annotations

import logging
import shutil
from datetime import date
from functools import wraps
from pathlib import Path, PurePosixPath

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..services.generate import TemplateError
from ..services.storage import ProjectStore, project_folder
from ..engine.schema import CounterDef, FieldDef, FieldSource, ProjectJSON, validate_pj
from ..engine.resolve import COUNTER_WIDTHS, TODAY_PRESETS, format_today
from ..tables.excel import ExcelReader
from .dialogs import ask_save_discard_cancel, ask_text, ask_yes_no
from .strings import STRINGS
from .theme import set_button_role
from .table_picker import eye_icon, open_picker, picker_available
from .widgets import fit_table_rows

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "constant": STRINGS.FLD_SRC_CONSTANT,
    "table": STRINGS.FLD_SRC_TABLE,
    "counter": STRINGS.FLD_SRC_COUNTER,
    "today": STRINGS.FLD_SRC_TODAY,
}
SOURCE_ORDER = ("constant", "table", "counter", "today")


class _FieldError(Exception):
    """Save-blocking validation error: field + STRINGS message key."""

    def __init__(self, field: str, msg: str):
        super().__init__(f"{msg}: {field}")
        self.field = field
        self.msg = msg


def _counter_action(action: str):
    """Catch unexpected errors in counter widgets: log + keep dialog open."""

    def decorate(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                target = (
                    args[0] if args and not isinstance(args[0], bool) else ""
                )
                self._counter_failed(action, target, e)

        return wrapper

    return decorate


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
        self._crows: dict[str, dict] = {}
        self._rows_cache: dict[str, list[dict]] = {}
        self._headers_warned: set[str] = set()
        self._recovery_prompted = False
        self._recovery_dir: Path | None = None
        pj, config_path = self._store.resolve_project(project_ref)
        self._pj = pj
        self._shared = self._store.global_counters()  # 026
        self._config_name = config_path.stem
        self._folder = project_folder(project_ref, pj, config_path, self._store)
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
        sources = (
            [source_file]
            if source_file
            else [ds.file for ds in self._pj.data_sources]
        )
        rows: list[dict] = []
        if self._folder.exists() and self._folder.is_dir():
            for f in sources:
                path = self._resolve_source_path(f)
                if path is None:
                    continue
                try:
                    reader = ExcelReader()
                    rows.extend(reader.read(path))
                except Exception as e:
                    logger.warning(f"headers for {f} failed: {e}", exc_info=True)
                    self._warn_source(f, f"{f}: {e}")
                else:
                    skipped = reader.skipped_columns.get(path, [])
                    if skipped:
                        message = STRINGS.TBL_SKIPPED_COLUMNS.format(
                            columns=", ".join(skipped)
                        )
                        self._warn_source(f, f"{f}: {message}")
        self._rows_cache[key] = rows
        return rows

    def _resolve_source_path(self, source: str) -> Path | None:
        """Path for a source; offer a one-time fix when the file is missing."""
        path = self._folder / source
        if path.is_file():
            return path
        name = PurePosixPath(source.replace("\\", "/")).name
        if self._recovery_dir is not None:
            restored = self._restore_source(source, name, self._recovery_dir)
            if restored is not None:
                return self._folder / restored
        elif not self._recovery_prompted:
            self._recovery_prompted = True
            choice = self._ask_source_recovery(name)
            if choice == "pick":
                folder = QFileDialog.getExistingDirectory(
                    self, STRINGS.FLD_SRC_FIND_TITLE, str(self._folder)
                )
                if folder:
                    self._recovery_dir = Path(folder)
                    restored = self._restore_source(
                        source, name, self._recovery_dir
                    )
                    if restored is not None:
                        return self._folder / restored
            elif choice == "create":
                self._create_project_dirs()
        self._warn_source(source, STRINGS.FLD_SRC_MISSING.format(name=name))
        return None

    def _ask_source_recovery(self, name: str) -> str | None:
        """Ask how to fix a missing source: 'pick', 'create' or None."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(STRINGS.MAIN_ERROR_TITLE)
        box.setText(STRINGS.FLD_SRC_MISSING.format(name=name))
        box.setInformativeText(STRINGS.FLD_SRC_MISSING_HINT)
        pick = box.addButton(STRINGS.FLD_SRC_PICK, QMessageBox.ActionRole)
        create = box.addButton(STRINGS.FLD_SRC_CREATE, QMessageBox.ActionRole)
        box.addButton(STRINGS.MAIN_CANCEL, QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is pick:
            return "pick"
        if clicked is create:
            return "create"
        return None

    def _restore_source(
        self, source: str, name: str, folder: Path
    ) -> str | None:
        """Bind `source` to file `name` found under `folder`; None if absent."""
        found = next(
            (
                c
                for c in (folder / name, folder / STRINGS.DATA_DIR / name)
                if c.is_file()
            ),
            None,
        )
        if found is None:
            return None
        found = found.resolve()
        root = self._folder.resolve()
        target = (self._folder / source).resolve()
        try:
            if found == target:
                return source
            if root in found.parents:
                new = found.relative_to(root).as_posix()
                self._rebind_source(source, new)
                return new
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(found, target)
        except OSError as e:
            logger.warning(
                f"restore source {name} from {folder}: {e}", exc_info=True
            )
            QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, f"{name}: {e}")
            return None
        self._rows_cache.clear()
        return source

    def _rebind_source(self, old: str, new: str) -> None:
        """Repoint data sources and counters from `old` to `new` path."""
        for ds in self._pj.data_sources:
            if ds.file == old:
                ds.file = new
        for cdef in self._pj.counters.values():
            if cdef.table == old:
                cdef.table = new
        try:
            self._store.save(self._pj, name=self._config_name)
        except Exception as e:
            logger.warning(
                f"save rebound source {old} -> {new}: {e}", exc_info=True
            )

    def _create_project_dirs(self) -> None:
        """Recreate the project Данные/Шаблоны folders."""
        for sub in (STRINGS.DATA_DIR, STRINGS.TPL_DIR):
            try:
                (self._folder / sub).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(
                    f"cannot create {self._folder / sub}: {e}", exc_info=True
                )
                QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, str(e))
                return
        QMessageBox.information(
            self,
            STRINGS.MAIN_ERROR_TITLE,
            STRINGS.FLD_SRC_DIR_MADE.format(folder=self._folder),
        )

    def _warn_source(self, key: str, message: str) -> None:
        """Warn once per source about an unreadable or missing table."""
        if key in self._headers_warned:
            return
        self._headers_warned.add(key)
        QMessageBox.warning(self, STRINGS.MAIN_ERROR_TITLE, message)

    def _read_headers(self, source_file: str | None) -> list[str]:
        """Column headers for one source (None = union of all)."""
        headers: list[str] = []
        for r in self._read_table_rows(source_file):
            for h in r.keys():
                if h not in headers:
                    headers.append(h)
        return headers

    def _counter_table(self, cname: str | None) -> str | None:
        """Current source bound to a counter (from its row combo, else PJ)."""
        cst = self._crows.get(cname)
        if cst is not None:
            return cst["table"].currentData()
        cdef = self._pj.counters.get(cname) if cname else None
        return cdef.table if cdef is not None else None

    # -- UI construction --------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle(STRINGS.FLD_TITLE.format(name=self._template_name))
        self.resize(920, 700)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(8)
        title = QLabel(STRINGS.FLD_TITLE.format(name=self._template_name), self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        scroll = QScrollArea(self)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        body = QVBoxLayout(content)
        body.setContentsMargins(4, 4, 4, 4)
        body.setSpacing(8)
        layout.addWidget(scroll, 1)
        scroll.setWidget(content)
        layout = body

        layout.addWidget(self._section_title(STRINGS.FLD_FNAME_TITLE))
        fname_row = QHBoxLayout()
        self.fname_edit = QLineEdit(self._pj.filename_template or "", self)
        self.fname_edit.textChanged.connect(self._mark_dirty)
        fname_row.addWidget(self.fname_edit, 1)
        self.fname_insert_btn = QPushButton(STRINGS.FLD_INSERT_FIELD, self)
        self.fname_insert_btn.clicked.connect(self._on_insert_field)
        fname_row.addWidget(self.fname_insert_btn)
        layout.addLayout(fname_row)

        layout.addWidget(self._section_title(STRINGS.FLD_FIELDS_TITLE))
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
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
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
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
            type_combo.setCurrentIndex(SOURCE_ORDER.index(fdef.source.value))
            type_combo.blockSignals(True)
            self.table.setCellWidget(row, 1, type_combo)
            type_combo.blockSignals(False)
            type_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._on_type_changed(field)
            )
            self._rows[name] = {"type": type_combo}
            self._build_value_cell(row, name, fdef)
        layout.addWidget(self.table)

        layout.addWidget(self._section_title(STRINGS.FLD_COUNTERS_TITLE))
        definition = QLabel(STRINGS.FLD_CNT_DEFINITION, self)
        definition.setObjectName("muted")
        definition.setWordWrap(True)
        layout.addWidget(definition)
        self.ctable = QTableWidget(self)
        self.ctable.setColumnCount(6)
        self.ctable.setAlternatingRowColors(True)
        self.ctable.setShowGrid(False)
        header_tips = [
            STRINGS.FLD_CNT_NAME_TIP,
            STRINGS.FLD_CNT_SOURCE_TIP,
            STRINGS.FLD_CNT_FORMAT_TIP,
            STRINGS.FLD_POS_TIP,
            STRINGS.FLD_CNT_RESUME_TIP,
        ]
        self.ctable.setHorizontalHeaderLabels(
            [
                STRINGS.FLD_CNT_NAME,
                STRINGS.FLD_CNT_SOURCE,
                STRINGS.FLD_CNT_FORMAT,
                STRINGS.FLD_CNT_POS,
                STRINGS.FLD_CNT_RESUME,
                "",
            ]
        )
        for col, tip in enumerate(header_tips):
            self.ctable.horizontalHeaderItem(col).setToolTip(tip)
        self.ctable.horizontalHeader().setStretchLastSection(False)
        self.ctable.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        # ResizeToContents ignores cell widgets, so the remove button column gets a fixed width.
        self.ctable.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.ctable.horizontalHeader().resizeSection(5, 120)
        self._build_counters_table()
        layout.addWidget(self.ctable)
        layout.addWidget(QLabel(STRINGS.FLD_CNT_HINT, self))

        self.counter_add_btn = QPushButton(STRINGS.FLD_COUNTER_CREATE, self)
        self.counter_add_btn.clicked.connect(self._on_counter_create)
        layout.addWidget(self.counter_add_btn)
        self._fit_tables()

        buttons = QDialogButtonBox(self)
        self.save_btn = buttons.addButton(
            STRINGS.FLD_SAVE, QDialogButtonBox.ActionRole
        )
        set_button_role(self.save_btn, "primary")
        self.save_btn.clicked.connect(self._on_save)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        close_btn.setText(STRINGS.FLD_CLOSE)
        close_btn.clicked.connect(self.reject)
        # Hide AFTER all buttons are added: QDialogButtonBox unhides on add.
        self.save_btn.setVisible(False)
        self.layout().addWidget(buttons)
        self.layout().addWidget(QLabel(STRINGS.FLD_HINT, self))

    def _fit_tables(self) -> None:
        """Size tables to content; scrolling is owned by the outer QScrollArea."""
        for table in (self.table, self.ctable):
            fit_table_rows(table, minimum=32)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            height = table.horizontalHeader().height()
            for row in range(table.rowCount()):
                height += table.rowHeight(row)
            height += 2 * table.frameWidth() + 2
            table.setFixedHeight(height)

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
            "const", "cname", "col", "clabel", "fmt", "cprev",
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
            cname_combo = QComboBox(box)
            for cname in self._pj.counters:
                cname_combo.addItem(cname, cname)
            wanted = stored.counter_name if stored.source.value == "table" else None
            idx = cname_combo.findData(wanted)
            cname_combo.setCurrentIndex(idx if idx >= 0 else 0)
            cname_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._on_table_counter_changed(field)
            )
            layout.addWidget(cname_combo)
            st["cname"] = cname_combo
            sep = QLabel("/", box)
            sep.setObjectName("muted")
            sep.setFixedWidth(10)
            sep.setAlignment(Qt.AlignCenter)
            layout.addWidget(sep)
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
            for cname in self._shared:
                if cname in self._pj.counters:
                    # Same name as a project counter: a field could not tell them apart.
                    name_combo.addItem(f"{cname} ({STRINGS.GCNT_CLASH_TAG})", cname)
                    name_combo.model().item(name_combo.count() - 1).setEnabled(False)
                else:
                    name_combo.addItem(f"{cname} ({STRINGS.GCNT_SHARED_TAG})", cname)
            wanted = (
                str(stored.value)
                if stored.source.value == "counter" and stored.value
                else ""
            )
            idx = name_combo.findData(wanted)
            if idx < 0 and wanted:
                name_combo.addItem(wanted, wanted)
                idx = name_combo.findData(wanted)
                st["touched"] = True
            name_combo.setCurrentIndex(idx if idx >= 0 else 0)
            name_combo.currentIndexChanged.connect(
                lambda _i=0, field=name: self._on_counter_name_changed(field)
            )
            layout.addWidget(name_combo)
            st["cname"] = name_combo
            cprev = QLabel(self.table)
            self.table.setCellWidget(row, 3, cprev)
            st["cprev"] = cprev
            self._update_counter_preview(name)
        else:  # today ("Дата"): format combo + preview
            dfmt = QComboBox(box)
            if stored.source.value == "today" and stored.value is None:
                dfmt.addItem(STRINGS.FLD_DATE_KEEP, None)
            today = date.today()
            for key in TODAY_PRESETS:
                dfmt.addItem(str(format_today(key, today)), key)
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

    @_counter_action("create")
    def _on_counter_create(self, _checked: bool = False) -> None:
        text, ok = ask_text(
            self, STRINGS.FLD_COUNTER_CREATE, STRINGS.FLD_COUNTER_NAME
        )
        cname = text.strip()
        if not ok or not cname:
            return
        if cname in self._pj.counters or cname in self._shared:
            QMessageBox.warning(
                self,
                STRINGS.MAIN_ERROR_TITLE,
                STRINGS.FLD_DUP_COUNTER.format(name=cname),
            )
            return
        logger.debug(f"counter created: {cname} in {self._template_name}")
        self._pj.counters[cname] = CounterDef()
        self._build_counters_table()
        self._fit_tables()
        for st in self._rows.values():
            combo = st.get("cname")
            if combo is None:
                continue
            combo.blockSignals(True)
            combo.addItem(cname, cname)
            combo.blockSignals(False)
        self._mark_dirty()

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _build_counters_table(self) -> None:
        self._crows = {}
        names = list(self._pj.counters)
        self.ctable.setRowCount(len(names))
        for row, cname in enumerate(names):
            cdef = self._pj.counters[cname]
            name_item = QTableWidgetItem(cname)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.ctable.setItem(row, 0, name_item)
            table_combo = QComboBox(self.ctable)
            table_combo.setToolTip(STRINGS.FLD_CNT_SOURCE_TIP)
            table_combo.addItem(STRINGS.FLD_NONE, None)
            for ds in self._pj.data_sources:
                table_combo.addItem(ds.file, ds.file)
            idx = table_combo.findData(cdef.table)
            table_combo.setCurrentIndex(idx if idx >= 0 else 0)
            table_combo.currentIndexChanged.connect(
                lambda _i=0, counter=cname: self._on_counter_source_changed(counter)
            )
            self.ctable.setCellWidget(row, 1, table_combo)
            fmt_combo = QComboBox(self.ctable)
            fmt_combo.setToolTip(STRINGS.FLD_CNT_FORMAT_TIP)
            for width in COUNTER_WIDTHS:
                fmt_combo.addItem(width, width)
            if cdef.format not in COUNTER_WIDTHS:
                fmt_combo.addItem(cdef.format, cdef.format)
            fmt_combo.setCurrentIndex(fmt_combo.findData(cdef.format))
            fmt_combo.currentIndexChanged.connect(
                lambda _i=0, counter=cname: self._mark_counter_touched(counter)
            )
            self.ctable.setCellWidget(row, 2, fmt_combo)
            pos_box = QWidget(self.ctable)
            pos_layout = QHBoxLayout(pos_box)
            pos_layout.setContentsMargins(0, 0, 0, 0)
            pos_layout.setSpacing(2)
            pos_edit = QLineEdit(str(cdef.pos), pos_box)
            pos_edit.setToolTip(STRINGS.FLD_POS_TIP)
            pos_edit.textChanged.connect(
                lambda _t="", counter=cname: self._mark_counter_touched(counter)
            )
            pos_layout.addWidget(pos_edit)
            pick_btn = QToolButton(pos_box)
            pick_btn.setIcon(eye_icon())
            pick_btn.setAutoRaise(True)
            pick_btn.setCursor(Qt.PointingHandCursor)
            pick_btn.setAccessibleName(STRINGS.FLD_PICK_DATA)
            pick_btn.clicked.connect(
                lambda _checked=False, counter=cname: self._pick_counter_value(counter)
            )
            pos_layout.addWidget(pick_btn)
            self.ctable.setCellWidget(row, 3, pos_box)
            resume_check = QCheckBox(self.ctable)
            resume_check.setToolTip(STRINGS.FLD_CNT_RESUME_TIP)
            resume_check.setChecked(not bool(cdef.resume))
            resume_check.stateChanged.connect(
                lambda _s=0, counter=cname: self._mark_counter_touched(counter)
            )
            self.ctable.setCellWidget(row, 4, resume_check)
            remove_btn = QPushButton(STRINGS.FLD_CNT_REMOVE, self.ctable)
            remove_btn.setToolTip(STRINGS.FLD_CNT_REMOVE_TIP)
            remove_btn.clicked.connect(
                lambda _checked=False, counter=cname: self._on_counter_remove(counter)
            )
            self.ctable.setCellWidget(row, 5, remove_btn)
            self._crows[cname] = {
                "table": table_combo,
                "pos": pos_edit,
                "pos_box": pos_box,
                "resume": resume_check,
                "pick": pick_btn,
                "fmt": fmt_combo,
                "touched": False,
            }
            self._update_counter_row_state(cname)

    def _counter_users(self, cname: str) -> list[str]:
        """Fields that read counter `cname`: saved templates and this dialog's rows."""
        users: list[str] = []
        for tname, tdef in self._pj.templates.items():
            if tname == self._template_name:
                continue  # this template's rows are read from the widgets below
            for fname, fdef in tdef.fields.items():
                if (fdef.source == FieldSource.TABLE and fdef.counter_name == cname) or (
                    fdef.source == FieldSource.COUNTER and fdef.value == cname
                ):
                    users.append(f"{tname}: {fname}")
        for name, st in self._rows.items():
            if "cname" not in st:
                continue  # constant and date rows have no counter
            if st["cname"].currentData() == cname:
                users.append(f"{self._template_name}: {name}")
        return users

    @_counter_action("remove counter")
    def _on_counter_remove(self, cname: str) -> None:
        if cname not in self._pj.counters:
            return
        if self._pj.counters[cname].table is not None:
            QMessageBox.information(self, STRINGS.FLD_CNT_REMOVE, STRINGS.FLD_CNT_REMOVE_BOUND)
            return
        users = self._counter_users(cname)
        if users:
            QMessageBox.information(
                self,
                STRINGS.FLD_CNT_REMOVE,
                STRINGS.FLD_CNT_REMOVE_USED.format(name=cname, fields=", ".join(users)),
            )
            return
        if not ask_yes_no(
            self, STRINGS.FLD_CNT_REMOVE, STRINGS.FLD_CNT_REMOVE_ASK.format(name=cname)
        ):
            return
        logger.debug(f"counter removed: {cname} in {self._template_name}")
        del self._pj.counters[cname]
        for st in self._rows.values():
            combo = st.get("cname")
            if combo is None:
                continue
            idx = combo.findData(cname)
            if idx >= 0:
                combo.blockSignals(True)
                combo.removeItem(idx)
                combo.blockSignals(False)
        self._build_counters_table()
        self._fit_tables()
        self._mark_dirty()

    def _on_insert_field(self) -> None:
        menu = QMenu(self)
        for field_name in self._template_def.fields:
            menu.addAction(
                field_name,
                lambda _checked=False, name=field_name: self.fname_edit.insert(
                    f"{{{name}}}"
                ),
            )
        menu.addSeparator()
        for var in ("{i}", "{template}"):
            menu.addAction(
                var,
                lambda _checked=False, text=var: self.fname_edit.insert(text),
            )
        menu.exec_(self.fname_insert_btn.mapToGlobal(
            self.fname_insert_btn.rect().bottomLeft()
        ))

    # -- counter previews -------------------------------------------------------
    @_counter_action("change source")
    def _on_counter_source_changed(self, cname: str) -> None:
        self._update_counter_row_state(cname)
        for field, st in self._rows.items():
            if st["type"].currentData() == "table" and self._selected_counter(field) == cname:
                self._refill_columns(field, select=None)
        self._mark_counter_touched(cname)

    def _counter_table_live(self, cname: str) -> str | None:
        cst = self._crows.get(cname)
        if cst is not None:
            return cst["table"].currentData()
        cdef = self._pj.counters.get(cname)
        return cdef.table if cdef is not None else None

    def _mode_of_table(self, table: str | None) -> str | None:
        if not table:
            return None
        for source in self._pj.data_sources:
            if source.file == table:
                return source.mode
        return None

    def _update_counter_row_state(self, cname: str) -> None:
        """Constant sources keep their position fixed; the picker needs a table."""
        cst = self._crows.get(cname)
        if cst is None:
            return
        table = self._counter_table_live(cname)
        constant = self._mode_of_table(table) == "constant"
        pos = cst["pos"]
        pos.setReadOnly(constant)
        pos.setToolTip(
            STRINGS.FLD_POS_CONST_TIP if constant else STRINGS.FLD_POS_TIP
        )
        resume = cst["resume"]
        if table is None or constant:
            resume.setEnabled(False)
            resume.setToolTip(STRINGS.FLD_CNT_RESUME_NA_TIP)
        else:
            resume.setEnabled(True)
            resume.setToolTip(STRINGS.FLD_CNT_RESUME_TIP)
        pick = cst["pick"]
        if table is None:
            pick.setEnabled(False)
            pick.setToolTip(STRINGS.FLD_PICK_NO_SOURCE_TIP)
        elif not picker_available():
            pick.setEnabled(False)
            pick.setToolTip(STRINGS.FLD_PICK_DISABLED_TIP)
        else:
            pick.setEnabled(True)
            pick.setToolTip(STRINGS.FLD_PICK_TIP)

    @_counter_action("pick value")
    def _pick_counter_value(self, cname: str) -> None:
        table = self._counter_table_live(cname)
        if table is None:
            return
        value = open_picker(
            self, self._folder, table, self._current_counter_pos(cname)
        )
        if value is None:
            return
        cst = self._crows.get(cname)
        if cst is not None:
            cst["pos"].setText(str(value))

    @_counter_action("change position, format or resume")
    def _mark_counter_touched(self, cname: str) -> None:
        logger.debug(f"counter changed: {cname} in {self._template_name}")
        self._crows[cname]["touched"] = True
        self._mark_dirty()
        for field, st in self._rows.items():
            combo = st.get("cname")
            if combo is None or combo.currentData() != cname:
                continue
            kind = st["type"].currentData()
            if kind == "counter":
                self._update_counter_preview(field)
            elif kind == "table":
                self._update_table_value(field)

    def _selected_counter(self, name: str) -> str | None:
        return self._rows[name]["cname"].currentData()

    @_counter_action("change field counter")
    def _on_table_counter_changed(self, name: str) -> None:
        self._refill_columns(name, select=None)
        self._update_table_value(name)
        self._mark_row_touched(name)

    @_counter_action("change field counter")
    def _on_counter_name_changed(self, name: str) -> None:
        self._update_counter_preview(name)
        self._mark_row_touched(name)

    def _current_counter_pos(self, cname: str | None) -> int | None:
        if cname is None:
            return None
        cst = self._crows.get(cname)
        if cst is not None:
            try:
                return int(cst["pos"].text())
            except (ValueError, TypeError):
                return None
        cdef = self._pj.counters.get(cname) or self._shared.get(cname)
        return cdef.pos if cdef is not None else 0

    def _counter_format(self, cname: str | None) -> str:
        if cname is None:
            return "1"
        cst = self._crows.get(cname)
        if cst is not None:
            return cst["fmt"].currentData() or "1"
        cdef = self._pj.counters.get(cname) or self._shared.get(cname)
        return cdef.format if cdef is not None else "1"

    def _update_counter_preview(self, name: str) -> None:
        st = self._rows[name]
        pos = self._current_counter_pos(st["cname"].currentData())
        width = self._counter_format(st["cname"].currentData())
        if pos is None or pos < 0:
            st["cprev"].setText("")
        else:
            st["cprev"].setText(str(pos).zfill(len(width)))

    def _update_today_preview(self, name: str) -> None:
        st = self._rows[name]
        value = format_today(st["dfmt"].currentData(), date.today())
        st["dlabel"].setText(str(value))

    def _counter_row_index(self, cname: str | None) -> tuple[list[dict], int | None]:
        """Rows of the counter source + the row its current position points at."""
        table = self._counter_table(cname)
        rows = self._read_table_rows(table)
        pos = self._current_counter_pos(cname)
        if table is None or pos is None or pos < 0 or not rows:
            return rows, None
        mode = self._mode_of_table(table) or "sequential"
        idx = pos % len(rows) if mode == "circular" else pos
        return rows, idx if 0 <= idx < len(rows) else None

    def _update_table_value(self, name: str) -> None:
        st = self._rows[name]
        rows, idx = self._counter_row_index(st["cname"].currentData())
        row = rows[idx] if idx is not None else {}
        column = st["col"].currentText()
        if row and any(v not in (None, "") for v in row.values()):
            if column and column in row:
                st["clabel"].setText(str(row[column]))
            else:
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
        self._fit_tables()
        self._mark_row_touched(name)

    def _refill_columns(self, name: str, select: object = None) -> None:
        st = self._rows[name]
        headers = self._read_headers(self._counter_table(st["cname"].currentData()))
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

    def _counter_failed(self, action: str, target: str, error: Exception) -> None:
        logger.critical(
            f"counter {action} failed for {target!r} in "
            f"{self._config_name}/{self._template_name}: {error}",
            exc_info=True,
        )
        QMessageBox.critical(
            self,
            STRINGS.MAIN_ERROR_TITLE,
            STRINGS.FLD_CNT_CHANGE_FAILED.format(error=error),
        )

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
                f.counter_name = None
            elif kind == "table":
                column = st["col"].currentText()
                cname = st["cname"].currentData()
                if cname is None:
                    raise _FieldError(name, "FLD_NO_COUNTER")
                if not column:
                    raise _FieldError(name, "FLD_EMPTY_VALUE")
                f.source = FieldSource.TABLE
                f.value = column
                f.counter_name = cname
            elif kind == "counter":
                cname = self._selected_counter(name)
                if cname is None:
                    raise _FieldError(name, "FLD_NO_COUNTER")
                # A shared counter lives in settings: never copy its name into the project.
                if cname not in self._pj.counters and cname not in self._shared:
                    self._pj.counters[cname] = CounterDef()
                f.source = FieldSource.COUNTER
                f.value = cname
                f.counter_name = None
            else:
                value = st["dfmt"].currentData()
                if value is None:
                    raise _FieldError(name, "FLD_EMPTY_VALUE")
                f.source = FieldSource.TODAY
                f.value = value
                f.counter_name = None
        for cname, cst in self._crows.items():
            try:
                position = int(cst["pos"].text())
            except ValueError:
                raise _FieldError(cname, "FLD_CNT_POS_BAD") from None
            if position < 0:
                raise _FieldError(cname, "FLD_CNT_POS_BAD")
            cdef = self._pj.counters[cname]
            cdef.table = cst["table"].currentData()
            cdef.pos = position
            cdef.resume = 0 if cst["resume"].isChecked() else 1
            cdef.format = cst["fmt"].currentData() or "1"
        fname = self.fname_edit.text().strip()
        if not fname:
            raise _FieldError(self._template_name, "FLD_EMPTY_VALUE")
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
        answer = ask_save_discard_cancel(
            self, STRINGS.MAIN_TITLE, STRINGS.FLD_DIRTY_ASK
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
