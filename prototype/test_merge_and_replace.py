# -*- coding: utf-8 -*-
"""Prototype: Merge XML runs, then substitute placeholder text.

This is the critical test: not just finding placeholders after merging,
but also REPLACING them and writing a valid .docx back.

Strategy:
1. For each paragraph, merge adjacent runs into a single run
2. Find {{ ... }} placeholders in the merged text
3. Replace placeholder with actual value
4. Copy formatting from the first run of the placeholder
5. Save as a new .docx

If this works — the engine is viable.
"""

import re
import zipfile
import os
import shutil
from lxml import etree
from copy import deepcopy

NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def load_document_bytes(docx_path):
    with open(docx_path, 'rb') as f:
        return f.read()


def parse_document_xml(zf):
    return etree.parse(zf.open('word/document.xml'))


def get_runs(paragraph):
    return paragraph.findall(f'{{{W}}}r')


def run_text(run):
    """Get the text of a run."""
    texts = []
    for t in run.findall(f'{{{W}}}t'):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)


def set_run_text(run, text):
    """Set text on a run. Handles single vs multiple <w:t> elements."""
    t_elements = run.findall(f'{{{W}}}t')
    if len(t_elements) >= 1:
        # Use the first <w:t>
        t_elements[0].text = text
        # Remove extra <w:t> elements
        for extra in t_elements[1:]:
            run.remove(extra)
    else:
        # Create new <w:t> if none exists
        t_el = etree.SubElement(run, f'{{{W}}}t')
        t_el.text = text
        # Preserve space
        t_el.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def merge_and_replace_in_paragraph(paragraph, replacements):
    """Merge runs in a paragraph, then replace {{ placeholders }} with values.

    replacements: dict of { 'field_name': 'value' }

    Strategy:
    - Read all runs and their texts
    - Merge text
    - Find all {{ ... }} patterns
    - Build a new set of runs by slicing through the original runs
    - For each placeholder, use the formatting of its first run
    """
    runs = get_runs(paragraph)
    if not runs:
        return

    # Build mapping: character index -> run index
    merged_text = ''
    char_to_run = []
    run_texts = []

    for r_idx, run in enumerate(runs):
        text = run_text(run)
        run_texts.append(text)
        for ch in text:
            char_to_run.append(r_idx)
            merged_text += ch

    if not merged_text:
        return

    # Find all placeholders
    placeholders = list(re.finditer(r'\{\{\s*(.+?)\s*\}\}', merged_text))
    if not placeholders:
        return  # nothing to replace

    # Build list of (run_index, start_in_run, end_in_run, new_text, formatting_run)
    # We'll rebuild the runs from scratch
    new_runs_data = []  # (from_run_idx, start_pos, end_pos, replacement_text)

    # First pass: identify placeholder positions
    ph_positions = []
    for m in placeholders:
        field_name = m.group(1).strip()
        replacement = replacements.get(field_name, f'[НЕ НАЙДЕНО: {field_name}]')
        ph_positions.append((m.start(), m.end(), replacement))

    # Second pass: build new run segments
    cursor = 0
    for ph_start, ph_end, replacement in ph_positions:
        # Copy text before placeholder (keeping original runs)
        if cursor < ph_start:
            new_runs_data.append(('keep', cursor, ph_start, None))

        # The placeholder itself
        new_runs_data.append(('replace', ph_start, ph_end, replacement))

        cursor = ph_end

    # Remaining text after last placeholder
    if cursor < len(merged_text):
        new_runs_data.append(('keep', cursor, len(merged_text), None))

    # Now rebuild runs
    # We need to preserve the FIRST run element (for formatting)
    # and remove the rest
    first_run = runs[0] if runs else None

    if not first_run:
        return

    # Build final text and apply to runs
    # Simplified approach: merge everything into first run, delete other runs
    final_text_parts = []
    for action, start, end, repl in new_runs_data:
        if action == 'keep':
            # Copy text from original, preserving character-level formatting
            # For simplicity in proto: just take the text
            final_text_parts.append(merged_text[start:end])
        elif action == 'replace':
            final_text_parts.append(repl)

    final_text = ''.join(final_text_parts)

    # Set all text on first run
    set_run_text(first_run, final_text)

    # Remove other runs
    parent = paragraph
    for run in runs[1:]:
        parent.remove(run)


