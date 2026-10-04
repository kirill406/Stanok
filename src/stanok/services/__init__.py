# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Use cases, one function per scenario (generate/projects/migrate/storage).

LAYER CONTRACT: depends on engine + storage interfaces only; no Qt widgets,
no argv parsing. Errors are typed (ProjectNotFound, NoData), each carrying
context for logging.
"""
