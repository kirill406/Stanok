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
    rpr = template_run.find(W_NS + 'rPr')
    if rpr is not None:
        new_run.append(deepcopy(rpr))
    set_run_text(new_run, text)
    return new_run


def clone_element(original):
    return etree.fromstring(etree.tostring(original))


def row_contains_placeholder(row, field_name: str) -> bool:
    for p in row.findall('.//' + W_NS + 'p'):
        for r in p.findall(W_NS + 'r'):
            text = run_text(r)
            if ('{{ %s }}' % field_name) in text or ('{{%s}}' % field_name) in text:
                return True
    return False


def row_has_placeholders(row) -> bool:
    for p in row.findall('.//' + W_NS + 'p'):
        for r in p.findall(W_NS + 'r'):
            if re.search(r'\{\{.+?\}\}', run_text(r)):
                return True
    return False


