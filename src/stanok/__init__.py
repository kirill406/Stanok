# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""stanok: generate docx documents from templates and Excel data."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: version lives in pyproject.toml only.
    __version__ = version("stanok")
except PackageNotFoundError:  # pragma: no cover - installed in practice
    __version__ = "0.0.0"
