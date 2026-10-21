# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""PJ/AJ/Filling schemas: validate, normalize, migrate. Pure engine, no Qt."""

import logging
import os
import re
from datetime import datetime
from enum import Enum
from importlib.metadata import version as pkg_version, PackageNotFoundError
from pathlib import PurePosixPath
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..gui.strings import STRINGS

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
        super().__init__(STRINGS.SCH_FORMAT_TOO_NEW.format(version=version))


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


class StorageError(SchemaError):
    def __init__(self, path: str, errors: list[str]):
        self.path = path
        self.errors = errors
        super().__init__(f"Storage failed at {path}: {errors}")


def _format_errors(exc: Exception) -> list:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]


def _check_relative_path(value: str, field: str) -> str:
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(STRINGS.SCH_DIST_TRAVERSAL.format(field=field, value=value))
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
    counter_name: str | None = None  # TABLE: counter ref, required (021)


class CounterDef(_WarnExtra):
    pos: int = 0  # one position: source row (0-based) and printed number
    format: str = "1"  # 020: width 1 | 01 | 001 | 0001 (zero-pad); legacy plain/month still render
    table: str | None = None  # bound source file (021); None = numeric counter
    resume: int = 1  # 1 — pos persists after run; 0 — keep it

    @model_validator(mode="before")
    @classmethod
    def _merge_legacy_position(cls, data: Any) -> Any:
        """Unify pre-unification `last` + `start_row` into one `pos`.

        Legacy PJs kept the printed number and the row cursor separately.
        For a counter with a source the row is primary, for a numeric counter
        the printed number is primary.
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)
        last = data.pop("last", None)
        start = data.pop("start_row", None)
        if "pos" in data:
            return data
        if data.get("table") is None:
            pos = last if last is not None else start
        else:
            pos = start if start is not None else last
        if pos is not None:
            data["pos"] = pos
            logger.debug("counter: merged legacy last/start_row into pos=%s", pos)
        return data

    @field_validator("table")
    @classmethod
    def _relative_counter_table(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _check_relative_path(v, "counters.<name>.table")


class TemplateDef(_WarnExtra):
    file: str
    fields: dict[str, FieldDef] = {}
    limit: int = 0  # 021: per-template document limit; 0 = no limit

    @field_validator("file")
    @classmethod
    def _relative_file(cls, v: str) -> str:
        return _check_relative_path(v, "templates.<name>.file")


class DataSourceDef(_WarnExtra):
    file: str
    mode: str = "sequential"  # sequential | circular | constant

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
    folder: str | None = None  # absolute path with Данные/Шаблоны (020)
    default_template: str = ""  # 021: template for window 1; "" = first template

    @field_validator("folder")
    @classmethod
    def _abs_folder(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not value:
            return None
        if not os.path.isabs(value):
            logger.warning("project folder is not absolute: %s", value)
        return value

    @model_validator(mode="after")
    def _check_relations(self) -> "ProjectJSON":
        names = list(self.templates)
        if not self.default_template and names:
            self.default_template = names[0]
        if self.default_template and self.default_template not in self.templates:
            raise ValueError(
                f"default_template '{self.default_template}' not in templates"
            )
        files = [ds.file for ds in self.data_sources]
        for tname, tdef in self.templates.items():
            for fname, fdef in tdef.fields.items():
                if fdef.source == FieldSource.COUNTER:
                    # 021: a counter field's value must name a defined counter.
                    value = fdef.value
                    if not isinstance(value, str) or value not in self.counters:
                        raise ValueError(
                            f"counter field references unknown counter "
                            f"'{value}': {tname}.{fname}"
                        )
                    continue
                if fdef.source != FieldSource.TABLE:
                    continue
                cname = fdef.counter_name
                if not cname:
                    raise ValueError(
                        f"table field needs counter_name: {tname}.{fname}"
                    )
                cdef = self.counters.get(cname)
                if cdef is None:
                    raise ValueError(
                        f"counter '{cname}' not defined: {tname}.{fname}"
                    )
                if cdef.table is None:
                    raise ValueError(
                        f"counter '{cname}' is not bound to a source: "
                        f"{tname}.{fname}"
                    )
        for cname, cdef in self.counters.items():
            if cdef.table is not None and cdef.table not in files:
                raise ValueError(
                    f"counter '{cname}' table not in data_sources: {cdef.table}"
                )
        bound = {c.table for c in self.counters.values() if c.table}
        for ds in self.data_sources:
            if ds.file not in bound:
                raise ValueError(f"source '{ds.file}' has no bound counter")
        return self


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
    """Return the numeric core; accepts both ``0.2.0-alpha`` and ``0.2.0a0``."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", v.strip())
    if match is None:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


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
    "ResolveError",
    "StorageError",
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
