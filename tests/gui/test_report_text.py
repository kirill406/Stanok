# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Final generation message formatting."""

from stanok.gui.report_text import done_text
from stanok.gui.strings import STRINGS
from stanok.services.generate import GenerateReport


def test_report_text_full_limit_uses_plain_done():
    report = GenerateReport(created=3, planned=3, limit=3, elapsed=1.0)
    assert done_text(report) == STRINGS.APP_DONE.format(
        created=3, errors=0, elapsed="1.0"
    )


def test_report_text_shortfall_mentions_limit():
    report = GenerateReport(created=2, planned=2, limit=3, elapsed=1.0)
    assert done_text(report) == STRINGS.APP_DONE_SHORT.format(
        created=2, limit=3, errors=0, elapsed="1.0"
    )
    assert "строки закончились" in done_text(report)


def test_report_text_unlimited_uses_plain_done():
    report = GenerateReport(created=2, planned=2, limit=0, elapsed=1.0)
    assert "из 0" not in done_text(report)


def test_report_text_lists_skipped_columns():
    report = GenerateReport(
        created=1,
        planned=1,
        elapsed=1.0,
        skipped_columns={"data.xlsx": ["B", "D"]},
    )
    text = done_text(report)
    assert "data.xlsx" in text
    assert "B, D" in text
