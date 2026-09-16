# -*- coding: utf-8 -*-
"""Document generation loop: field resolution and XML processing per document."""

import re
import os
import logging
import zipfile
from datetime import datetime
from typing import Dict, List, Optional
from lxml import etree

from .xml_utils import W_NS
from .merge import merge_and_replace_paragraph, expand_table_cycle
from .formatting import compute_aggregation, format_counter, format_today
from .image_utils import append_image_run, add_image_to_zdata, add_image_relationship
from .schema import (
    TemplateConfig, FieldMapping, FieldType, AggregationFunction,
    BatchSourceConfig, RowIterationMode, ResumeState,
    substitute_placeholders,
)


logger = logging.getLogger(__name__)


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
                if not rows:
                    # No data at all: leave the placeholder untouched.
                    continue
                managed = (fm.file in per_source_rows
                           or fm.file in (config.batch_sources or {}))
                if not managed and fm.column in rows[0]:
                    # Legacy default for unmanaged files (first row).
                    effective[fn] = str(rows[0][fm.column])
                else:
                    # M7: missing data must not be masked with rows[0].
                    effective[fn] = ''
                    logger.warning(
                        "No data for field '%s' (table '%s', column '%s'); "
                        "using empty string", fn, fm.file, fm.column)

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
                    if not rows:
                        # No data at all: leave the placeholder untouched.
                        continue
                    managed = (fm.file in per_source_rows
                               or fm.file in (config.batch_sources or {}))
                    if not managed and fm.column in rows[0]:
                        # Legacy default for unmanaged files (first row).
                        effective[fn] = str(rows[0][fm.column])
                    else:
                        # M7: missing data must not be masked with rows[0].
                        effective[fn] = ''
                        logger.warning(
                            "No data for field '%s' (table '%s', column '%s'); "
                            "using empty string", fn, fm.file, fm.column)
            else:
                primary_val = effective.get(fm.linked_to)
                if primary_val:
                    rows = all_table_data.get(fm.file, [])
                    primary_col = primary_fm.column
                    matched = False
                    for row in rows:
                        if str(row.get(primary_col, '')) == primary_val:
                            effective[fn] = str(row.get(fm.column, ''))
                            matched = True
                            break
                    if not matched:
                        if not rows:
                            # No data at all: leave placeholder.
                            continue
                        # M7: lookup miss is missing data, not rows[0].
                        effective[fn] = ''
                        logger.warning(
                            "Lookup miss for field '%s' (table '%s'); "
                            "using empty string", fn, fm.file)

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



def resolve_folder_name_template(
    template: str,
    row_data: Optional[Dict[str, str]] = None,
    constants: Optional[Dict[str, str]] = None,
    user_values: Optional[Dict[str, str]] = None,
    counter_value: Optional[int] = None,
    counter_format: str = '0001',
    now: Optional[datetime] = None,
) -> str:
    """Resolve {{field}} placeholders in a folder name template.

    This function reuses the same field resolution logic as document generation
    but operates on a simpler set of inputs suitable for folder name templates.

    Args:
        template: Folder name template string with {{field}} placeholders
        row_data: Current row data from batch source (e.g., {'client_name': 'ООО Альфа'})
        constants: Constant field values from template config
        user_values: User-provided values from UI
        counter_value: Current counter value (if counter field is used)
        counter_format: Counter format string (e.g., '0001')
        now: Current datetime for today fields (defaults to datetime.now())

    Returns:
        Resolved folder name string with all placeholders replaced.
        Missing fields are replaced with empty string.
    """
    if not template:
        return ''

    if now is None:
        now = datetime.now()

    if row_data is None:
        row_data = {}
    if constants is None:
        constants = {}
    if user_values is None:
        user_values = {}

    # Build effective values dict using same priority as resolve_field_values
    effective = {}
    effective.update(constants)
    effective.update(row_data)
    effective.update(user_values)

    # Add today fields if referenced in template
    today_matches = re.findall(r'\{\{\s*(today(?::[^}]*)?)\s*\}\}', template)
    for match in today_matches:
        stripped = match.strip()
        if stripped.startswith('today'):
            fmt = stripped[len('today:'):] if stripped.startswith('today:') else 'dd.MM.yyyy'
            effective[stripped] = format_today(fmt, now)

    # Add counter field if referenced and counter_value provided
    counter_matches = re.findall(r'\{\{\s*(counter)\s*\}\}', template)
    if counter_matches and counter_value is not None:
        effective['counter'] = format_counter(counter_value, counter_format)

    # Replace all placeholders via the shared engine core (M1): same
    # whitespace tolerance as generate/schema; missing fields become ''.
    result, _unresolved = substitute_placeholders(
        template, effective, on_missing='empty')

    return result

