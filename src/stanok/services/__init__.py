# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Use cases, one function per scenario (depends on engine + storage only).

Full layer contract: docs/architecture.md.
"""

from .generate import GenerateCommand, GenerateReport, generate_documents
from .storage import ProjectStore, resolve_project

__all__ = [
    "GenerateCommand",
    "GenerateReport",
    "ProjectStore",
    "generate_documents",
    "resolve_project",
]
