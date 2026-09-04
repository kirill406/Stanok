# -*- coding: utf-8 -*-
"""Prototype: XML-run merging for .docx {{ }} placeholders.

Tests whether we can reliably find and reconstruct {{ }} placeholders
that Word may have split across multiple XML runs.

A .docx file is a ZIP archive containing (among others) word/document.xml.
A paragraph <w:p> contains one or more <w:r> (run) elements.
Each run contains a <w:t> (text) element.
Word may split a single logical placeholder like "{{ ABC }}" across
multiple runs: <w:r><w:t>{{ </w:t></w:r> <w:r><w:t>ABC</w:t></w:r> <w:r><w:t> }}</w:t></w:r>.

This script:
1. Opens each .docx as ZIP
2. Reads document.xml
3. Merges adjacent runs within each paragraph
4. Searches for {{ ... }} patterns in merged text
5. Reports which placeholders were found and which were lost
"""

import re
import zipfile
import os
from lxml import etree
from collections import defaultdict

NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

def load_document_xml(docx_path):
    """Load word/document.xml from a .docx ZIP archive."""
    with zipfile.ZipFile(docx_path, 'r') as z:
        return etree.parse(z.open('word/document.xml'))

def get_paragraphs(doc_xml):
    """Extract all <w:p> elements."""
    return doc_xml.findall('.//w:p', NAMESPACES)

def get_runs(paragraph):
    """Extract all <w:r> elements from a paragraph."""
    return paragraph.findall('w:r', NAMESPACES)

def get_text_from_run(run):
    """Extract text from a <w:r> element.
    Returns the concatenation of all <w:t> elements.
    A single run may contain multiple <w:t> elements (rare but possible)."""
    texts = []
    for t in run.findall('w:t', NAMESPACES):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)

def merge_runs_text(paragraph):
    """Merge all runs in a paragraph into a single text string,
    while tracking which character positions belong to which run.

    Returns:
        merged_text (str): concatenation of all run texts
        char_to_run (list): for each character index, indicates the run index
        runs (list): list of (run_element, run_text) tuples
    """
    merged = ''
    char_to_run = []
    runs = []

    all_runs = get_runs(paragraph)

    for run_idx, run in enumerate(all_runs):
        text = get_text_from_run(run)
        runs.append((run, text))
        for ch in text:
            merged += ch
            char_to_run.append(run_idx)

    return merged, char_to_run, runs

def find_placeholders(text):
    """Find all {{ ... }} patterns in text.
    Returns list of (start_idx, end_idx, content) tuples."""
    pattern = re.compile(r'\{\{.+?\}\}')
    return [(m.start(), m.end(), m.group()) for m in pattern.finditer(text)]

def find_special_placeholders(text):
    """Find today, doc_number, image: patterns."""
    results = []
    for m in re.finditer(r'\{\{(today|doc_number|image):?[^}]*\}\}', text):
        results.append((m.start(), m.end(), m.group()))
    return results

def analyze_placeholder(placeholder_text, char_to_run, runs):
    """Check if a placeholder spans multiple runs.

    Returns:
        num_runs: how many different runs make up this placeholder
        run_indices: set of run indices involved
        run_texts: list of text from each involved run
    """
    # Extract the slice — in our merged text, the placeholder
    # starts at start_idx and ends at end_idx.
    # But we need to map back to which runs contributed.
    # Since we don't have start/end directly here, let's re-approach.
    pass


