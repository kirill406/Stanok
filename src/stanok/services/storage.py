# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project storage: atomic save/load, Home migration, recent projects."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from ..engine.schema import (
    ApplicationJSON,
    FieldDef,
    FieldSource,
    ProjectJSON,
    RecentItem,
    StorageError,
    TemplateDef,
    validate_aj,
    validate_pj,
)
from ..engine.xmlops import PLACEHOLDER_RE
from ..gui.strings import STRINGS

logger = logging.getLogger(__name__)


def project_folder(
    ref: str | Path, pj: ProjectJSON, config_path: Path, store: ProjectStore
) -> Path:
    """Find project folder: direct dir ref, else AJ recent lookup by config."""
    ref_path = Path(ref) if isinstance(ref, str) else ref
    if ref_path.exists() and ref_path.is_dir():
        return ref_path.resolve()
    # Config-name ref: folder remembered in recent projects.
    for item in store.get_recent():
        if item.config == ref_path.name or item.config == config_path.stem:
            folder = Path(item.folder)
            if folder.is_dir():
                return folder.resolve()
    raise StorageError(
        "resolve",
        [f"project folder not found for '{ref}': pass a project folder path"],
    )


def _scan_placeholders(docx_path: Path) -> list[str]:
    """Ordered unique {{name}} placeholders from docx paragraphs + tables."""
    from docx import Document

    try:
        doc = Document(str(docx_path))
    except Exception as e:
        logger.warning(f"unreadable template {docx_path}: {e}", exc_info=True)
        raise StorageError(
            "init", [f"cannot read template {docx_path.name}: {e}"]
        ) from e
    blocks = list(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                blocks.extend(cell.paragraphs)
    names: list[str] = []
    for p in blocks:
        for m in PLACEHOLDER_RE.finditer(p.text):
            name = m.group(1).strip()
            if name and name not in names:
                names.append(name)
    return names


def _unique_sibling(path: Path) -> Path:
    """Return path or first free `stem (1).suffix` sibling."""
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


class ProjectStore:
    """Manages project configs in ~/.stanok/ with atomic operations."""

    def __init__(self, home_dir: Path | None = None):
        if home_dir is None:
            home_dir = Path.home() / ".stanok"
        self.home_dir = Path(home_dir).resolve()
        # RLock: init_project re-enters via save()/add_recent().
        self._lock = threading.RLock()
        self._ensure_home()

    def _ensure_home(self) -> None:
        self.home_dir.mkdir(parents=True, exist_ok=True)
        settings_file = self.home_dir / "settings.json"
        if not settings_file.exists():
            default_aj = ApplicationJSON(version="0.0.0", recent=[], settings={})
            self._atomic_write_json(
                settings_file, default_aj.model_dump(mode="json")
            )

    def _validate_path(self, path: Path, field: str = "path") -> Path:
        """Validate path: no traversal, must be under home_dir."""
        if ".." in path.parts:
            raise StorageError(field, [f"path traversal not allowed: {path}"])
        resolved = path.resolve()
        try:
            resolved.relative_to(self.home_dir)
        except ValueError:
            raise StorageError(
                field, [f"path must be under home directory: {path}"]
            )
        return resolved

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Write JSON atomically: tmp + fsync -> backup + rename."""
        path = self._validate_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        bak_path = path.with_suffix(path.suffix + ".bak")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

        if path.exists():
            if bak_path.exists():
                bak_path.unlink()
            path.rename(bak_path)

        try:
            tmp_path.rename(path)
        except OSError as e:
            logger.warning(f"atomic rename failed for {path}: {e}", exc_info=True)
            shutil.copy2(tmp_path, path)
            tmp_path.unlink()

    def _read_json(self, path: Path) -> dict:
        path = self._validate_path(path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_config_path(self, name: str) -> Path:
        """Get path for config file in Home."""
        safe_name = name.replace("/", "_").replace("\\", "_")
        if not safe_name:
            safe_name = "project"
        return self.home_dir / f"{safe_name}.stanok"

    def _extract_project_name(self, pj: ProjectJSON) -> str:
        """Extract project name from PJ or use fallback."""
        template = pj.filename_template or ""
        name = template.split("{")[0].strip()
        if name:
            return name.replace("/", "_").replace("\\", "_")
        if pj.templates:
            first_template = next(iter(pj.templates.values()))
            file = getattr(first_template, "file", "")
            if file:
                stem = Path(file).stem
                if stem:
                    return stem
        return "project"

    def save(self, pj: ProjectJSON, name: str | None = None) -> Path:
        """Save project config atomically, return path."""
        with self._lock:
            path = self._get_config_path(name or self._extract_project_name(pj))
            self._atomic_write_json(path, pj.model_dump(mode="json"))
            logger.info("saved project config to %s", path)
            return path

    def load(self, name: str) -> ProjectJSON:
        """Load project config by name."""
        with self._lock:
            path = self._get_config_path(name)
            if not path.exists():
                raise StorageError("load", [f"project not found: {name}"])
            try:
                return validate_pj(self._read_json(path))
            except StorageError:
                raise
            except Exception as e:
                logger.error(f"load config {path}: {e}", exc_info=True)
                raise StorageError("load", [f"invalid config {name}: {e}"]) from e

    def delete(self, name: str) -> None:
        """Delete project config and backup."""
        with self._lock:
            path = self._get_config_path(name)
            bak_path = path.with_suffix(path.suffix + ".bak")
            if path.exists():
                path.unlink()
            if bak_path.exists():
                bak_path.unlink()
            logger.info("deleted project config %s", name)

    def list(self) -> list[ProjectJSON]:
        """List all project configs sorted by mtime (newest first)."""
        with self._lock:
            configs = []
            for path in self.home_dir.glob("*.stanok"):
                try:
                    pj = validate_pj(self._read_json(path))
                    configs.append((path.stat().st_mtime, pj))
                except Exception as e:
                    logger.warning(f"skipping invalid config {path}: {e}")
            configs.sort(key=lambda x: x[0], reverse=True)
            return [pj for _, pj in configs]

    def _unique_config_name(self, base: str) -> str:
        """Free config stem: base, base (1), base (2), ... (§5.3 spec.md)."""
        if not self._get_config_path(base).exists():
            return base
        i = 1
        while True:
            candidate = f"{base} ({i})"
            if not self._get_config_path(candidate).exists():
                return candidate
            i += 1

    def migrate_from_project(self, project_dir: Path) -> ProjectJSON:
        """Migrate project config from project folder to Home."""
        if ".." in project_dir.parts:
            raise StorageError(
                "migrate", [f"path traversal not allowed: {project_dir}"]
            )
        legacy_config = project_dir.resolve() / "project.stanok"
        if not legacy_config.exists():
            raise StorageError(
                "migrate", [f"legacy config not found: {legacy_config}"]
            )
        with open(legacy_config, "r", encoding="utf-8") as f:
            pj = validate_pj(json.load(f))
        name = self._unique_config_name(project_dir.resolve().name)
        self.save(pj, name=name)
        legacy_config.unlink()
        logger.info("migrated project config from %s as %s", project_dir, name)
        return pj

    def resolve_project(self, ref: str | Path) -> tuple[ProjectJSON, Path]:
        """Resolve project reference to (PJ, config_path)."""
        ref_path = Path(ref) if isinstance(ref, str) else ref

        if ref_path.exists() and ref_path.is_dir():
            legacy = ref_path / "project.stanok"
            if legacy.exists():
                pj = self.migrate_from_project(ref_path)
                return pj, self._get_config_path(ref_path.resolve().name)

        config_path = self._get_config_path(ref_path.name)
        if config_path.exists():
            return self.load(ref_path.name), config_path

        raise StorageError("resolve", [f"project not found: {ref}"])

    def get_recent(self) -> list[RecentItem]:
        """Get recent projects from ApplicationJSON."""
        settings_file = self.home_dir / "settings.json"
        if settings_file.exists():
            return validate_aj(self._read_json(settings_file)).recent
        return []

    def add_recent(self, folder: str, config: str) -> None:
        """Add or update recent project entry (dedupe, cap 10)."""
        with self._lock:
            settings_file = self.home_dir / "settings.json"
            data = self._read_json(settings_file) if settings_file.exists() else {}
            aj = validate_aj(data)
            key = (folder, config)
            aj.recent = [r for r in aj.recent if (r.folder, r.config) != key]
            # Append at end (file order oldest-first; validator reverses on read)
            aj.recent.append(
                RecentItem(
                    folder=folder, config=config, opened_at=datetime.now()
                )
            )
            aj.recent = aj.recent[-10:]
            self._atomic_write_json(
                self.home_dir / "settings.json", aj.model_dump(mode="json")
            )
            logger.info("updated recent projects, count=%d", len(aj.recent))


    def init_project(
        self,
        folder: str | Path,
        name: str,
        xlsx: list[str | Path],
        docx: list[str | Path],
        copy_files: bool = True,
    ) -> ProjectJSON:
        """Create project folder with Данные/Шаблоны + PJ from files (FR-12).

        copy_files=True copies sources into the folder (unique names on
        collision); False only links files already inside Данные/Шаблоны.
        Template fields default to table source named as the placeholder.
        """
        with self._lock:
            name = (name or "").strip()
            if not name or "/" in name or "\\" in name or name in (".", ".."):
                raise StorageError("init", [f"invalid project name: {name!r}"])
            if self._get_config_path(name).exists():
                raise StorageError("init", [f"project already exists: {name}"])
            if not xlsx:
                raise StorageError("init", ["no Excel files selected"])
            if not docx:
                raise StorageError("init", ["no Word templates selected"])

            folder = Path(folder).resolve()
            data_dir = folder / STRINGS.DATA_DIR
            tpl_dir = folder / STRINGS.TPL_DIR
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
                tpl_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"cannot create project folder {folder}: {e}")
                raise StorageError(
                    "init", [f"cannot create folder {folder}: {e}"]
                ) from e

            rel_xlsx = [
                self._place_source(Path(f), data_dir, folder, ".xlsx", copy_files)
                for f in xlsx
            ]
            templates: dict[str, dict] = {}
            for f in docx:
                rel = self._place_source(
                    Path(f), tpl_dir, folder, ".docx", copy_files
                )
                stem = Path(rel).stem
                base, i = stem, 1
                while stem in templates:
                    i += 1
                    stem = f"{base} ({i})"
                placeholders = _scan_placeholders(folder / rel)
                templates[stem] = {
                    "file": rel,
                    "fields": {
                        ph: {"source": "table", "value": ph} for ph in placeholders
                    },
                }

            pj = validate_pj(
                {
                    "version": "0.0.0",
                    "templates": templates,
                    "data_sources": [
                        {"file": r, "mode": "sequential", "start_row": 0}
                        for r in rel_xlsx
                    ],
                    "counters": {},
                    "filename_template": "{template}_{i}",
                }
            )
            self.save(pj, name=name)
            self.add_recent(str(folder), name)
            logger.info("initialized project %s in %s", name, folder)
            return pj

    def _place_source(
        self,
        src: Path,
        dest_dir: Path,
        folder: Path,
        suffix: str,
        copy_files: bool,
    ) -> str:
        """Copy (or link in place) one source file; return PJ-relative posix path."""
        if src.suffix.lower() != suffix:
            raise StorageError(
                "init", [f"wrong file type {src.name}: expected *{suffix}"]
            )
        if copy_files:
            if not src.is_file():
                raise StorageError("init", [f"file not found: {src}"])
            try:
                dst = _unique_sibling(dest_dir / src.name)
                shutil.copy2(src, dst)
            except OSError as e:
                logger.warning(f"copy {src} -> {dest_dir} failed: {e}")
                raise StorageError(
                    "init", [f"cannot copy {src.name}: {e}"]
                ) from e
            return dst.relative_to(folder).as_posix()
        resolved = src.resolve()
        try:
            rel = resolved.relative_to(folder)
        except ValueError:
            raise StorageError(
                "init", [f"file outside project folder: {src}"]
            ) from None
        if rel.parts[0] != dest_dir.name:
            raise StorageError(
                "init", [f"file must be in {dest_dir.name}/: {src}"]
            )
        if not resolved.is_file():
            raise StorageError("init", [f"file not found: {src}"])
        return rel.as_posix()


    def remove_recent(self, folder: str, config: str) -> None:
        """Remove one recent project entry (no-op when absent)."""
        with self._lock:
            settings_file = self.home_dir / "settings.json"
            data = self._read_json(settings_file) if settings_file.exists() else {}
            aj = validate_aj(data)
            aj.recent = [
                r
                for r in aj.recent
                if (r.folder, r.config) != (folder, config)
            ]
            self._atomic_write_json(
                self.home_dir / "settings.json", aj.model_dump(mode="json")
            )
            logger.info("removed recent project %s", config)

    def get_setting(self, key: str, default=None):
        """Read one AJ setting (018)."""
        settings_file = self.home_dir / "settings.json"
        if not settings_file.exists():
            return default
        try:
            data = self._read_json(settings_file)
            return validate_aj(data).settings.get(key, default)
        except Exception as e:
            logger.warning(f"read setting {key} failed: {e}", exc_info=True)
            return default

    def set_setting(self, key: str, value) -> None:
        """Write one AJ setting atomically (018)."""
        with self._lock:
            settings_file = self.home_dir / "settings.json"
            data = self._read_json(settings_file) if settings_file.exists() else {}
            aj = validate_aj(data)
            aj.settings[key] = value
            self._atomic_write_json(
                self.home_dir / "settings.json", aj.model_dump(mode="json")
            )
            logger.info("updated setting %s", key)

    def add_template(
        self, ref: str | Path, docx: str | Path, copy_files: bool = True
    ) -> str:
        """Attach a docx template to the project (FR-13); return its name."""
        with self._lock:
            pj, config_path = self.resolve_project(ref)
            folder = project_folder(ref, pj, config_path, self)
            tpl_dir = folder / STRINGS.TPL_DIR
            try:
                tpl_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"cannot create templates dir {tpl_dir}: {e}")
                raise StorageError(
                    "templates", [f"cannot create folder {tpl_dir}: {e}"]
                ) from e
            rel = self._place_source(
                Path(docx), tpl_dir, folder, ".docx", copy_files
            )
            stem = Path(rel).stem
            base, i = stem, 1
            while stem in pj.templates:
                i += 1
                stem = f"{base} ({i})"
            placeholders = _scan_placeholders(folder / rel)
            pj.templates[stem] = TemplateDef(
                file=rel,
                fields={
                    ph: FieldDef(source=FieldSource.TABLE, value=ph)
                    for ph in placeholders
                },
            )
            self.save(pj, name=config_path.stem)
            logger.info("attached template %s to %s", stem, config_path.stem)
            return stem

    def remove_template(self, ref: str | Path, name: str) -> None:
        """Detach a template; removing the last one is forbidden (FR-13)."""
        with self._lock:
            pj, config_path = self.resolve_project(ref)
            if name not in pj.templates:
                raise StorageError(
                    "templates", [f"template not found: {name}"]
                )
            if len(pj.templates) == 1:
                raise StorageError(
                    "templates",
                    ["cannot remove last template: project needs at least one"],
                )
            del pj.templates[name]
            self.save(pj, name=config_path.stem)
            logger.info("removed template %s from %s", name, config_path.stem)

    def delete_project(self, ref: str | Path, delete_folder: bool = False) -> None:
        """Delete project config + recent entry; folder only on flag (FR-13)."""
        with self._lock:
            pj, config_path = self.resolve_project(ref)
            try:
                folder = project_folder(ref, pj, config_path, self)
            except StorageError:
                folder = None
            if delete_folder and folder == self.home_dir:
                raise StorageError(
                    "delete", ["refusing to delete home directory"]
                )
            self.delete(config_path.stem)
            if folder is not None:
                self.remove_recent(str(folder), config_path.stem)
            if delete_folder and folder is not None:
                if folder.exists():
                    try:
                        shutil.rmtree(folder)
                    except OSError as e:
                        logger.warning(f"rmtree {folder} failed: {e}")
                        raise StorageError(
                            "delete",
                            [f"config deleted, folder partially removed: {e}"],
                        ) from e
            logger.info("deleted project %s", config_path.stem)


def resolve_project(ref: str | Path, store: ProjectStore) -> tuple:
    """Convenience function to resolve project reference."""
    return store.resolve_project(ref)
