# -*- coding: utf-8 -*-
"""Core rendering engine: XML-run merge, placeholder substitution, cycle expansion."""

import re
import zipfile
import os
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional
from lxml import etree

from .schema import (
    Project, TemplateConfig, FieldMapping, CycleMapping,
    AggregationMapping, FieldType, AggregationFunction,
)
from .data_reader import DataReader

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_NS = '{http://www.w3.org/XML/1998/namespace}'
W_NS = '{%s}' % W


# ============================================================
# XML helpers
# ============================================================

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
    """Check if a table row contains a specific {{ field_name }} placeholder."""
    for p in row.findall('.//' + W_NS + 'p'):
        for r in p.findall(W_NS + 'r'):
            text = run_text(r)
            if ('{{ %s }}' % field_name) in text or ('{{%s}}' % field_name) in text:
                return True
    return False


def row_has_placeholders(row) -> bool:
    """Check if a table row contains ANY {{ }} placeholder."""
    for p in row.findall('.//' + W_NS + 'p'):
        for r in p.findall(W_NS + 'r'):
            if re.search(r'\{\{.+?\}\}', run_text(r)):
                return True
    return False


# ============================================================
# merge + replace
# ============================================================

def merge_and_replace_paragraph(paragraph, field_values: Dict[str, str]):
    """Merge XML runs in a paragraph and replace {{ placeholders }} with values.
    Preserves run-level formatting by cloning the source run of each segment.
    """
    runs = paragraph.findall(W_NS + 'r')
    if not runs:
        return

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

    new_runs = []
    for seg_type, start, end, repl in segments:
        run_ids = {char_to_run[i] for i in range(start, end) if i < len(char_to_run)}
        if not run_ids:
            continue
        template_run = runs[min(run_ids)]
        text = repl if seg_type == 'replace' else merged[start:end]
        if text:
            new_runs.append(clone_run_with_text(template_run, text))

    anchor = runs[0]
    for nr in reversed(new_runs):
        anchor.addprevious(nr)
    for run in runs:
        paragraph.remove(run)


# ============================================================
# Table cycles
# ============================================================

def expand_table_cycle(table_element, cycle: CycleMapping,
                       table_data: List[Dict[str, str]],
                       field_values: Dict[str, str]):
    """Expand a table with cycle rows.

    Finds the row that contains the first cycle field placeholder
    and replaces it with one row per data entry.
    """
    rows = table_element.findall(W_NS + 'tr')
    if len(rows) < 2:
        return

    # Find the template row: first row that has any cycle field placeholder
    first_cycle_field = next(iter(cycle.columns.keys()), None)
    if not first_cycle_field:
        return

    template_row = None
    for row in rows:
        if row_contains_placeholder(row, first_cycle_field):
            template_row = row
            break

    if template_row is None:
        # Fallback: last row with any placeholder
        for row in reversed(rows):
            if row_has_placeholders(row):
                template_row = row
                break

    if template_row is None:
        return

    # Process after all other paragraphs so we don't re-process
    for row_data in table_data:
        new_row = clone_element(template_row)
        for p in new_row.findall('.//' + W_NS + 'p'):
            row_values = {}
            for field_name, column_name in cycle.columns.items():
                row_values[field_name] = row_data.get(column_name, '')
            merge_and_replace_paragraph(p, {**field_values, **row_values})
        template_row.addprevious(new_row)

    table_element.remove(template_row)


# ============================================================
# Aggregation
# ============================================================

def compute_aggregation(agg: AggregationMapping,
                        table_data: List[Dict[str, str]]) -> str:
    try:
        values = []
        for row in table_data:
            val = row.get(agg.column, '0').replace(',', '.').replace(' ', '')
            try:
                values.append(float(val))
            except ValueError:
                continue
        if not values:
            return '0'

        if agg.function == AggregationFunction.SUM:
            result = sum(values)
        elif agg.function == AggregationFunction.COUNT:
            result = len(values)
        elif agg.function == AggregationFunction.MAX:
            result = max(values)
        elif agg.function == AggregationFunction.MIN:
            result = min(values)
        else:
            result = sum(values)

        if agg.function == AggregationFunction.SUM_MULTIPLY and agg.multiplier:
            result *= agg.multiplier

        if result == int(result):
            return str(int(result))
        return '{:.2f}'.format(result).replace('.', ',')
    except Exception:
        return '0'


