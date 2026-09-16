# -*- coding: utf-8 -*-
"""Paragraph merge and table cycle expansion for .docx templates."""

import re
from copy import deepcopy
from typing import Dict, List
from lxml import etree

from .xml_utils import W_NS, run_text, clone_run_with_text, clone_element, row_contains_placeholder, row_has_placeholders
from .schema import CycleMapping


def _split_mixed_runs(paragraph, runs):
    """Split runs mixing <w:t> with non-text content (w:br, w:drawing, ...).

    Word stores Shift+Enter inside a text run as
    <w:r><w:t>a</w:t><w:br/><w:t>b</w:t></w:r>. Merging such a run by
    concatenating its <w:t> texts moves the break past the field value.
    Splitting into order-preserving pure runs (text-only / non-text-only,
    formatting via copied rPr) keeps every break at its document position.
    Only runs containing '{{' are touched; others are left as is.
    """
    changed = False
    for run in list(runs):
        if '{{' not in run_text(run):
            continue
        children = list(run)
        has_text = any(c.tag == W_NS + 't' for c in children)
        has_non_text = any(c.tag != W_NS + 't' and c.tag != W_NS + 'rPr'
                           for c in children)
        if not (has_text and has_non_text):
            continue
        rpr = run.find(W_NS + 'rPr')
        groups = []
        buf = []
        for child in children:
            if child.tag == W_NS + 'rPr':
                continue
            if child.tag == W_NS + 't':
                buf.append(child.text or '')
            else:
                if buf:
                    groups.append(('text', ''.join(buf)))
                    buf = []
                groups.append(('node', child))
        if buf:
            groups.append(('text', ''.join(buf)))
        for kind, payload in groups:
            new_run = etree.Element(W_NS + 'r')
            if rpr is not None:
                new_run.append(deepcopy(rpr))
            if kind == 'text':
                t_el = etree.SubElement(new_run, W_NS + 't')
                t_el.text = payload
                t_el.set('{%s}space' % 'http://www.w3.org/XML/1998/namespace', 'preserve')
            else:
                new_run.append(deepcopy(payload))
            run.addprevious(new_run)
        paragraph.remove(run)
        changed = True
    if changed:
        return paragraph.findall(W_NS + 'r')
    return runs


def merge_and_replace_paragraph(paragraph, field_values: Dict[str, str]):
    """Merge XML runs in a paragraph and replace {{ placeholders }} with values.
    Preserves original run formatting by doing in-place replacement when possible."""
    runs = paragraph.findall(W_NS + 'r')
    if not runs:
        return

    # Normalize mixed runs (text + w:br/w:drawing) holding placeholders so
    # breaks stay at their document position instead of sliding past values.
    runs = _split_mixed_runs(paragraph, runs)

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
    # Re-scan after in-place replacements. Non-text children (w:br,
    # w:drawing, ...) carry no merged chars; record each as a mark at its
    # text offset so it can be re-emitted at the same document position.
    merged = ''
    char_to_run = []
    marks = []
    for idx, run in enumerate(runs):
        for child in run:
            if child.tag == W_NS + 't':
                for ch in (child.text or ''):
                    char_to_run.append(idx)
                    merged += ch
            elif child.tag == W_NS + 'rPr':
                continue
            else:
                marks.append((len(merged), idx, child))

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

    # Order-preserving emission: interleave non-text marks at their offsets.
    # A mark strictly inside a {{...}} span is emitted before the value (it
    # cannot stay inside it); a mark inside a text span splits it; boundary
    # marks go between neighbours.
    out = []
    mi = 0
    for seg_type, start, end, repl in segments:
        while mi < len(marks) and marks[mi][0] <= start:
            _, m_idx, m_el = marks[mi]
            out.append(('mark', m_idx, m_el))
            mi += 1
        if seg_type == 'replace' and repl is not None:
            while mi < len(marks) and start < marks[mi][0] < end:
                _, m_idx, m_el = marks[mi]
                out.append(('mark', m_idx, m_el))
                mi += 1
            out.append(('value', get_template_run_idx(start, end), repl))
        else:
            cur = start
            while mi < len(marks) and start < marks[mi][0] < end:
                pos = marks[mi][0]
                _, m_idx, m_el = marks[mi]
                if cur < pos:
                    out.append(('text', get_template_run_idx(cur, pos), merged[cur:pos]))
                out.append(('mark', m_idx, m_el))
                cur = pos
                mi += 1
            if cur < end:
                out.append(('text', get_template_run_idx(cur, end), merged[cur:end]))
    while mi < len(marks):
        _, m_idx, m_el = marks[mi]
        out.append(('mark', m_idx, m_el))
        mi += 1

    new_nodes = []
    for item in out:
        if item[0] in ('text', 'value'):
            _, template_run_idx, text = item
            if not text:
                continue
            new_run = clone_run_with_text(runs[template_run_idx], text)
            # Strip non-text payload from the clone so it is neither lost
            # nor duplicated (marks are re-emitted separately, in order).
            for child in list(new_run):
                if child.tag != W_NS + 't' and child.tag != W_NS + 'rPr':
                    new_run.remove(child)
            new_nodes.append(new_run)
        else:
            _, m_idx, m_el = item
            mark_run = etree.Element(W_NS + 'r')
            rpr = runs[m_idx].find(W_NS + 'rPr')
            if rpr is not None:
                mark_run.append(deepcopy(rpr))
            mark_run.append(deepcopy(m_el))
            new_nodes.append(mark_run)

    if not new_nodes:
        return
    anchor = runs[0]
    for new_run in new_nodes:
        anchor.addprevious(new_run)
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

    if not table_data:
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


