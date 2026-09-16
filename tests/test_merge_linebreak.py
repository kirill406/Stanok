# -*- coding: utf-8 -*-
"""Regression tests for the B0 linebreak-merge bug (Phase 9, fix/002-linebreak-merge).

A mixed run ``text<w:br/>text{{field}}`` must keep ``<w:br/>`` before the
substituted value instead of shifting it past the field.
"""

from lxml import etree

from docxforge.engine.merge import merge_and_replace_paragraph

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_NS = "{%s}" % W


def _text_run(text):
    r = etree.Element(W_NS + "r")
    t = etree.SubElement(r, W_NS + "t")
    t.text = text
    return r


def _br_run():
    r = etree.Element(W_NS + "r")
    etree.SubElement(r, W_NS + "br")
    return r


def _mixed_run(before, after):
    r = etree.Element(W_NS + "r")
    t1 = etree.SubElement(r, W_NS + "t")
    t1.text = before
    etree.SubElement(r, W_NS + "br")
    t2 = etree.SubElement(r, W_NS + "t")
    t2.text = after
    return r


def _ordered_tokens(p_el):
    """Document-order tokens: ('text', str) and ('br',) for runs of a paragraph."""
    tokens = []
    for r in p_el.findall(W_NS + "r"):
        for child in r:
            if child.tag == W_NS + "t":
                tokens.append(("text", child.text or ""))
            elif child.tag == W_NS + "rPr":
                continue
            else:
                tokens.append((child.tag.split("}")[1],))
    merged = []
    for tok in tokens:
        if tok[0] == "text" and merged and merged[-1][0] == "text":
            merged[-1] = ("text", merged[-1][1] + tok[1])
        else:
            merged.append(tok)
    return [t for t in merged if t != ("text", "")]


class TestMergeLinebreak:
    def test_merge_mixed_run_br_stays_before_field(self):
        p = etree.Element(W_NS + "p")
        p.append(_mixed_run("textA", "textB{{f}}"))
        merge_and_replace_paragraph(p, {"f": "VAL"})
        assert _ordered_tokens(p) == [("text", "textA"), ("br",), ("text", "textBVAL")]

    def test_merge_separate_br_run_keeps_order(self):
        p = etree.Element(W_NS + "p")
        p.append(_text_run("textA"))
        p.append(_br_run())
        p.append(_text_run("textB{{f}}"))
        merge_and_replace_paragraph(p, {"f": "VAL"})
        assert _ordered_tokens(p) == [("text", "textA"), ("br",), ("text", "textBVAL")]

    def test_merge_field_without_br_renders_inline(self):
        p = etree.Element(W_NS + "p")
        p.append(_text_run("a{{f}}b"))
        merge_and_replace_paragraph(p, {"f": "VAL"})
        assert _ordered_tokens(p) == [("text", "aVALb")]
        assert len(p.findall(".//{%s}br" % W)) == 0

    def test_merge_split_placeholder_with_br_inside(self):
        p = etree.Element(W_NS + "p")
        r1 = etree.Element(W_NS + "r")
        t1 = etree.SubElement(r1, W_NS + "t")
        t1.text = "textA{{"
        etree.SubElement(r1, W_NS + "br")
        p.append(r1)
        p.append(_text_run("f}}textB"))
        merge_and_replace_paragraph(p, {"f": "VAL"})
        assert _ordered_tokens(p) == [("text", "textA"), ("br",), ("text", "VALtextB")]
