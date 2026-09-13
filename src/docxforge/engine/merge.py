# -*- coding: utf-8 -*-
"""Paragraph merge and table cycle expansion for .docx templates."""

import re
from typing import Dict, List
from lxml import etree

from .xml_utils import W_NS, run_text, clone_run_with_text, clone_element, row_contains_placeholder, row_has_placeholders
from .schema import CycleMapping


def merge_and_replace_paragraph(paragraph, field_values: Dict[str, str]):
    """Merge XML runs in a paragraph and replace {{ placeholders }} with values.
    Preserves original run formatting by doing in-place replacement when possible."""
    runs = paragraph.findall(W_NS + 'r')
    if not runs:
        return

    # First pass: try in-place replacement within each run
    # If a run contains a complete placeholder, replace it directly
    for run in runs:
        text = run_text(run)
        if '{{' not in text:
            continue
        
        # Check if this run contains complete placeholders
        ph_matches = list(re.finditer(r'\{\{(.+?)\}\}', text))
        if not ph_matches:
            continue
        
        # If all placeholders in this run are complete (not split across runs),
        # we can do in-place replacement
        all_complete = True
        for m in ph_matches:
            field_key = m.group(1).strip()
            if field_key not in field_values:
                all_complete = False
                break
        
        if all_complete:
            # Replace all placeholders in this run
            new_text = text
            for m in reversed(ph_matches):  # Replace from end to preserve positions
                field_key = m.group(1).strip()
                repl = field_values.get(field_key)
                if repl is not None:
                    new_text = new_text[:m.start()] + str(repl) + new_text[m.end():]
            
            # Update the run's text in-place
            t_els = run.findall(W_NS + 't')
            if t_els:
                t_els[0].text = new_text
                t_els[0].set('{%s}space' % 'http://www.w3.org/XML/1998/namespace', 'preserve')
                for extra in t_els[1:]:
                    run.remove(extra)
            else:
                t_el = etree.SubElement(run, W_NS + 't')
                t_el.text = new_text
                t_el.set('{%s}space' % 'http://www.w3.org/XML/1998/namespace', 'preserve')
            continue

    # Second pass: handle placeholders that span multiple runs
    # Re-scan after in-place replacements
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

    if not segments:
        return

    def get_template_run_idx(start: int, end: int) -> int:
        run_ids = {char_to_run[i] for i in range(start, end) if i < len(char_to_run)}
        return min(run_ids) if run_ids else 0

    merged_segments = []
    cur_type, cur_start, cur_end, cur_repl = segments[0]
    cur_template_run_idx = get_template_run_idx(cur_start, cur_end)

    for seg_type, start, end, repl in segments[1:]:
        template_run_idx = get_template_run_idx(start, end)
        # Only merge if same run AND same type (both text or both replace)
        if template_run_idx == cur_template_run_idx and seg_type == cur_type:
            cur_end = end
            if seg_type == 'replace':
                cur_repl = repl
        else:
            merged_segments.append((cur_type, cur_start, cur_end, cur_repl, cur_template_run_idx))
            cur_type, cur_start, cur_end, cur_repl = seg_type, start, end, repl
            cur_template_run_idx = template_run_idx

    merged_segments.append((cur_type, cur_start, cur_end, cur_repl, cur_template_run_idx))

    new_runs = []
    for seg_type, start, end, repl, template_run_idx in merged_segments:
        template_run = runs[template_run_idx]
        if seg_type == 'replace' and repl is not None:
            text = repl
        else:
            text = merged[start:end]
        if text:
            new_runs.append(clone_run_with_text(template_run, text))

    if new_runs:
        last_old = runs[-1]
        prev = last_old
        for nr in new_runs:
            prev.addnext(nr)
            prev = nr
        last_new = prev
    else:
        last_new = runs[-1] if runs else None

    # Identify runs to preserve: those with non-text content (w:br, w:drawing, etc.)
    # but no text content - these should not be removed
    runs_to_preserve = []
    for run in runs:
        has_text = run_text(run) != ''
        has_non_text = any(
            child.tag != W_NS + 't' and child.tag != W_NS + 'rPr'
            for child in run
        )
        if not has_text and has_non_text:
            runs_to_preserve.append(run)

    for run in runs:
        if run not in runs_to_preserve:
            paragraph.remove(run)

    # Move preserved runs to the end (after all new content)
    if runs_to_preserve and last_new is not None:
        prev = last_new
        for run in runs_to_preserve:
            # Move the run to after last_new
            run.getparent().remove(run)
            prev.addnext(run)
            prev = run


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


