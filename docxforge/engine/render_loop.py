# -*- coding: utf-8 -*-
"""Document generation loop: field resolution and XML processing per document."""

import re
import os
import zipfile
from datetime import datetime
from typing import Dict, List, Optional
from lxml import etree

from .xml_utils import W, W_NS
from .merge import merge_and_replace_paragraph, expand_table_cycle
from .formatting import compute_aggregation, format_counter, format_today
from .image_utils import insert_image_in_paragraph, add_image_to_zdata, add_image_relationship
from .schema import (
    TemplateConfig, FieldMapping, FieldType, AggregationFunction,
    BatchSourceConfig, RowIterationMode, ResumeState,
)


def scan_raw_placeholders(zdata: dict) -> List[str]:
    """Scan raw placeholders from zipped document XML."""
    merged_all = ''
    doc_xml = etree.fromstring(zdata['word/document.xml'])
    for p in doc_xml.findall('.//' + W_NS + 'p'):
        for r in p.findall(W_NS + 'r'):
            for t in r.findall(W_NS + 't'):
                if t.text:
                    merged_all += t.text
        merged_all += '\n'
    return re.findall(r'\{\{(.+?)\}\}', merged_all)


def resolve_field_values(
    config: TemplateConfig,
    all_raw_phs: List[str],
    doc_index: int,
    per_source_rows: Dict[str, Optional[Dict[str, str]]],
    all_table_data: Dict[str, List[Dict[str, str]]],
    cycle_data: Dict[str, List[Dict[str, str]]],
    resume_compute: ResumeState,
    now: datetime,
    user_values: Dict[str, str],
) -> Dict[str, str]:
    """Build the effective field_values dict for a single document."""
    effective = dict(user_values)

    # 1. today from raw template
    for raw_ph in all_raw_phs:
        stripped = raw_ph.strip()
        if stripped.startswith('today'):
            fmt = stripped[len('today:'):] if stripped.startswith('today:') else 'dd.MM.yyyy'
            effective[stripped] = format_today(fmt, now)

    # 2. Counter
    counter_field = next(
        (fn for fn, fm in config.fields.items() if fm.type == FieldType.COUNTER), None)
    if counter_field:
        start = config.fields[counter_field].start
        fmt = config.fields[counter_field].format
        counter_offset = 0
        if resume_compute and resume_compute.continue_from_last:
            counter_offset = resume_compute.last_counter_value
        effective[counter_field] = format_counter(start + counter_offset + doc_index, fmt)

    # 3. Today from config
    for fn, fm in config.fields.items():
        if fm.type == FieldType.TODAY:
            effective[fn] = format_today(fm.format or 'dd.MM.yyyy', now)

    # 4. Constants
    for fn, fm in config.fields.items():
        if fm.type == FieldType.CONSTANT:
            effective[fn] = fm.value or ''

    # 5. TABLE \u2014 primary (not linked)
    for fn, fm in config.fields.items():
        if fm.type == FieldType.TABLE and not fm.linked_to:
            source_row = per_source_rows.get(fm.file)
            if source_row and fm.column in source_row:
                effective[fn] = str(source_row[fm.column])
            else:
                rows = all_table_data.get(fm.file, [])
                if rows and fm.column in rows[0]:
                    effective[fn] = str(rows[0][fm.column])

    # 6. TABLE \u2014 linked (same table \u2192 same row; different table \u2192 find by value)
    for fn, fm in config.fields.items():
        if fm.type == FieldType.TABLE and fm.linked_to:
            primary_fm = config.fields.get(fm.linked_to)
            if not primary_fm or not fm.file:
                continue
            if primary_fm.file == fm.file:
                source_row = per_source_rows.get(fm.file)
                if source_row and fm.column in source_row:
                    effective[fn] = str(source_row[fm.column])
                else:
                    rows = all_table_data.get(fm.file, [])
                    if rows and fm.column in rows[0]:
                        effective[fn] = str(rows[0][fm.column])
            else:
                primary_val = effective.get(fm.linked_to)
                if primary_val:
                    rows = all_table_data.get(fm.file, [])
                    primary_col = primary_fm.column
                    found = False
                    for row in rows:
                        if str(row.get(primary_col, '')) == primary_val:
                            effective[fn] = str(row.get(fm.column, ''))
                            found = True
                            break
                    if not found and rows:
                        effective[fn] = str(rows[0].get(fm.column, ''))

    # 7. Aggregations
    for aname, agg in config.aggregations.items():
        data = cycle_data.get(agg.table, [])
        effective[aname] = compute_aggregation(agg, data)

    # 8. IMAGE fields - store paths (not text values)
    image_paths = {}
    for fn, fm in config.fields.items():
        if fm.type == FieldType.IMAGE and fm.value:
            image_paths[fn] = fm.value

    return effective, image_paths