def process_document(input_path, output_path, replacements):
    """Open .docx, substitute placeholders, save to new file."""
    # Copy original to temp
    shutil.copy2(input_path, output_path)

    # Open the copy and modify
    with zipfile.ZipFile(output_path, 'a') as zf:
        # Need to read and rewrite document.xml
        pass

    # Actually, we need a different approach since ZIP can't easily rewrite files
    # Let's use the proper approach: read into memory, modify, write new ZIP

    # Read original
    with zipfile.ZipFile(input_path, 'r') as zin:
        zdata = {name: zin.read(name) for name in zin.namelist()}

    # Parse and modify document.xml
    doc_xml = etree.fromstring(zdata['word/document.xml'])
    paragraphs = doc_xml.findall(f'.//{{{W}}}p')

    modified_count = 0
    for p in paragraphs:
        merge_and_replace_in_paragraph(p, replacements)
        modified_count += 1

    # Write modified document.xml back
    zdata['word/document.xml'] = etree.tostring(doc_xml, xml_declaration=True,
                                                 encoding='UTF-8', standalone=True)

    # Write new ZIP
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in zdata.items():
            zout.writestr(name, data)

    return modified_count


def main():
    print('=' * 70)
    print('  MERGE + REPLACE TEST')
    print('=' * 70)
    print()

    # Test on the formatting-heavy template (worst case)
    input_path = 'prototype/templates/test_02_formatting.docx'
    output_path = 'prototype/output/test_02_merged.docx'

    replacements = {
        'название_клиента': 'ООО "Альфа"',
        'важное_поле': 'ВАЖНО',
        'ИНН_клиента': '7712345678',
        'сторона': 'Поставщик',
    }

    os.makedirs('prototype/output', exist_ok=True)

    try:
        n = process_document(input_path, output_path, replacements)
        print(f'  ✅ Processed {n} paragraphs')
        print(f'  Output: {output_path}')
        print()

        # Verify: read back and check no placeholders remain
        with zipfile.ZipFile(output_path, 'r') as zf:
            doc_xml = etree.parse(zf.open('word/document.xml'))
            pars = doc_xml.findall(f'.//{{{W}}}p')
            all_text = ''
            for p in pars:
                runs = p.findall(f'{{{W}}}r')
                for r in runs:
                    for t in r.findall(f'{{{W}}}t'):
                        if t.text:
                            all_text += t.text
                all_text += '\n'

            remaining = re.findall(r'\{\{.+?\}\}', all_text)
            if remaining:
                print(f'  ⚠  {len(remaining)} unreplaced placeholders:')
                for r in remaining:
                    print(f'     {r}')
            else:
                print(f'  ✅ All placeholders replaced. Remaining: 0')
                print(f'  Preview of output text:')
                for line in all_text.split('\n')[:10]:
                    if line.strip():
                        print(f'     {line.strip()[:100]}')

    except Exception as e:
        print(f'  ❌ Error: {e}')
        import traceback
        traceback.print_exc()

    print()
    print('  === NOW THE CRITICAL REAL-WORLD TEST ===')
    print()
    print('  Open these files in Microsoft Word:')
    print(f'    → {input_path}')
    print(f'    → prototype/templates/test_04_real_layout.docx')
    print(f'    → prototype/templates/test_05_edge_cases.docx')
    print()
    print('  Make minor edits near placeholders (add a space before «,')
    print('  change bold to italic, etc.) — any small formatting change.')
    print('  Then SAVE and re-run:')
    print('    python prototype/test_run_merge.py')
    print()
    print('  This will reveal whether Word creates MORE split-placeholders')
    print('  than python-docx did (which is almost certain).')


if __name__ == '__main__':
    main()
