# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""PJ/AJ/Filling schemas: validate, normalize, migrate. Pure engine, no Qt."""

import logging
from datetime import datetime
from enum import Enum
from importlib.metadata import version as pkg_version, PackageNotFoundError
from pathlib import PurePosixPath
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class SchemaError(Exception):
    """Base error of the schema layer (carries context for logging)."""


class PJValidationError(SchemaError):
    def __init__(self, path: str, errors: list):
        self.path = path
        self.errors = errors
        super().__init__(f"PJ validation failed at {path}: {errors}")


class FillingValidationError(SchemaError):
    def __init__(self, path: str, errors: list):
        self.path = path
        self.errors = errors
        super().__init__(f"Filling validation failed at {path}: {errors}")


class FormatTooNewError(SchemaError):
    def __init__(self, version: str):
        self.version = version
        super().__init__(f"Формат версии {version} новее программы — обновите программу")


class ResolveError(SchemaError):
    def __init__(self, path: str, errors: list[str]):
        self.path = path
        self.errors = errors
        super().__init__(f"Resolve failed at {path}: {errors}")


class AJValidationError(SchemaError):
    def __init__(self, path: str, errors: list[str]):
        self.path = path
        self.errors = errors
        super().__init__(f"AJ validation failed at {path}: {errors}")


class RenderError(SchemaError):
    def __init__(self, path: str, errors: list[str]):
        self.path = path
        self.errors = errors
        super().__init__(f"Render failed at {path}: {errors}")


def _format_errors(exc: Exception) -> list:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]


def _check_relative_path(value: str, field: str) -> str:
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{field}: путь должен быть относительным без '..': {value}")
    return value


class _WarnExtra(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _warn_unknown(self) -> "_WarnExtra":
        allowed = set(type(self).model_fields)
        unknown = [k for k in self.__pydantic_extra__ or {} if k not in allowed]
        if unknown:
            logger.warning("unknown keys ignored: %s", unknown)
        return self


class FieldSource(str, Enum):
    CONSTANT = "constant"
    TABLE = "table"
    COUNTER = "counter"
    TODAY = "today"


class FieldDef(_WarnExtra):
    source: FieldSource
    value: Any = None


class CounterDef(_WarnExtra):
    last: int = 0
    format: str = "plain"  # plain | month (ГГГГ-ММ-###)


class TemplateDef(_WarnExtra):
    file: str
    fields: dict[str, FieldDef] = {}

    @field_validator("file")
    @classmethod
    def _relative_file(cls, v: str) -> str:
        return _check_relative_path(v, "templates.<name>.file")


class DataSourceDef(_WarnExtra):
    file: str
    mode: str = "sequential"  # sequential | circular | constant
    start_row: int = 0  # > 0 означает «продолжать» (resume без отдельного флага)

    @field_validator("file")
    @classmethod
    def _relative_file(cls, v: str) -> str:
        return _check_relative_path(v, "data_sources.file")


class ProjectJSON(_WarnExtra):
    version: str
    templates: dict[str, TemplateDef]
    data_sources: list[DataSourceDef] = []
    counters: dict[str, CounterDef] = {}
    filename_template: str = "{template} ({i})"


class RecentItem(_WarnExtra):
    folder: str
    config: str
    opened_at: datetime


class ApplicationJSON(_WarnExtra):
    version: str
    recent: list[RecentItem] = []
    settings: dict[str, Any] = {}

    @field_validator("recent")
    @classmethod
    def _cap_recent(cls, v: list[RecentItem]) -> list[RecentItem]:
        ordered: list[RecentItem] = []
        for item in v:
            key = (item.folder, item.config)
            ordered = [x for x in ordered if (x.folder, x.config) != key]
            ordered.append(item)  # повторное открытие двигает запись наверх
        return list(reversed(ordered))[:10]


class FillingJSON(_WarnExtra):
    version: str
    template: str
    fields: dict[str, Any] = {}
    dist: str = ""  # resolved путь результата, относительный

    @field_validator("dist")
    @classmethod
    def _relative_dist(cls, v: str) -> str:
        return _check_relative_path(v, "dist") if v else v


def _get_package_version() -> str:
    """Read package version from installed metadata (no circular import)."""
    try:
        return pkg_version("stanok")
    except PackageNotFoundError:
        return "0.0.0"


def _parse_version(v: str) -> tuple:
    core = v.split("-", 1)[0]
    return tuple(int(p) for p in core.split("."))


def current_version() -> str:
    """Public API: current package version."""
    return _get_package_version()


MIGRATIONS: dict[tuple[str, str], Callable[[dict], dict]] = {}


def migrate(data: dict) -> dict:
    """Цепочка миграций к current_version()."""
    version = data.get("version", "0.0.0")
    target = _get_package_version()
    if _parse_version(version) > _parse_version(target):
        raise FormatTooNewError(version)
    while version != target:
        step = next((MIGRATIONS[k] for k in MIGRATIONS if k[0] == version), None)
        if step is None:
            raise FormatTooNewError(version)
        data = step(dict(data))
        new_version = data.get("version", target)
        if new_version == version:
            raise SchemaError(f"Migration {version}→{new_version} didn't update version")
        version = new_version
    return data


def normalize(raw: dict) -> dict:
    """Дефолты/trim до валидации: рекурсивный strip строк, tuple→list."""
    if isinstance(raw, dict):
        return {k: normalize(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [normalize(v) for v in raw]
    if isinstance(raw, tuple):
        return [normalize(v) for v in raw]
    if isinstance(raw, str):
        return raw.strip()
    return raw


def validate_pj(data: dict) -> ProjectJSON:
    try:
        return ProjectJSON(**normalize(data))
    except Exception as e:
        from pydantic import ValidationError

        if isinstance(e, ValidationError):
            raise PJValidationError("$", _format_errors(e)) from e
        logger.error(f"validate PJ: {e}", exc_info=True)
        raise


def validate_aj(data: dict) -> ApplicationJSON:
    try:
        return ApplicationJSON(**normalize(data))
    except Exception as e:
        from pydantic import ValidationError

        if isinstance(e, ValidationError):
            raise AJValidationError("$", _format_errors(e)) from e
        logger.error(f"validate AJ: {e}", exc_info=True)
        raise


def validate_fj(data: dict) -> FillingJSON:
    try:
        return FillingJSON(**normalize(data))
    except Exception as e:
        from pydantic import ValidationError

        if isinstance(e, ValidationError):
            raise FillingValidationError("$", _format_errors(e)) from e
        logger.error(f"validate FJ: {e}", exc_info=True)
        raise


__all__ = [
    "SchemaError",
    "PJValidationError",
    "AJValidationError",
    "FillingValidationError",
    "FormatTooNewError",
    "RenderError",
    "FieldSource",
    "FieldDef",
    "CounterDef",
    "TemplateDef",
    "DataSourceDef",
    "ProjectJSON",
    "RecentItem",
    "ApplicationJSON",
    "FillingJSON",
    "MIGRATIONS",
    "migrate",
    "normalize",
    "current_version",
    "validate_pj",
    "validate_aj",
    "validate_fj",
]
