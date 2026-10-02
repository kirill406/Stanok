# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Allow `python -m stanok` (requires `src` on PYTHONPATH)."""

from stanok.app import main

if __name__ == "__main__":
    main()
