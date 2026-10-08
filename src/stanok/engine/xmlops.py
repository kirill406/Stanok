# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Low-level docx XML ops: run-merge substitution, line breaks, tables."""

import logging
import re
from bisect import bisect_right
from copy import deepcopy
from typing import Any

from docx.text.paragraph import Paragraph

from .schema import RenderError

logger = logging.getLogger(__name__)

PLACEHOLDER_RE = re.compile(r"\{\{\s*([^}{]+?)\s*\}\}")
UNCLOSED_RE = re.compile(r"\{\{(?![^}]*\}\})")


def _stringify(value: Any) -> str:
    from datetime import date, datetime

    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value)
    return str(value)


def _copy_rpr(src_run, dst_run) -> None:
    src_rpr = src_run._r.rPr
    if src_rpr is None:
        return
    dst_rpr = dst_run._r.get_or_add_rPr()
    for child in src_rpr:
        dst_rpr.append(deepcopy(child))


def _add_text(paragraph: Paragraph, text: str, fmt_run) -> None:
    """Add text, turning \\n into real line breaks (w:br)."""
    for i, chunk in enumerate(text.split("\n")):
        if i:
            paragraph.add_run().add_break()
            # fmt of break run does not matter; keep paragraph flow
        if chunk:
            run = paragraph.add_run(chunk)
            _copy_rpr(fmt_run, run)


def substitute_paragraph(paragraph: Paragraph, mapping: dict[str, str]) -> None:
    """Replace {{ name }} in paragraph, merging runs, keeping formatting."""
    runs = list(paragraph.runs)
    if not runs:
        return
    full = "".join(r.text for r in runs)
    matches = list(PLACEHOLDER_RE.finditer(full))
    leftovers = PLACEHOLDER_RE.findall(full)
    unknown = [m for m in leftovers if m.strip() not in mapping]
    if unknown:
        raise RenderError(
            f"fields.{unknown[0].strip()}",
            [f"unknown placeholder '{{{{{unknown[0].strip()}}}}}'"],
        )
    if UNCLOSED_RE.search(full):
        raise RenderError("template", ["unclosed '{{' without '}}'"])
    if not matches:
        return

    # Offsets of each run in the joined text.
    offsets: list[int] = []
    pos = 0
    for r in runs:
        offsets.append(pos)
        pos += len(r.text)

    def run_at(char_pos: int) -> int:
        return bisect_right(offsets, char_pos) - 1

    # Build (text, formatting-run) segments.
    segments: list[tuple[str, Any]] = []
    cursor = 0
    for m in matches:
        name = m.group(1).strip()
        if m.start() > cursor:
            segments.append((full[cursor : m.start()], runs[run_at(cursor)]))
        segments.append((_stringify(mapping[name]), runs[run_at(m.start())]))
        cursor = m.end()
    if cursor < len(full):
        segments.append((full[cursor:], runs[run_at(cursor)]))

    # Rebuild runs: clear first (keeps pPr), then re-add with formatting.
    p_element = paragraph._p
    for r in runs:
        p_element.remove(r._r)
    for text, fmt_run in segments:
        _add_text(paragraph, text, fmt_run)
