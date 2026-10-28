# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project folder preparation and creation from a passed check (024).

create_skeleton / clone_structure prepare folders without a config in Home.
create_project_from_check is the only place that writes a config for them.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..engine.schema import ProjectJSON, StorageError
from ..gui.strings import STRINGS
from .project_check import ProjectCheck, name_problem
from .storage import ProjectStore, project_folder

logger = logging.getLogger(__name__)

PROJECT_SUBDIRS = (STRINGS.DATA_DIR, STRINGS.TPL_DIR, STRINGS.GEN_RESULT_DIR)


def _ensure_name(name: str, store: ProjectStore) -> str:
    problem = name_problem(name, store)
    if problem is not None:
        raise StorageError("init", [problem])
    return name.strip()


def _prepare_folder(folder: Path) -> None:
    """Create the folder; refuse one that already has content (no overwrite)."""
    if folder.exists() and any(folder.iterdir()):
        raise StorageError(
            "init", [STRINGS.PCHK_FOLDER_BUSY.format(path=folder)]
        )
    folder.mkdir(parents=True, exist_ok=True)


def create_skeleton(base: str | Path, name: str, store: ProjectStore) -> Path:
    """Create base/name with Данные, Шаблоны, Результат; no config is written."""
    name = _ensure_name(name, store)
    folder = Path(base).expanduser() / name
    _prepare_folder(folder)
    for sub in PROJECT_SUBDIRS:
        (folder / sub).mkdir(parents=True, exist_ok=True)
    logger.info(f"created project skeleton {folder}")
    return folder


def ensure_subfolders(folder: str | Path) -> list[str]:
    """Create missing Данные/Шаблоны inside an existing folder; return created names."""
    root = Path(folder)
    created: list[str] = []
    for sub in (STRINGS.DATA_DIR, STRINGS.TPL_DIR):
        target = root / sub
        if not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            created.append(sub)
    logger.info(f"ensured subfolders in {root}: created={created}")
    return created


def clone_structure(
    source: str, base: str | Path, name: str, store: ProjectStore
) -> Path:
    """Copy Шаблоны and Данные of a stored project into base/name; no config."""
    name = _ensure_name(name, store)
    pj, config_path = store.resolve_project(source)
    src_root = project_folder(source, pj, config_path, store)
    folder = Path(base).expanduser() / name
    _prepare_folder(folder)
    try:
        for sub in (STRINGS.DATA_DIR, STRINGS.TPL_DIR):
            if (src_root / sub).is_dir():
                shutil.copytree(src_root / sub, folder / sub)
            else:
                (folder / sub).mkdir(parents=True)
        (folder / STRINGS.GEN_RESULT_DIR).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"clone {src_root} -> {folder}: {e}", exc_info=True)
        raise StorageError(
            "init", [STRINGS.PCHK_CREATE_FAILED.format(cause=e)]
        ) from e
    logger.info(f"cloned project structure {src_root} -> {folder}")
    return folder


def create_project_from_check(
    store: ProjectStore, folder: str | Path, name: str, check: ProjectCheck
) -> ProjectJSON:
    """Write the project config for a folder whose check has no errors.

    Files stay where they are (copy_files=False); the result folder is created
    if missing.
    """
    if not check.ok:
        raise StorageError(
            "init", [check.errors[0].message if check.errors else ""]
        )
    root = Path(folder).resolve()
    (root / STRINGS.GEN_RESULT_DIR).mkdir(parents=True, exist_ok=True)
    xlsx = [root / rel for rel in check.xlsx]
    docx = [root / rel for rel in check.docx]
    return store.init_project(root, name.strip(), xlsx, docx, copy_files=False)
