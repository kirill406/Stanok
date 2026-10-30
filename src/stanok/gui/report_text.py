# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Final generation message formatting (no Qt)."""

from __future__ import annotations

from stanok.services.generate import GenerateReport

from .strings import STRINGS


def done_text(report: GenerateReport) -> str:
    """Final run message; notes when the data ended before the template limit."""
    if report.limit == 0 and report.planned == 0:
        text = STRINGS.APP_DONE_NO_LIMIT.format(
            errors=len(report.errors),
            elapsed=f"{report.elapsed:.1f}",
        )
    elif report.limit and report.planned < report.limit:
        text = STRINGS.APP_DONE_SHORT.format(
            created=report.created,
            limit=report.limit,
            errors=len(report.errors),
            elapsed=f"{report.elapsed:.1f}",
        )
    else:
        text = STRINGS.APP_DONE.format(
            created=report.created,
            errors=len(report.errors),
            elapsed=f"{report.elapsed:.1f}",
        )
    if report.skipped_columns:
        items = "\n".join(
            f"{file}: {', '.join(columns)}"
            for file, columns in report.skipped_columns.items()
        )
        text += "\n\n" + STRINGS.GEN_SKIPPED_COLUMNS.format(items=items)
    return text
