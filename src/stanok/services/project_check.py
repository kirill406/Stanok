# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project folder structure check before creation (024).

Checks folders, template and table files. It never binds fields to columns:
that is the job of the fields window.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document

from ..engine.xmlops import PLACEHOLDER_RE, iter_paragraphs
from ..gui.strings import STRINGS
from ..tables.excel import ExcelReader, HeaderError, TableReadError
from .storage import ProjectStore

logger = logging.getLogger(__name__)

EMPTY_FIELD_RE = re.compile(r"\{\{\s*\}\}")


@dataclass(frozen=True)
class CheckIssue:
    """One problem: file (relative to the project folder), column, text."""

    file: str
    column: str | None
    message: str


@dataclass
class ProjectCheck:
    """Result of check_project_structure: errors block creation, warnings do not."""

    errors: list[CheckIssue] = field(default_factory=list)
    warnings: list[CheckIssue] = field(default_factory=list)
    xlsx: list[str] = field(default_factory=list)  # Данные/*.xlsx, sorted
    docx: list[str] = field(default_factory=list)  # Шаблоны/*.docx, sorted
    missing_dirs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_project_structure(
    folder: Path, name: str, store: ProjectStore
) -> ProjectCheck:
    """Check name, subfolders, template and table files of one project folder."""
    folder = Path(folder)
    check = ProjectCheck()
    _check_name(name, store, check)
    if not folder.is_dir():
        check.errors.append(
            CheckIssue("", None, STRINGS.PCHK_NO_FOLDER.format(path=folder))
        )
        return check

    for dir_name in (STRINGS.DATA_DIR, STRINGS.TPL_DIR):
        if not (folder / dir_name).is_dir():
            check.missing_dirs.append(dir_name)
    if check.missing_dirs:
        check.errors.append(
            CheckIssue(
                "",
                None,
                STRINGS.PCHK_MISSING_DIRS.format(dirs=", ".join(check.missing_dirs)),
            )
        )

    check.docx = _relative_files(folder, STRINGS.TPL_DIR, "*.docx")
    check.xlsx = _relative_files(folder, STRINGS.DATA_DIR, "*.xlsx")
    if (folder / STRINGS.TPL_DIR).is_dir() and not check.docx:
        check.errors.append(CheckIssue(STRINGS.TPL_DIR, None, STRINGS.PCHK_NO_DOCX))
    if (folder / STRINGS.DATA_DIR).is_dir() and not check.xlsx:
        check.errors.append(CheckIssue(STRINGS.DATA_DIR, None, STRINGS.PCHK_NO_XLSX))

    for rel in check.docx:
        _check_template(folder, rel, check)
    for rel in check.xlsx:
        _check_table(folder, rel, check)
    logger.debug(
        f"project check {folder}: errors={len(check.errors)} "
        f"warnings={len(check.warnings)} docx={len(check.docx)} "
        f"xlsx={len(check.xlsx)}"
    )
    return check


def name_problem(name: str, store: ProjectStore) -> str | None:
    """Text of the first problem with a project name, or None when it is usable."""
    name = (name or "").strip()
    if not name:
        return STRINGS.PCHK_NAME_EMPTY
    if "/" in name or "\\" in name or name in (".", ".."):
        return STRINGS.PCHK_NAME_BAD
    if store.config_exists(name):
        return STRINGS.PCHK_NAME_TAKEN.format(name=name)
    return None


def _check_name(name: str, store: ProjectStore, check: ProjectCheck) -> None:
    problem = name_problem(name, store)
    if problem is not None:
        check.errors.append(CheckIssue("", None, problem))


def _relative_files(folder: Path, sub: str, pattern: str) -> list[str]:
    """Sorted files of folder/sub matching pattern, as posix paths from folder."""
    base = folder / sub
    if not base.is_dir():
        return []
    return sorted(
        p.relative_to(folder).as_posix()
        for p in base.glob(pattern)
        if p.is_file()
    )


def _check_template(folder: Path, rel: str, check: ProjectCheck) -> None:
    """Template must open and contain at least one {{field}}."""
    path = folder / rel
    try:
        doc = Document(str(path))
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f"check template {path}: {e}", exc_info=True)
        check.errors.append(
            CheckIssue(rel, None, STRINGS.PCHK_TEMPLATE_READ.format(cause=e))
        )
        return
    except Exception as e:
        logger.critical(f"unexpected check template {path}: {e}", exc_info=True)
        check.errors.append(
            CheckIssue(rel, None, STRINGS.PCHK_TEMPLATE_READ.format(cause=e))
        )
        return

    fields: list[str] = []
    empty = False
    for paragraph in iter_paragraphs(doc):
        text = paragraph.text
        if EMPTY_FIELD_RE.search(text):
            empty = True
        for match in PLACEHOLDER_RE.finditer(text):
            name = match.group(1).strip()
            if name and name not in fields:
                fields.append(name)
    if not fields:
        check.errors.append(CheckIssue(rel, None, STRINGS.PCHK_NO_FIELDS))
    if empty:
        check.warnings.append(CheckIssue(rel, None, STRINGS.PCHK_EMPTY_FIELD))


def _check_table(folder: Path, rel: str, check: ProjectCheck) -> None:
    """Table must have a unique header row; no data rows is only a warning."""
    path = folder / rel
    try:
        rows = ExcelReader().read(path)
    except HeaderError as e:
        if e.kind == "no_headers":
            message = STRINGS.PCHK_NO_HEADERS
        else:
            message = STRINGS.PCHK_TABLE_READ.format(cause=e.cause)
        check.errors.append(CheckIssue(rel, None, message))
        return
    except TableReadError as e:
        check.errors.append(
            CheckIssue(rel, None, STRINGS.PCHK_TABLE_READ.format(cause=e.cause))
        )
        return
    except Exception as e:
        logger.critical(f"unexpected check table {path}: {e}", exc_info=True)
        check.errors.append(
            CheckIssue(rel, None, STRINGS.PCHK_TABLE_READ.format(cause=e))
        )
        return
    if not rows:
        check.warnings.append(CheckIssue(rel, None, STRINGS.PCHK_NO_ROWS))
