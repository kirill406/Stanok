# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Detect an existing project folder layout for creation (022)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..gui.strings import STRINGS


@dataclass(frozen=True)
class ProjectLayout:
    """Project folder with Данные/Шаблоны/Результат and its source files."""

    folder: Path
    xlsx: list[Path]
    docx: list[Path]


def detect_project_layout(folder: str | Path) -> ProjectLayout | None:
    """Return layout only when all three project subfolders exist."""
    root = Path(folder).expanduser()
    if not root.is_dir():
        return None
    data = root / STRINGS.DATA_DIR
    tpl = root / STRINGS.TPL_DIR
    result = root / STRINGS.GEN_RESULT_DIR
    if not (data.is_dir() and tpl.is_dir() and result.is_dir()):
        return None
    return ProjectLayout(
        folder=root.resolve(),
        xlsx=sorted(p for p in data.glob("*.xlsx") if p.is_file()),
        docx=sorted(p for p in tpl.glob("*.docx") if p.is_file()),
    )