def process_xml(zdata: dict, config: TemplateConfig,
                cycle_data: Dict[str, List[Dict[str, str]]],
                effective: Dict[str, str],
                image_paths: Dict[str, str] = None,
                project_dir: str = None) -> dict:
    """Process all XML parts: expand cycles, replace placeholders, insert images."""
    from .xml_utils import W_NS
    if image_paths is None:
        image_paths = {}

    doc_xml = etree.fromstring(zdata['word/document.xml'])
    body = doc_xml.find(W_NS + 'body')

    for cycle in config.cycles:
        data = cycle_data.get(cycle.table, [])
        for tbl in body.findall('.//' + W_NS + 'tbl'):
            expand_table_cycle(tbl, cycle, data, effective)

    # Insert images before text replacement
    image_index = 1
    for p in body.findall('.//' + W_NS + 'p'):
        runs = p.findall(W_NS + 'r')
        if not runs:
            continue
        merged_text = ''
        for r in runs:
            for t in r.findall(W_NS + 't'):
                if t.text:
                    merged_text += t.text
        for m in re.finditer(r'\{\{\s*image:(.+?)\s*\}\}', merged_text):
            img_name = m.group(1).strip()
            if img_name in image_paths:
                img_path = image_paths[img_name]
                if project_dir:
                    img_path = os.path.join(project_dir, img_path) if not os.path.isabs(img_path) else img_path
                if os.path.exists(img_path):
                    r_id = 'rIdImg{:d}'.format(image_index)
                    add_image_to_zdata(zdata, img_path, image_index)
                    add_image_relationship(zdata, r_id,
                                          'word/media/image{:d}{}'.format(
                                              image_index,
                                              os.path.splitext(img_path)[1] or '.png'))
                    insert_image_in_paragraph(p, r_id, name=img_name)
                    image_index += 1
                    break

    for p in body.findall('.//' + W_NS + 'p'):
        merge_and_replace_paragraph(p, effective)

    for part_name in list(zdata.keys()):
        if 'header' in part_name or 'footer' in part_name:
            part_xml = etree.fromstring(zdata[part_name])
            for p in part_xml.findall('.//' + W_NS + 'p'):
                # Check for image placeholders in headers/footers too
                runs = p.findall(W_NS + 'r')
                if runs:
                    merged_text = ''
                    for r in runs:
                        for t in r.findall(W_NS + 't'):
                            if t.text:
                                merged_text += t.text
                    for m in re.finditer(r'\{\{\s*image:(.+?)\s*\}\}', merged_text):
                        img_name = m.group(1).strip()
                        if img_name in image_paths:
                            img_path = image_paths[img_name]
                            if project_dir:
                                img_path = os.path.join(project_dir, img_path) if not os.path.isabs(img_path) else img_path
                            if os.path.exists(img_path):
                                r_id = 'rIdImgHF{:d}'.format(image_index)
                                add_image_to_zdata(zdata, img_path, image_index)
                                add_image_relationship(zdata, r_id,
                                                      'word/media/image{:d}{}'.format(
                                                          image_index,
                                                          os.path.splitext(img_path)[1] or '.png'))
                                insert_image_in_paragraph(p, r_id, name=img_name)
                                image_index += 1
                                break
                merge_and_replace_paragraph(p, effective)
            zdata[part_name] = etree.tostring(part_xml, xml_declaration=True,
                                               encoding='UTF-8', standalone=True)

    zdata['word/document.xml'] = etree.tostring(
        doc_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

    return zdata


def write_output_doc(zdata: dict, output_dir: str,
                     template_rel_path: str,
                     doc_index: int, total_docs: int,
                     batch_primary: Optional[str],
                     filename_template: Optional[str] = None,
                     directory_template: Optional[str] = None,
                     effective_values: Optional[Dict[str, str]] = None) -> str:
    """Write a single output .docx file and return its path."""
    if filename_template and effective_values:
        # Use filename template with field substitution
        out_name = filename_template
        for key, value in effective_values.items():
            out_name = out_name.replace('{{ %s }}' % key, str(value))
            out_name = out_name.replace('{{%s}}' % key, str(value))
        # Ensure .docx extension
        if not out_name.lower().endswith('.docx'):
            out_name += '.docx'
    elif total_docs > 1 or batch_primary:
        out_name = '%s_%04d.docx' % (os.path.splitext(template_rel_path)[0], doc_index + 1)
    else:
        out_name = os.path.basename(template_rel_path).replace(
            '.docx', '_\u0437\u0430\u043f\u043e\u043b\u043d\u0435\u043d.docx')

    # Process directory template
    out_dir = output_dir
    if directory_template and effective_values:
        dir_path = directory_template
        for key, value in effective_values.items():
            dir_path = dir_path.replace('{{ %s }}' % key, str(value))
            dir_path = dir_path.replace('{{%s}}' % key, str(value))
        out_dir = os.path.join(output_dir, dir_path)
        os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, out_name)

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in zdata.items():
            zout.writestr(name, data)

    return out_path


def update_resume_state(resume: ResumeState, resume_compute: ResumeState,
                        config: TemplateConfig, batch_configs: Dict[str, BatchSourceConfig],
                        doc_index: int):
    """Update resume state after a successful render batch."""
    counter_field = next(
        (fn for fn, fm in config.fields.items() if fm.type == FieldType.COUNTER), None)
    if counter_field:
        counter_offset = 0
        if resume_compute.continue_from_last:
            counter_offset = resume_compute.last_counter_value
        resume.last_counter_value = counter_offset + doc_index
    for source_file, bsc in batch_configs.items():
        if bsc.mode in (RowIterationMode.SEQUENTIAL, RowIterationMode.CIRCULAR):
            start_offset = 0
            if resume_compute.continue_from_last:
                start_offset = resume_compute.sources.get(source_file, 0)
            resume.sources[source_file] = start_offset + doc_index