# ============================================================
# Formatting
# ============================================================

def format_counter(value: int, fmt: str) -> str:
    if fmt and fmt.startswith('0'):
        return str(value).zfill(len(fmt))
    return str(value)


def format_today(fmt: str, dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    months_ru = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']

    result = fmt
    result = result.replace('MM:название_месяца', months_ru[dt.month - 1])
    result = result.replace('dd', dt.strftime('%d'))
    result = result.replace('MM', dt.strftime('%m'))
    result = result.replace('yyyy', dt.strftime('%Y'))
    result = result.replace('HH', dt.strftime('%H'))
    result = result.replace('mm', dt.strftime('%M'))
    result = result.replace('ss', dt.strftime('%S'))
    return result


# ============================================================
# Renderer
# ============================================================

class Renderer:
    def __init__(self, project_dir: str, data_reader: DataReader):
        self.project_dir = project_dir
        self.data_reader = data_reader
        self.project: Optional[Project] = None

    def load_project(self):
        project_file = os.path.join(self.project_dir, 'проект.docxforge')
        self.project = Project.from_file(project_file) if os.path.exists(project_file) else Project()

    def save_project(self):
        self.project.to_file(os.path.join(self.project_dir, 'проект.docxforge'))

    def get_template_path(self, template_name: str) -> str:
        base = os.path.join(self.project_dir, 'Шаблоны')
        direct = os.path.join(base, template_name)
        if os.path.exists(direct):
            return direct
        for root, dirs, files in os.walk(base):
            if os.path.basename(template_name) in files:
                return os.path.join(root, os.path.basename(template_name))
        return direct

    def _read_table_data(self, table_file: str) -> List[Dict[str, str]]:
        path = os.path.join(self.project_dir, 'Данные', table_file)
        if os.path.exists(path):
            return self.data_reader.read_excel(path)
        return []

    def render(self, template_rel_path: str,
               user_values: Dict[str, str],
               batch_table: Optional[str] = None,
               output_dir: str = None) -> List[str]:
        template_path = self.get_template_path(template_rel_path)
        config = self.project.templates.get(template_rel_path, TemplateConfig()) if self.project else TemplateConfig()

        if output_dir is None:
            output_dir = os.path.join(self.project_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)

        with zipfile.ZipFile(template_path, 'r') as zf:
            zdata = {name: zf.read(name) for name in zf.namelist()}

        # Scan ALL raw placeholders from template
        merged_all = ''
        doc_for_scan = etree.fromstring(zdata['word/document.xml'])
        for p in doc_for_scan.findall('.//' + W_NS + 'p'):
            for r in p.findall(W_NS + 'r'):
                for t in r.findall(W_NS + 't'):
                    if t.text:
                        merged_all += t.text
            merged_all += '\n'

        all_raw_phs = re.findall(r'\{\{(.+?)\}\}', merged_all)

        # Determine batch rows
        batch_rows = [None]
        if batch_table:
            batch_rows = self._read_table_data(batch_table)

        # Pre-read cycle data
        cycle_data = {}
        for cycle in config.cycles:
            cycle_data[cycle.table] = self._read_table_data(cycle.table)

        # Pre-read table data for all TABLE fields
        table_primary_rows = {}
        for fn, fm in config.fields.items():
            if fm.type == FieldType.TABLE and fm.file and not fm.linked_to:
                if fm.file not in table_primary_rows:
                    table_primary_rows[fm.file] = self._read_table_data(fm.file)

        outputs = []

        for batch_idx, batch_row in enumerate(batch_rows):
            effective = dict(user_values)
            now = datetime.now()

            # 1. Batch row overrides
            if batch_row is not None:
                for key, val in batch_row.items():
                    effective[key] = str(val)

            # 2. today: variants (from raw template scan — auto-resolved)
            for raw_ph in all_raw_phs:
                stripped = raw_ph.strip()
                if stripped.startswith('today'):
                    fmt = stripped[len('today:'):] if stripped.startswith('today:') else 'dd.MM.yyyy'
                    effective[stripped] = format_today(fmt, now)

            # 3. doc_number from config counter
            counter_field = next(
                (fn for fn, fm in config.fields.items() if fm.type == FieldType.COUNTER), None)
            if counter_field:
                start = config.fields[counter_field].start
                fmt = config.fields[counter_field].format
                effective[counter_field] = format_counter(start + batch_idx, fmt)

            # 4. Today config fields
            for fn, fm in config.fields.items():
                if fm.type == FieldType.TODAY:
                    effective[fn] = format_today(fm.format or 'dd.MM.yyyy', now)

            # 5. Constant fields
            for fn, fm in config.fields.items():
                if fm.type == FieldType.CONSTANT:
                    effective[fn] = fm.value or ''

            # 6. Table fields: resolve from data (first row by default)
            for fn, fm in config.fields.items():
                if fm.type == FieldType.TABLE and not fm.linked_to:
                    rows = table_primary_rows.get(fm.file, [])
                    if rows and fm.column in rows[0]:
                        effective[fn] = str(rows[0][fm.column])

            # 7. Linked table fields
            for fn, fm in config.fields.items():
                if fm.type == FieldType.TABLE and fm.linked_to:
                    primary_val = effective.get(fm.linked_to)
                    if primary_val and fm.file:
                        rows = self._read_table_data(fm.file)
                        primary_fm = config.fields.get(fm.linked_to)
                        if primary_fm:
                            primary_col = primary_fm.column
                            found = False
                            for row in rows:
                                if str(row.get(primary_col, '')) == primary_val:
                                    effective[fn] = str(row.get(fm.column, ''))
                                    found = True
                                    break
                            if not found and rows:
                                effective[fn] = str(rows[0].get(fm.column, ''))

            # 8. Aggregations
            for aname, agg in config.aggregations.items():
                data = cycle_data.get(agg.table, [])
                effective[aname] = compute_aggregation(agg, data)

            # ---- XML transformation ----
            doc_xml = etree.fromstring(zdata['word/document.xml'])
            body = doc_xml.find(W_NS + 'body')

            # (A) Expand table cycles FIRST
            for cycle in config.cycles:
                data = cycle_data.get(cycle.table, [])
                for tbl in body.findall('.//' + W_NS + 'tbl'):
                    expand_table_cycle(tbl, cycle, data, effective)

            # (B) Text-level replacements in ALL paragraphs (including new cycle rows)
            for p in body.findall('.//' + W_NS + 'p'):
                merge_and_replace_paragraph(p, effective)

            # (C) Headers/footers
            for part_name in list(zdata.keys()):
                if 'header' in part_name or 'footer' in part_name:
                    part_xml = etree.fromstring(zdata[part_name])
                    for p in part_xml.findall('.//' + W_NS + 'p'):
                        merge_and_replace_paragraph(p, effective)
                    zdata[part_name] = etree.tostring(part_xml, xml_declaration=True,
                                                       encoding='UTF-8', standalone=True)

            zdata['word/document.xml'] = etree.tostring(
                doc_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

            if batch_table:
                out_name = '%s_%04d.docx' % (
                    os.path.splitext(template_rel_path)[0], batch_idx + 1)
            else:
                out_name = os.path.basename(template_rel_path).replace('.docx', '_заполнен.docx')
            out_path = os.path.join(output_dir, out_name)

            with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for name, data in zdata.items():
                    zout.writestr(name, data)

            outputs.append(out_path)

        return outputs
