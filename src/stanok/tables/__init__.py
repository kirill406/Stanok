# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Table-reading backends: the ONLY place Excel (later csv/…) is read.

LAYER CONTRACT: backend functions take explicit file paths and return
plain rows; Home/project layout knowledge lives in services/storage.
"""
