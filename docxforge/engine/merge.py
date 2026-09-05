# -*- coding: utf-8 -*-
"""Paragraph merge and table cycle expansion for .docx templates."""

import re
from typing import Dict, List
from lxml import etree

from .xml_utils import W_NS, run_text, clone_run_with_text, clone_element, row_contains_placeholder, row_has_placeholders
from .schema import CycleMapping


def merge_and_replace_paragraph(paragraph, field_values: Dict[str, str]):
    """Merge XML runs in a paragraph and replace {{ placeholders }} with values.
    Uses addnext() in forward order to preserve text ordering."""
    runs = paragraph.findall(W_NS + 'r')
    if not runs:
        return

    merged = ''
    char_to_run = []
    for idx, run in enumerate(runs):
        for ch in run_text(run):
            char_to_run.append(idx)
            merged += ch

    if not merged:
        return

    ph_matches = list(re.finditer(r'\{\{(.+?)\}\}', merged))
    if not ph_matches:
        return

    segments = []
    cursor = 0
    for m in ph_matches:
        if cursor < m.start():
            segments.append(('text', cursor, m.start(), None))
        field_key = m.group(1).strip()
        repl = field_values.get(field_key)
        if repl is None:
            segments.append(('text', m.start(), m.end(), None))
        else:
            segments.append(('replace', m.start(), m.end(), str(repl)))
        cursor = m.end()

    if cursor < len(merged):
        segments.append(('text', cursor, len(merged), None))

    new_runs = []
    for seg_type, start, end, repl in segments:
        run_ids = {char_to_run[i] for i in range(start, end) if i < len(char_to_run)}
        if not run_ids:
            continue
        template_run = runs[min(run_ids)]
        text = repl if seg_type == 'replace' else merged[start:end]
        if text:
            new_runs.append(clone_run_with_text(template_run, text))

    if new_runs:
        last_old = runs[-1]
        prev = last_old
        for nr in new_runs:
            prev.addnext(nr)
            prev = nr

    for run in runs:
        paragraph.remove(run)


def expand_table_cycle(table_element, cycle: CycleMapping,
                       table_data: List[Dict[str, str]],
                       field_values: Dict[str, str]):
    rows = table_element.findall(W_NS + 'tr')
    if len(rows) < 2:
        return

    first_cycle_field = next(iter(cycle.columns.keys()), None)
    if not first_cycle_field:
        return

    template_row = None
    for row in rows:
        if row_contains_placeholder(row, first_cycle_field):
            template_row = row
            break
    if template_row is None:
        for row in reversed(rows):
            if row_has_placeholders(row):
                template_row = row
                break
    if template_row is None:
        return

    for row_data in table_data:
        new_row = clone_element(template_row)
        for p in new_row.findall('.//' + W_NS + 'p'):
            row_values = {}
            for field_name, column_name in cycle.columns.items():
                row_values[field_name] = row_data.get(column_name, '')
            merge_and_replace_paragraph(p, {**field_values, **row_values})
        template_row.addprevious(new_row)

    table_element.remove(template_row)


