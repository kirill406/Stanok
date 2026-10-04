# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure engine: PJ/AJ/Filling types, tables, resolve, render, XML.

LAYER CONTRACT: no Qt, no dialogs, no Home paths, no direct Excel reads
(tables come from ``stanok.tables`` backends injected by callers).
See FirstAgent docs/rebrending/layers.md.
"""
