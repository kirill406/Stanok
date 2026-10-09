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
    ProjectJSON,
    RecentItem,
    StorageError,
    validate_aj,
    validate_pj,
)

logger = logging.getLogger(__name__)


class ProjectStore:
    """Manages project configs in ~/.stanok/ with atomic operations."""

    def __init__(self, home_dir: Path | None = None):
        if home_dir is None:
            home_dir = Path.home() / ".stanok"
        self.home_dir = Path(home_dir).resolve()
        self._lock = threading.Lock()
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
        self.save(pj, name=project_dir.name)
        legacy_config.unlink()
        logger.info("migrated project config from %s", project_dir)
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


def resolve_project(ref: str | Path, store: ProjectStore) -> tuple:
    """Convenience function to resolve project reference."""
    return store.resolve_project(ref)