def analyze_document(docx_path, template_name):
    """Full analysis of one .docx template.

    Returns a report dict:
        - total_placeholders
        - found_placeholders
        - single_run: placeholders entirely in 1 run
        - multi_run: placeholders split across >1 run
        - lost: placeholders we expected but didn't find (where Word broke them)
        - issues: list of (paragraph_index, issue_description)
    """
    report = {
        'template': template_name,
        'total_expected': 0,
        'found': 0,
        'single_run': 0,
        'multi_run': 0,
        'multi_run_details': [],
        'lost': [],
        'issues': [],
    }

    doc_xml = load_document_xml(docx_path)
    paragraphs = get_paragraphs(doc_xml)

    # First pass: merge text and find all placeholders
    all_merged_texts = []
    para_data = []

    for p_idx, p in enumerate(paragraphs):
        merged, char_to_run, runs = merge_runs_text(p)
        all_merged_texts.append(merged)
        para_data.append((merged, char_to_run, runs))

        # Find all placeholders
        placeholders = find_placeholders(merged)

        for start, end, ph in placeholders:
            content = ph[2:-2].strip()

            # Which runs does this placeholder touch?
            # The character indices start...end span the merged text.
            # char_to_run[i] gives the run index for character i.
            involved_runs = set()
            for i in range(start, end):
                if i < len(char_to_run):
                    involved_runs.add(char_to_run[i])

            num_runs = len(involved_runs)
            report['found'] += 1

            if num_runs == 1:
                report['single_run'] += 1
            else:
                report['multi_run'] += 1
                # Show which run texts were involved
                run_snippets = []
                for ri in sorted(involved_runs):
                    run_snippets.append(repr(runs[ri][1]))
                report['multi_run_details'].append({
                    'placeholder': ph,
                    'num_runs': num_runs,
                    'paragraph': p_idx,
                    'run_texts': run_snippets,
                })

    # Second pass: check for placeholders that might be broken
    # (e.g. {{ at end of one para, }} at start of another — unlikely but possible)
    # Also check for {{ without }} and }} without {{
    total_text = '\n'.join(all_merged_texts)

    # Find unmatched opening braces
    open_braces = list(re.finditer(r'(?<!\{)\{\{(?!\{)', total_text))
    close_braces = list(re.finditer(r'(?<!\})\}\}(?!\})', total_text))

    # Count placeholders found by regex vs actual pairs
    expected_pairs = len(list(re.finditer(r'\{\{.*?\}\}', total_text)))
    report['regex_pair_count'] = expected_pairs

    if len(open_braces) != len(close_braces):
        diff_o = len(open_braces) - expected_pairs
        diff_c = len(close_braces) - expected_pairs
        report['issues'].append(
            f'Mismatched braces: {len(open_braces)} opening vs {len(close_braces)} closing '
            f'(regex found {expected_pairs} pairs). '
            f'Extra open: {diff_o}, Extra close: {diff_c}'
        )

    # Content analysis: what types of placeholders exist
    all_ph = re.findall(r'\{\{(.+?)\}\}', total_text)
    report['placeholder_types'] = {
        'simple': len([p for p in all_ph if not p.startswith('today') and not p.startswith('doc_number') and not p.startswith('image:')]),
        'today': len([p for p in all_ph if p.startswith('today')]),
        'doc_number': len([p for p in all_ph if p.startswith('doc_number')]),
        'image': len([p for p in all_ph if p.startswith('image:')]),
    }
    report['all_placeholders'] = [re.sub(r'^(.{40}).+$', r'\1...', f'{{{{{p}}}}}') for p in all_ph]

    return report


def main():
    templates_dir = 'prototype/templates'
    results = []

    for fname in sorted(os.listdir(templates_dir)):
        if not fname.endswith('.docx'):
            continue

        path = os.path.join(templates_dir, fname)
        report = analyze_document(path, fname)
        results.append(report)

    # Print summary
    print('=' * 70)
    print('  DOCX XML-RUN MERGE PROTOTYPE — RESULTS')
    print('=' * 70)
    print()

    total_found = 0
    total_multi = 0
    total_single = 0

    for r in results:
        print(f'--- {r["template"]} ---')
        print(f'  Found:     {r["found"]} placeholders')
        print(f'  1-run:     {r["single_run"]} (intact)')
        print(f'  Multi-run: {r["multi_run"]} (need merging)')
        if r['placeholder_types']:
            pt = r['placeholder_types']
            print(f'  Types:     {pt["simple"]} simple, {pt["today"]} today, '
                  f'{pt["doc_number"]} doc_number, {pt["image"]} image')
        if r['multi_run_details']:
            print(f'  Multi-run details:')
            for d in r['multi_run_details']:
                print(f'    P{d["paragraph"]}: {d["placeholder"]} '
                      f'— {d["num_runs"]} runs: {d["run_texts"]}')
        if r['issues']:
            for issue in r['issues']:
                print(f'  ⚠ ISSUE: {issue}')
        print()

        total_found += r['found']
        total_multi += r['multi_run']
        total_single += r['single_run']

    print('=' * 70)
    print(f'  TOTAL: {total_found} placeholders in {len(results)} templates')
    print(f'  1-run (OK):     {total_single} ({0 if total_found == 0 else 100*total_single//total_found}%)')
    print(f'  Multi-run (OK):  {total_multi} ({0 if total_found == 0 else 100*total_multi//total_found}%)')
    print()

    if total_multi == 0:
        print('  ✅ All placeholders are in single XML runs — no merging needed.')
        print('     (This is expected when python-docx generates the files.)')
        print('     TEST WITH REAL WORD-EDITED FILES for a true assessment.')
    else:
        pct = 100 * total_multi // total_found
        if pct < 10:
            print(f'  ✅ Only {pct}% multi-run — merge should handle this fine.')
        elif pct < 30:
            print(f'  ⚠  {pct}% multi-run — merge is feasible but needs testing on more files.')
        else:
            print(f'  ❌ {pct}% multi-run — very high split rate. Merge may be fragile.')

    print()
    print('  RECOMMENDATION:')
    print('  Open these .docx files in Microsoft Word, make minor edits')
    print('  (add/remove spaces near placeholders), save, and re-run this script.')
    print('  Word will likely split more placeholders, revealing the real risk.')


if __name__ == '__main__':
    main()
