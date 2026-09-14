# -*- coding: utf-8 -*-
"""XML utility functions for .docx run-level operations."""

import re
from copy import deepcopy
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_NS = '{http://www.w3.org/XML/1998/namespace}'
W_NS = '{%s}' % W


def run_text(run) -> str:
    return ''.join(t.text or '' for t in run.findall(W_NS + 't'))


def set_run_text(run, text: str):
    t_els = run.findall(W_NS + 't')
    if t_els:
        t_els[0].text = text
        t_els[0].set('%sspace' % XML_NS, 'preserve')
        for extra in t_els[1:]:
            run.remove(extra)
    else:
        t_el = etree.SubElement(run, W_NS + 't')
        t_el.text = text
        t_el.set('%sspace' % XML_NS, 'preserve')


def clone_run_with_text(template_run, text: str):
    new_run = etree.Element(W_NS + 'r')
    # Copy all child elements except <w:t> (text) which will be replaced
    for child in template_run:
        tag = child.tag
        if tag == W_NS + 't':
            continue
        new_run.append(deepcopy(child))
    set_run_text(new_run, text)
    return new_run


def clone_element(original):
    return etree.fromstring(etree.tostring(original))


def _row_text(row) -> str:
    """Merged text of a table row (all runs of all paragraphs).

    Row-scoped single pass: placeholders split across runs become visible.
    """
    parts = []
    for p in row.findall('.//' + W_NS + 'p'):
        parts.append(''.join(run_text(r) for r in p.findall(W_NS + 'r')))
    return '\n'.join(parts)


def row_contains_placeholder(row, field_name: str) -> bool:
    pattern = re.compile(r'\{\{\s*' + re.escape(field_name) + r'\s*\}\}')
    return bool(pattern.search(_row_text(row)))


def row_has_placeholders(row) -> bool:
    return bool(re.search(r'\{\{.+?\}\}', _row_text(row)))


