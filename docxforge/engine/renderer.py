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
    BatchSourceConfig, RowIterationMode, ResumeState,
)
from .data_reader import DataReader

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


def merge_and_replace_paragraph(paragraph, field_values: Dict[str, str]):
    """Merge XML runs in a paragraph and replace {{ placeholders }} with values.
    Uses addnext() in forward order to preserve text ordering."""
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

    if new_runs:
        last_old = runs[-1]
        prev = last_old
        for nr in new_runs:
            prev.addnext(nr)
            prev = nr

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

    for row_data in table_data:
        new_row = clone_element(template_row)
        for p in new_row.findall('.//' + W_NS + 'p'):
            row_values = {}
            for field_name, column_name in cycle.columns.items():
                row_values[field_name] = row_data.get(column_name, '')
            merge_and_replace_paragraph(p, {**field_values, **row_values})
        template_row.addprevious(new_row)

    table_element.remove(template_row)


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
        self._atomic_write_project()

    def _atomic_write_project(self):
        """Atomically write project file: write .tmp → backup .bak → rename."""
        project_file = os.path.join(self.project_dir, 'проект.docxforge')
        tmp_file = project_file + '.tmp'
        bak_file = project_file + '.bak'
        data = self.project._to_dict()
        # Write to temp
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Backup current
        if os.path.exists(project_file):
            try:
                os.replace(project_file, bak_file)
            except Exception:
                pass
        # Rename temp to final
        os.replace(tmp_file, project_file)

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

    def _resolve_constant_row(self, table_file: str,
                               batch_configs: Optional[Dict[str, BatchSourceConfig]] = None,
                               all_rows: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, str]]:
        """Resolve the row for a CONSTANT-mode source (lookup by column value).

        Returns the matching row, or first row if lookup fails, or None if no data.
        """
        if not batch_configs:
            return None
        bsc = batch_configs.get(table_file)
        if not bsc or bsc.mode != RowIterationMode.CONSTANT:
            return None
        if all_rows is None:
            all_rows = self._read_table_data(table_file)
        if not all_rows:
            return None
        if bsc.lookup_column and bsc.lookup_value:
            for row in all_rows:
                if str(row.get(bsc.lookup_column, '')).strip() == bsc.lookup_value.strip():
                    return row
            return all_rows[0]  # fallback
        return all_rows[0]  # no lookup → first row

    def _resolve_row_for_source(self, source_file: str, doc_index: int,
                                 batch_configs: Dict[str, BatchSourceConfig],
                                 resume: Optional[ResumeState] = None,
                                 all_rows: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, str]]:
        """Resolve the data row for a given source at a given document index.

        doc_index: 0-based index of the document being generated.
        resume: if continue_from_last, offset by last_row.
        """
        if all_rows is None:
            all_rows = self._read_table_data(source_file)
        if not all_rows:
            return None

        bsc = batch_configs.get(source_file)
        if not bsc:
            # No config → default to CONSTANT (first row)
            return all_rows[0]

        if bsc.mode == RowIterationMode.CONSTANT:
            return self._resolve_constant_row(source_file, batch_configs, all_rows)

        # Compute effective start index (for resume)
        start_offset = 0
        if resume and resume.continue_from_last:
            start_offset = resume.sources.get(source_file, 0)

        effective_i = start_offset + doc_index

        if bsc.mode == RowIterationMode.SEQUENTIAL:
            if effective_i < len(all_rows):
                return all_rows[effective_i]
            else:
                return None  # exhausted → stop

        if bsc.mode == RowIterationMode.CIRCULAR:
            return all_rows[effective_i % len(all_rows)]

        return all_rows[0]

    def _compute_total_docs(self, config: TemplateConfig,
                            batch_configs: Dict[str, BatchSourceConfig],
                            resume: Optional[ResumeState] = None) -> Optional[int]:
        """Determine total number of documents to generate.

        Returns int if total can be determined, None if it cannot.

        Rules:
        - If total_docs is set explicitly → use it.
        - If any SEQUENTIAL source exists → min(len) of all SEQUENTIAL sources
          (accounting for resume offset).
        - If no SEQUENTIAL -> return None (cannot auto-determine).
        """
        if config.total_docs is not None and config.total_docs > 0:
            return config.total_docs

        # Auto: find min rows among SEQUENTIAL sources
        sequential_sources = [
            (name, bsc) for name, bsc in batch_configs.items()
            if bsc.mode == RowIterationMode.SEQUENTIAL
        ]
        if not sequential_sources:
            # No SEQUENTIAL, cannot auto-determine
            return None

        min_remaining = None
        for name, bsc in sequential_sources:
            all_rows = self._read_table_data(name)
            start_offset = 0
            if resume and resume.continue_from_last:
                start_offset = resume.sources.get(name, 0)
            remaining = max(0, len(all_rows) - start_offset)
            if min_remaining is None or remaining < min_remaining:
                min_remaining = remaining

        return min_remaining if min_remaining and min_remaining > 0 else None

    def render(self, template_rel_path: str,
               user_values: Dict[str, str],
               batch_table: Optional[str] = None,
               output_dir: str = None,
               batch_configs: Optional[Dict[str, BatchSourceConfig]] = None,
               max_docs: Optional[int] = None,
               resume: Optional[ResumeState] = None) -> List[str]:
        """Render template into one or more output documents.

        Args:
            batch_table: (legacy) Excel file for batch iteration.
            max_docs: (legacy) limit on total documents.
            batch_configs: per-source iteration mode config.
            resume: resume state for continuation.
        """
        template_path = self.get_template_path(template_rel_path)
        config = self.project.templates.get(template_rel_path, TemplateConfig()) if self.project else TemplateConfig()

        if output_dir is None:
            output_dir = os.path.join(self.project_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)

        # Use batch_configs from project if not provided
        if batch_configs is None:
            batch_configs = dict(config.batch_sources)

        # Legacy: if batch_table given without matching batch_config, add SEQUENTIAL
        if batch_table and batch_table not in batch_configs:
            batch_configs[batch_table] = BatchSourceConfig(
                file=batch_table, mode=RowIterationMode.SEQUENTIAL)

        # Use resume from config if not provided, else fresh start
        if resume is None:
            # Only auto-use config.resume if it has actual saved state
            if config.resume and config.resume.sources:
                resume = config.resume
            else:
                resume = ResumeState(continue_from_last=False)

        # Clone resume for computation so the original is not mutated
        # during the render loop (updated only after successful render).
        resume_compute = ResumeState(
            last_counter_value=resume.last_counter_value,
            sources=dict(resume.sources),
            continue_from_last=resume.continue_from_last,
        )

        with zipfile.ZipFile(template_path, 'r') as zf:
            zdata = {name: zf.read(name) for name in zf.namelist()}

        zdata_orig = {name: data for name, data in zdata.items()}

        # Scan raw placeholders
        merged_all = ''
        doc_for_scan = etree.fromstring(zdata['word/document.xml'])
        for p in doc_for_scan.findall('.//' + W_NS + 'p'):
            for r in p.findall(W_NS + 'r'):
                for t in r.findall(W_NS + 't'):
                    if t.text:
                        merged_all += t.text
            merged_all += '\n'
        all_raw_phs = re.findall(r'\{\{(.+?)\}\}', merged_all)

        # Determine total documents
        total_docs = self._compute_total_docs(config, batch_configs, resume_compute)
        # Legacy max_docs override
        if max_docs is not None and max_docs > 0:
            if total_docs is None:
                total_docs = max_docs
            else:
                total_docs = min(total_docs, max_docs)
        if total_docs is None or total_docs <= 0:
            total_docs = 1

        # Pre-read all table data (shared across iterations)
        all_table_data = {}
        for fn, fm in config.fields.items():
            if fm.type == FieldType.TABLE and fm.file and fm.file not in all_table_data:
                all_table_data[fm.file] = self._read_table_data(fm.file)
        for source_file in batch_configs:
            if source_file not in all_table_data:
                all_table_data[source_file] = self._read_table_data(source_file)

        cycle_data = {}
        for cycle in config.cycles:
            if cycle.table not in all_table_data:
                cycle_data[cycle.table] = self._read_table_data(cycle.table)
            else:
                cycle_data[cycle.table] = all_table_data[cycle.table]

        # Find primary batch table for legacy mode
        batch_primary = None
        if batch_table:
            batch_primary = batch_table
        elif batch_configs:
            # First SEQUENTIAL source is the "primary" batch table
            for name, bsc in batch_configs.items():
                if bsc.mode == RowIterationMode.SEQUENTIAL:
                    batch_primary = name
                    break

        # Collect warnings
        warnings = []

        outputs = []
        doc_index = 0

        while doc_index < total_docs:
            # Reset zdata from pristine copy
            zdata = {name: data for name, data in zdata_orig.items()}
            effective = dict(user_values)
            now = datetime.now()

            # Resolve per-source rows for this document index
            per_source_rows: Dict[str, Optional[Dict[str, str]]] = {}
            for source_file, bsc in batch_configs.items():
                rows = all_table_data.get(source_file, [])
                row = self._resolve_row_for_source(
                    source_file, doc_index, batch_configs, resume_compute, rows)
                if row is None and bsc.mode == RowIterationMode.SEQUENTIAL:
                    # Source exhausted — stop generation
                    if doc_index == 0:
                        warnings.append(
                            'Таблица «%s» не имеет данных для генерации.' % source_file)
                    break
                per_source_rows[source_file] = row

            # Check if any source stopped us
            stopped = False
            for source_file, bsc in batch_configs.items():
                if bsc.mode == RowIterationMode.SEQUENTIAL:
                    rows = all_table_data.get(source_file, [])
                    start_offset = 0
                    if resume_compute and resume_compute.continue_from_last:
                        start_offset = resume_compute.sources.get(source_file, 0)
                    if start_offset + doc_index >= len(rows):
                        stopped = True
                        if doc_index > 0:
                            # Only warn if we produced at least some docs
                            pass
                        else:
                            warnings.append(
                                'Таблица «%s» исчерпана (строк: %d, начало: %d).' %
                                (source_file, len(rows), start_offset))
            if stopped and doc_index == 0:
                # No docs at all — still generate one from defaults
                pass
            elif stopped:
                break

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

            # 5. TABLE — primary (not linked)
            for fn, fm in config.fields.items():
                if fm.type == FieldType.TABLE and not fm.linked_to:
                    source_row = per_source_rows.get(fm.file)
                    if source_row and fm.column in source_row:
                        effective[fn] = str(source_row[fm.column])
                    else:
                        rows = all_table_data.get(fm.file, [])
                        if rows and fm.column in rows[0]:
                            effective[fn] = str(rows[0][fm.column])

            # 6. TABLE — linked (same table → same row; different table → find by value)
            for fn, fm in config.fields.items():
                if fm.type == FieldType.TABLE and fm.linked_to:
                    primary_fm = config.fields.get(fm.linked_to)
                    if not primary_fm or not fm.file:
                        continue
                    if primary_fm.file == fm.file:
                        # Same table: use same row resolution
                        source_row = per_source_rows.get(fm.file)
                        if source_row and fm.column in source_row:
                            effective[fn] = str(source_row[fm.column])
                        else:
                            rows = all_table_data.get(fm.file, [])
                            if rows and fm.column in rows[0]:
                                effective[fn] = str(rows[0][fm.column])
                    else:
                        # Different table: find row by primary value
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

            # ---- XML ----
            doc_xml = etree.fromstring(zdata['word/document.xml'])
            body = doc_xml.find(W_NS + 'body')

            for cycle in config.cycles:
                data = cycle_data.get(cycle.table, [])
                for tbl in body.findall('.//' + W_NS + 'tbl'):
                    expand_table_cycle(tbl, cycle, data, effective)

            for p in body.findall('.//' + W_NS + 'p'):
                merge_and_replace_paragraph(p, effective)

            for part_name in list(zdata.keys()):
                if 'header' in part_name or 'footer' in part_name:
                    part_xml = etree.fromstring(zdata[part_name])
                    for p in part_xml.findall('.//' + W_NS + 'p'):
                        merge_and_replace_paragraph(p, effective)
                    zdata[part_name] = etree.tostring(part_xml, xml_declaration=True,
                                                       encoding='UTF-8', standalone=True)

            zdata['word/document.xml'] = etree.tostring(
                doc_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

            # File naming
            if total_docs > 1 or batch_primary:
                out_name = '%s_%04d.docx' % (os.path.splitext(template_rel_path)[0], doc_index + 1)
            else:
                out_name = os.path.basename(template_rel_path).replace('.docx', '_заполнен.docx')
            out_path = os.path.join(output_dir, out_name)

            with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for name, data in zdata.items():
                    zout.writestr(name, data)

            outputs.append(out_path)
            doc_index += 1

        # Update resume state
        if resume:
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

        return outputs
