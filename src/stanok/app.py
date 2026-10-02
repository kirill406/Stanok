# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap (CLI/GUI startup lives here, not in __init__)."""

import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Program entry point (stub until GUI lands)."""
    logging.basicConfig(level=logging.INFO)
    logger.info("stanok started")
