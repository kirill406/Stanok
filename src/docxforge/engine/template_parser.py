# -*- coding: utf-8 -*-
"""Scans .docx templates, finds {{ }} placeholders, and classifies them."""

import re
import zipfile
import logging
from typing import Any, Dict
from lxml import etree

logger = logging.getLogger(__name__)

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

IMAGE_PREFIX = 'image:'


def scan_template(docx_path: str) -> Dict[str, Any]:
    """Scan a .docx template and extract all placeholders.

    Returns:
        {
            'filename': str,
            'placeholders': [(name, raw_text), ...],
            'simple': [name, ...],
            'today': [raw, ...],
            'doc_number': [raw, ...],
            'image': [name, ...],
        }
    """
    with zipfile.ZipFile(docx_path, 'r') as zf:
        all_names = zf.namelist()
        doc_xml = etree.parse(zf.open('word/document.xml'))

    all_text_parts = []
    header_footer_placeholders = []

    # Scan document.xml (.//p already covers table paragraphs)
    for p in doc_xml.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
        merged = merge_runs_text(p)
        if merged:
            all_text_parts.append(merged)

    # Scan headers and footers
    with zipfile.ZipFile(docx_path, 'r') as zf:
        for name in all_names:
            if 'header' in name or 'footer' in name:
                if name.endswith('.xml'):
                    try:
                        part_xml = etree.parse(zf.open(name))
                        for p in part_xml.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                            merged = merge_runs_text(p)
                            if merged:
                                phs = re.findall(r'\{\{(.+?)\}\}', merged)
                                for ph in phs:
                                    header_footer_placeholders.append(
                                        (ph.strip(), '{{ ' + ph + ' }}', name))
                                all_text_parts.append(merged)
                    except Exception as e:
                        logger.exception(f'Skipping unparsable header/footer part {name}: {e}')

    full_text = '\n'.join(all_text_parts)
    raw_placeholders = re.findall(r'\{\{(.+?)\}\}', full_text)

    seen = set()
    unique = []
    for ph in raw_placeholders:
        if ph not in seen:
            seen.add(ph)
            unique.append(ph)

    simple = []
    today_list = []
    doc_number_list = []
    image_list = []

    for ph in unique:
        stripped = ph.strip()
        if stripped.startswith(IMAGE_PREFIX):
            image_list.append(stripped[len(IMAGE_PREFIX):])
        elif stripped.startswith('today'):
            today_list.append(stripped)
        elif stripped.startswith('doc_number'):
            doc_number_list.append(stripped)
        else:
            # Check if it's purely a reserved name without format
            base = stripped.split(':')[0]
            if base in ('today', 'doc_number', 'now', 'page'):
                if base == 'today':
                    today_list.append(stripped)
                else:
                    doc_number_list.append(stripped)
            else:
                simple.append(stripped)

    return {
        'filename': docx_path,
        'placeholders': [(ph.strip(), '{{ ' + ph + ' }}') for ph in unique],
        'simple': simple,
        'today': today_list,
        'doc_number': doc_number_list,
        'image': image_list,
        'header_footer_placeholders': header_footer_placeholders,
    }


def merge_runs_text(paragraph) -> str:
    runs = paragraph.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
    if not runs:
        return ''
    result = ''
    for run in runs:
        for t in run.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
            if t.text:
                result += t.text
    return result
