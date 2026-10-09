# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Development and PyInstaller entry point (thin wrapper, no logic here)."""

import sys
from pathlib import Path

# Make `src/` importable without installing the package (dev convenience;
# PyInstaller build uses `--paths src` for the same purpose).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from stanok.app import main

if __name__ == "__main__":
    raise SystemExit(main())
