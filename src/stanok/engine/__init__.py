# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure engine: PJ/AJ/Filling types, resolve, render, XML (no Qt, no Home, no Excel).

Full layer contract: docs/architecture.md.
"""

from .resolve import resolve_rows, ResolveError
from .schema import (
    SchemaError,
    PJValidationError,
    AJValidationError,
    FillingValidationError,
    FormatTooNewError,
    ProjectJSON,
    ApplicationJSON,
    FillingJSON,
    migrate,
    normalize,
    validate_pj,
    validate_aj,
    validate_fj,
)

__all__ = [
    "SchemaError",
    "PJValidationError",
    "AJValidationError",
    "FillingValidationError",
    "FormatTooNewError",
    "ResolveError",
    "ProjectJSON",
    "ApplicationJSON",
    "FillingJSON",
    "MIGRATIONS",
    "migrate",
    "normalize",
    "current_version",
    "validate_pj",
    "validate_aj",
    "validate_fj",
    "resolve_rows",
    "ResolveError",
]
