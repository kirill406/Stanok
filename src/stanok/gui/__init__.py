# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Thin Qt adapter: windows call services, zero business logic.

LAYER CONTRACT: may import services + strings only (engine types for
annotations under TYPE_CHECKING). QMessageBox lives here, never below.
"""
