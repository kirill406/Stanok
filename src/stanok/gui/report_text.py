# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Final generation message formatting (no Qt)."""

from __future__ import annotations

from stanok.services.generate import GenerateReport

from .strings import STRINGS


def done_text(report: GenerateReport) -> str:
    """Final run message; notes when the data ended before the template limit."""
    if report.limit and report.planned < report.limit:
        return STRINGS.APP_DONE_SHORT.format(
            created=report.created,
            limit=report.limit,
            errors=len(report.errors),
            elapsed=f"{report.elapsed:.1f}",
        )
    return STRINGS.APP_DONE.format(
        created=report.created,
        errors=len(report.errors),
        elapsed=f"{report.elapsed:.1f}",
    )
