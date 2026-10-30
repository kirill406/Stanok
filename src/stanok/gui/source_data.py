# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Rows and column headers of a project's data sources for window 3 (027).

Shared by the template window and the field editor, so one read and one
missing-file recovery serve both. A recovery that moves a source rebinds
it in the live project and saves at once, as before.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path, PurePosixPath

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget

from ..engine.schema import ProjectJSON
from ..services.storage import ProjectStore
from ..tables.excel import ExcelReader
from .strings import STRINGS

logger = logging.getLogger(__name__)


class SourceData:
    """Cached rows per source; warns once per source and offers a fix when missing."""

    def __init__(
        self,
        pj: ProjectJSON,
        folder: Path,
        store: ProjectStore,
        config_name: str,
        parent: QWidget,
    ) -> None:
        self._pj = pj
        self._folder = folder
        self._store = store
        self._config_name = config_name
        self._parent = parent
        self._rows_cache: dict[str, list[dict]] = {}
        self._warned: set[str] = set()
        self._recovery_prompted = False
        self._recovery_dir: Path | None = None

    @property
    def folder(self) -> Path:
        return self._folder

    def headers(self, source_file: str | None) -> list[str]:
        """Column headers for one source (None = union of all sources)."""
        headers: list[str] = []
        for row in self.rows(source_file):
            for key in row.keys():
                if key not in headers:
                    headers.append(key)
        return headers

    def rows(self, source_file: str | None) -> list[dict]:
        """Rows for one source (None = all sources concatenated); warns once."""
        key = source_file or "__all__"
        if key in self._rows_cache:
            return self._rows_cache[key]
        sources = (
            [source_file] if source_file else [ds.file for ds in self._pj.data_sources]
        )
        rows: list[dict] = []
        if self._folder.exists() and self._folder.is_dir():
            for source in sources:
                path = self._resolve_path(source)
                if path is None:
                    continue
                try:
                    reader = ExcelReader()
                    rows.extend(reader.read(path))
                except Exception as e:
                    logger.warning(f"rows of {source} failed: {e}", exc_info=True)
                    self._warn(source, f"{source}: {e}")
                else:
                    skipped = reader.skipped_columns.get(path, [])
                    if skipped:
                        message = STRINGS.TBL_SKIPPED_COLUMNS.format(
                            columns=", ".join(skipped)
                        )
                        self._warn(source, f"{source}: {message}")
        self._rows_cache[key] = rows
        return rows

    # -- missing files ----------------------------------------------------------
    def _resolve_path(self, source: str) -> Path | None:
        """Path for a source; offer a one-time fix when the file is missing."""
        path = self._folder / source
        if path.is_file():
            return path
        name = PurePosixPath(source.replace("\\", "/")).name
        if self._recovery_dir is not None:
            restored = self._restore(source, name, self._recovery_dir)
            if restored is not None:
                return self._folder / restored
        elif not self._recovery_prompted:
            self._recovery_prompted = True
            choice = self._ask_recovery(name)
            if choice == "pick":
                folder = QFileDialog.getExistingDirectory(
                    self._parent, STRINGS.FLD_SRC_FIND_TITLE, str(self._folder)
                )
                if folder:
                    self._recovery_dir = Path(folder)
                    restored = self._restore(source, name, self._recovery_dir)
                    if restored is not None:
                        return self._folder / restored
            elif choice == "create":
                self._create_dirs()
        self._warn(source, STRINGS.FLD_SRC_MISSING.format(name=name))
        return None

    def _ask_recovery(self, name: str) -> str | None:
        """Ask how to fix a missing source: 'pick', 'create' or None."""
        box = QMessageBox(self._parent)
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

    def _restore(self, source: str, name: str, folder: Path) -> str | None:
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
                self._rebind(source, new)
                return new
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(found, target)
        except OSError as e:
            logger.warning(f"restore source {name} from {folder}: {e}", exc_info=True)
            QMessageBox.warning(self._parent, STRINGS.MAIN_ERROR_TITLE, f"{name}: {e}")
            return None
        self._rows_cache.clear()
        return source

    def _rebind(self, old: str, new: str) -> None:
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
            logger.warning(f"save rebound source {old} -> {new}: {e}", exc_info=True)

    def _create_dirs(self) -> None:
        """Recreate the project Данные/Шаблоны folders."""
        for sub in (STRINGS.DATA_DIR, STRINGS.TPL_DIR):
            try:
                (self._folder / sub).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"cannot create {self._folder / sub}: {e}", exc_info=True)
                QMessageBox.warning(self._parent, STRINGS.MAIN_ERROR_TITLE, str(e))
                return
        QMessageBox.information(
            self._parent,
            STRINGS.MAIN_ERROR_TITLE,
            STRINGS.FLD_SRC_DIR_MADE.format(folder=self._folder),
        )

    def _warn(self, key: str, message: str) -> None:
        """Warn once per source about an unreadable or missing table."""
        if key in self._warned:
            return
        self._warned.add(key)
        QMessageBox.warning(self._parent, STRINGS.MAIN_ERROR_TITLE, message)
