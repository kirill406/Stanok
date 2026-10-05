# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Table-reading backends: the ONLY place tables are read (Excel now, csv later).

Full layer contract: docs/architecture.md.
"""

from .protocols import TableReader
from .excel import ExcelReader, TableReadError

__all__ = ["TableReader", "ExcelReader", "TableReadError"]
