# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Project storage: atomic save/load, Home migration, recent projects."""

import errno
import fcntl
import json
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from ..engine.schema import (
    ApplicationJSON,
    ProjectJSON,
    RecentItem,
    SchemaError,
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
        self.home_dir = home_dir.resolve()
        self._lock = threading.Lock()
        self._ensure_home()

    def _ensure_home(self) -> None:
        self.home_dir.mkdir(parents=True, exist_ok=True)
        settings_file = self.home_dir / "settings.json"
        if not settings_file.exists():
            default_aj = ApplicationJSON(version="0.0.0", recent=[], settings={})
            self._atomic_write_json(settings_file, default_aj.model_dump(mode="json"))

    def _validate_path(self, path: Path, field: str = "path") -> Path:
        """Validate path: no traversal, must be under home_dir."""
        try:
            resolved = path.resolve()
            # Check for traversal
            if ".." in path.parts:
                raise StorageError(
                    field, [f"path traversal not allowed: {path}"]
                )
            # Must be under home_dir or a subdirectory
            try:
                resolved.relative_to(self.home_dir)
            except ValueError:
                raise StorageError(
                    field, [f"path must be under home directory: {path}"]
                )
            return resolved
        except Exception as e:
            raise StorageError(field, [str(e)])

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Write JSON atomically: tmp -> fsync -> rename + .bak."""
        path = self._validate_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        bak_path = path.with_suffix(path.suffix + ".bak")

        # Write to tmp
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Ensure data is on disk
        with open(tmp_path, "r") as f:
            f.flush()
            os.fsync(f.fileno())

        # Backup existing file
        if path.exists():
            if bak_path.exists():
                bak_path.unlink()
            path.rename(bak_path)

        # Atomic rename
        try:
            tmp_path.rename(path)
        except OSError:
            # Fallback for Windows: copy + unlink
            shutil.copy2(tmp_path, path)
            tmp_path.unlink()

    def _read_json(self, path: Path) -> dict:
        path = self._validate_path(path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _lock_file(self, path: Path, exclusive: bool = True):
        """File locking for concurrent access."""
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_file = open(lock_path, "w")
        try:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
            )
        except OSError:
            pass  # Windows fallback: no locking
        return lock_file

    def _unlock_file(self, lock_file) -> None:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_file.close()

    def _get_config_path(self, name: str) -> Path:
        """Get path for config file in Home."""
        safe_name = name.replace("/", "_").replace("\\", "_")
        return self.home_dir / f"{safe_name}.stanok"

    def save(self, pj: ProjectJSON) -> Path:
        """Save project config atomically, return path."""
        with self._lock:
            path = self._get_config_path(pj.filename_template.split("{")[0].strip() or "project")
            # Use project name from template or fallback
            name = getattr(pj, "_name", None) or "project"
            path = self._get_config_path(name)
            self._atomic_write_json(path, pj.model_dump(mode="json"))
            logger.info("saved project config to %s", path)
            return path

    def load(self, name: str) -> ProjectJSON:
        """Load project config by name."""
        with self._lock:
            path = self._get_config_path(name)
            if not path.exists():
                raise StorageError("load", [f"project not found: {name}"])
            data = self._read_json(path)
            return validate_pj(data)

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
                    data = self._read_json(path)
                    pj = validate_pj(data)
                    configs.append((path.stat().st_mtime, pj))
                except Exception:
                    logger.warning("skipping invalid config: %s", path)
            configs.sort(key=lambda x: x[0], reverse=True)
            return [pj for _, pj in configs]

    def migrate_from_project(self, project_dir: Path) -> ProjectJSON:
        """Migrate project config from project folder to Home."""
        project_dir = self._validate_path(project_dir, "project_dir")
        legacy_config = project_dir / "project.stanok"
        if not legacy_config.exists():
            raise StorageError(
                "migrate", [f"legacy config not found: {legacy_config}"]
            )

        data = self._read_json(legacy_config)
        pj = validate_pj(data)

        # Save to Home with project folder name
        name = project_dir.name
        self.save(pj)

        # Remove legacy config after successful migration
        legacy_config.unlink()
        logger.info("migrated project config from %s", project_dir)
        return pj

    def resolve_project(
        self, ref: str | Path, project_store: "ProjectStore"
    ) -> tuple[ProjectJSON, Path]:
        """Resolve project reference to (PJ, config_path)."""
        ref_path = Path(ref) if isinstance(ref, str) else ref

        # If it's a path to project folder
        if ref_path.exists() and ref_path.is_dir():
            legacy = ref_path / "project.stanok"
            if legacy.exists():
                pj = self.migrate_from_project(ref_path)
                config_path = self._get_config_path(ref_path.name)
                return pj, config_path

        # Try as config name in Home
        config_path = self._get_config_path(ref_path.name)
        if config_path.exists():
            return self.load(ref_path.name), config_path

        # Try to find by folder name in Home
        for pj in self.list():
            # Check if any template path contains this folder name
            if ref_path.name in str(pj.filename_template):
                config_path = self._get_config_path(ref_path.name)
                if config_path.exists():
                    return self.load(ref_path.name), config_path

        raise StorageError("resolve", [f"project not found: {ref}"])

    def get_recent(self) -> list[RecentItem]:
        """Get recent projects from ApplicationJSON."""
        settings_file = self.home_dir / "settings.json"
        if settings_file.exists():
            data = self._read_json(settings_file)
            aj = validate_aj(data)
            return aj.recent
        return []

    def add_recent(self, folder: str, config: str) -> None:
        """Add or update recent project entry."""
        settings_file = self.home_dir / "settings.json"
        with self._lock:
            data = {}
            if (self.home_dir / "settings.json").exists():
                data = self._read_json(self.home_dir / "settings.json")
            aj = validate_aj(data)

            # Remove existing entry with same (folder, config)
            key = (folder, config)
            aj.recent = [r for r in aj.recent if (r.folder, r.config) != key]
            # Add new at front
            aj.recent.insert(0, RecentItem(folder=folder, config=config, opened_at=datetime.now()))
            # Cap at 10
            aj.recent = aj.recent[:10]

            self._atomic_write_json(self.home_dir / "settings.json", aj.model_dump(mode="json"))
            logger.info("updated recent projects, count=%d", len(aj.recent))


def resolve_project(
    ref: str | Path, store: "ProjectStore"
) -> tuple[ProjectJSON, Path]:
    """Convenience function to resolve project reference."""
    return store.resolve_project(ref, store)