def process_xml(zdata: dict, config: TemplateConfig,
                cycle_data: Dict[str, List[Dict[str, str]]],
                effective: Dict[str, str],
                image_paths: Dict[str, str] = None,
                project_dir: str = None) -> dict:
    """Process all XML parts: expand cycles, replace placeholders, insert images."""
    if image_paths is None:
        image_paths = {}

    doc_xml = etree.fromstring(zdata['word/document.xml'])
    body = doc_xml.find(W_NS + 'body')

    for cycle in config.cycles:
        data = cycle_data.get(cycle.table, [])
        for tbl in body.findall('.//' + W_NS + 'tbl'):
            expand_table_cycle(tbl, cycle, data, effective)

    # Insert images before text replacement
    # Start past any media the template already ships (word/media/imageN.*),
    # otherwise new images would overwrite the template's own files.
    image_index = 1
    for _name in zdata:
        _m = re.match(r'word/media/image(\d+)', _name)
        if _m:
            image_index = max(image_index, int(_m.group(1)) + 1)
    for p in body.findall('.//' + W_NS + 'p'):
        runs = p.findall(W_NS + 'r')
        if not runs:
            continue
        merged_text = ''
        for r in runs:
            for t in r.findall(W_NS + 't'):
                if t.text:
                    merged_text += t.text
        pending = []
        for m in re.finditer(r'\{\{\s*image:(.+?)\s*\}\}', merged_text):
            img_name = m.group(1).strip()
            if img_name in image_paths:
                img_path = image_paths[img_name]
                if project_dir:
                    img_path = os.path.join(project_dir, img_path) if not os.path.isabs(img_path) else img_path
                if os.path.exists(img_path):
                    pending.append((img_name, img_path))
        if not pending:
            continue
        for run in p.findall(W_NS + 'r'):
            p.remove(run)
        for img_name, img_path in pending:
            media_path, _ct = add_image_to_zdata(zdata, img_path, image_index)
            r_id = 'rIdImg{:d}'.format(image_index)
            add_image_relationship(zdata, r_id, media_path)
            append_image_run(p, r_id, name=img_name)
            image_index += 1

    for p in body.findall('.//' + W_NS + 'p'):
        merge_and_replace_paragraph(p, effective)

    for part_name in list(zdata.keys()):
        if (part_name.startswith(('word/header', 'word/footer'))
                and part_name.endswith('.xml')):
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
                    pending_hf = []
                    for m in re.finditer(r'\{\{\s*image:(.+?)\s*\}\}', merged_text):
                        img_name = m.group(1).strip()
                        if img_name in image_paths:
                            img_path = image_paths[img_name]
                            if project_dir:
                                img_path = os.path.join(project_dir, img_path) if not os.path.isabs(img_path) else img_path
                            if os.path.exists(img_path):
                                pending_hf.append((img_name, img_path))
                    if pending_hf:
                        for run in p.findall(W_NS + 'r'):
                            p.remove(run)
                        for img_name, img_path in pending_hf:
                            media_path, _ct = add_image_to_zdata(zdata, img_path, image_index)
                            r_id = 'rIdImgHF{:d}'.format(image_index)
                            add_image_relationship(zdata, r_id, media_path)
                            append_image_run(p, r_id, name=img_name)
                            image_index += 1
                merge_and_replace_paragraph(p, effective)
            zdata[part_name] = etree.tostring(part_xml, xml_declaration=True,
                                               encoding='UTF-8', standalone=True)

    zdata['word/document.xml'] = etree.tostring(
        doc_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

    return zdata


def resolve_unique_output_path(path: str) -> str:
    """Return a non-existing sibling path, renaming as ``name (1).ext``.

    B5 (002-stabilization): generation must never overwrite an existing
    file — the file being created is renamed (``файл (1)``, ``файл (2)``,
    …) while the existing one is left untouched.
    """
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    index = 1
    while True:
        candidate = '%s (%d)%s' % (root, index, ext)
        if not os.path.exists(candidate):
            logger.info('Output %r exists; using %r instead', path, candidate)
            return candidate
        index += 1


def write_output_doc(zdata: dict, output_dir: str,
                     template_rel_path: str,
                     doc_index: int, total_docs: int,
                     batch_primary: Optional[str],
                     filename_template: Optional[str] = None,
                     directory_template: Optional[str] = None,
                     effective_values: Optional[Dict[str, str]] = None,
                     row_data: Optional[Dict[str, str]] = None,
                     constants: Optional[Dict[str, str]] = None,
                     user_values: Optional[Dict[str, str]] = None,
                     counter_value: Optional[int] = None,
                     counter_format: str = '0001',
                     now: Optional[datetime] = None) -> str:
    """Write a single output .docx file and return its path."""
    if filename_template and effective_values:
        out_name = filename_template
        for key, value in effective_values.items():
            out_name = out_name.replace('{{ %s }}' % key, str(value))
            out_name = out_name.replace('{{%s}}' % key, str(value))
        if not out_name.lower().endswith('.docx'):
            out_name += '.docx'
    elif total_docs > 1 or batch_primary:
        out_name = '%s_%04d.docx' % (os.path.splitext(template_rel_path)[0], doc_index + 1)
    else:
        out_name = os.path.basename(template_rel_path).replace(
            '.docx', '_заполнен.docx')

    out_dir = output_dir
    if directory_template:
        if row_data is not None or constants is not None or user_values is not None or counter_value is not None:
            dir_path = resolve_folder_name_template(
                directory_template,
                row_data=row_data,
                constants=constants,
                user_values=user_values,
                counter_value=counter_value,
                counter_format=counter_format,
                now=now)
        elif effective_values:
            dir_path = directory_template
            for key, value in effective_values.items():
                dir_path = dir_path.replace('{{ %s }}' % key, str(value))
                dir_path = dir_path.replace('{{%s}}' % key, str(value))
            dir_path = re.sub(r'\{\{\s*.+?\s*\}\}', '', dir_path)
        else:
            dir_path = directory_template

        if dir_path:
            out_dir = os.path.join(output_dir, dir_path)
            os.makedirs(out_dir, exist_ok=True)

    out_path = resolve_unique_output_path(os.path.join(out_dir, out_name))

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
