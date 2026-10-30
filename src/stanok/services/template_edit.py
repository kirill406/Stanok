# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Text editing of a template .docx (027): read a paragraph, write its new text.

Only the text changes. The new text is matched against the old one by
characters: unchanged characters keep their run, inserted characters take the
run formatting of the neighbouring text. Runs without text (pictures) stay in
place. A paragraph with a hyperlink or a tracked change is refused.
"""

from __future__ import annotations

import difflib
import logging
import os
import shutil
from copy import deepcopy
from pathlib import Path

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .template_layout import Layout, iter_run_elements, layout_of, open_document, run_chars

logger = logging.getLogger(__name__)

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
PAGE_BREAK = "\f"
_UNSUPPORTED = {
    qn("w:hyperlink"),
    qn("w:ins"),
    qn("w:del"),
    qn("w:smartTag"),
    qn("w:fldSimple"),
}


class TemplateEditError(Exception):
    """The text cannot be edited or the template cannot be saved; the message is user-facing."""


def is_editable(p_el) -> bool:
    """False for a paragraph with a hyperlink, a tracked change or a Word field."""
    return not any(child.tag in _UNSUPPORTED for child in p_el)


def paragraph_text(p_el) -> str:
    """Plain text of a paragraph: \\n for a line break, \\t for a tab, \\f for a page break."""
    return "".join(ch for run in iter_run_elements(p_el) for ch in run_chars(run))


def set_paragraph_text(p_el, text: str) -> bool:
    """Replace the paragraph text; True if it changed. Raises TemplateEditError if refused."""
    if not is_editable(p_el):
        raise TemplateEditError("paragraph has a hyperlink or a tracked change")
    old_units = [
        (ch, run) for run in p_el if run.tag == qn("w:r") for ch in run_chars(run)
    ]
    old = "".join(ch for ch, _ in old_units)
    if old == text:
        return False
    units = _merge(old_units, text)
    runs = _runs_of(units)  # built first: they copy the formatting of the old runs
    _replace_runs(p_el, runs)
    logger.debug(f"paragraph text changed: {len(old)} -> {len(text)} characters")
    return True


def _merge(old_units: list, text: str) -> list:
    """(char, source run) for every character of the new text."""
    old = "".join(ch for ch, _ in old_units)
    matcher = difflib.SequenceMatcher(None, old, text, autojunk=False)
    units: list = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            units.extend(old_units[i1:i2])
        elif j2 > j1:  # insert or replace: formatting of the left neighbour
            source = _neighbour(old_units, i1)
            units.extend((ch, source) for ch in text[j1:j2])
    return units


def _neighbour(old_units: list, index: int):
    if index > 0:
        return old_units[index - 1][1]
    if old_units:
        return old_units[0][1]
    return None


def _runs_of(units: list) -> list:
    """New w:r elements, one per run of identical source formatting."""
    runs = []
    segment: list[str] = []
    source = None
    started = False
    for ch, run in units:
        if started and run is not source:
            runs.append(_new_run(source, segment))
            segment = []
        source = run
        started = True
        segment.append(ch)
    if started:
        runs.append(_new_run(source, segment))
    return runs


def _new_run(source, chars: list[str]):
    run = OxmlElement("w:r")
    if source is not None:
        rpr = source.find(qn("w:rPr"))
        if rpr is not None:
            run.append(deepcopy(rpr))
    text = ""
    for ch in chars:
        if ch in ("\n", "\t", PAGE_BREAK):
            if text:
                run.append(_text(text))
                text = ""
            run.append(_break(ch))
        else:
            text += ch
    if text:
        run.append(_text(text))
    return run


def _text(value: str):
    element = OxmlElement("w:t")
    element.text = value
    element.set(XML_SPACE, "preserve")
    return element


def _break(ch: str):
    if ch == "\t":
        return OxmlElement("w:tab")
    element = OxmlElement("w:br")
    if ch == PAGE_BREAK:
        element.set(qn("w:type"), "page")
    return element


def _replace_runs(p_el, runs: list) -> None:
    """Put the new runs where the first text run was; drop the old text runs."""
    children = list(p_el)
    text_runs = [c for c in children if c.tag == qn("w:r") and any(True for _ in run_chars(c))]
    index = children.index(text_runs[0]) if text_runs else len(children)
    for old in text_runs:
        p_el.remove(old)
    for offset, run in enumerate(runs):
        p_el.insert(index + offset, run)


class TemplateDocument:
    """An open template: the layout, text edits in memory, and the save to disk."""

    def __init__(self, path: Path, doc) -> None:
        self.path = path
        self.doc = doc
        self.dirty = False

    @classmethod
    def load(cls, path: Path) -> TemplateDocument:
        """Open a template file; TemplateLayoutError if it cannot be read."""
        return cls(path, open_document(path))

    def layout(self) -> Layout:
        return layout_of(self.doc, self.path)

    def set_paragraph_text(self, element, text: str) -> bool:
        """Apply a text edit of one paragraph; True if it changed the document."""
        changed = set_paragraph_text(element, text)
        if changed:
            self.dirty = True
        return changed

    def save(self) -> None:
        """Write the document: the old file goes to `<name>.bak`, the new one replaces it."""
        tmp = self.path.with_name(self.path.name + ".tmp")
        bak = self.path.with_name(self.path.name + ".bak")
        try:
            self.doc.save(str(tmp))
            if self.path.exists():
                shutil.copy2(self.path, bak)
            os.replace(tmp, self.path)
        except (OSError, ValueError) as e:
            logger.error(f"save template {self.path}: {e}", exc_info=True)
            if tmp.exists():
                tmp.unlink()
            raise TemplateEditError(f"cannot save template {self.path.name}: {e}") from e
        self.dirty = False
        logger.info(f"template saved: {self.path.name}")
