# -*- coding: utf-8 -*-
"""Excel → JSON boundary: read tables once, resolve Filling JSON fields.

003-json layer: the single home of per-document field resolution.
``resolve_document_fields`` is the exact legacy loop semantics (moved
verbatim from ``render_loop``: linked tables, legacy unmanaged fallback,
M7 no-masking, aggregations, image paths, raw-template today) — the
generation loop and all callers consume it from here.
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from docxforge.engine.data_reader import DataReader
from docxforge.engine.errors import (
    EMPTY_SEQUENTIAL,
    TABLE_EXHAUSTED,
    message_for_code,
)
from docxforge.engine.formatting import (
    compute_aggregation,
    format_counter,
    format_today,
)
from docxforge.engine.schema import (
    BatchSourceConfig,
    FieldType,
    ResumeState,
    RowIterationMode,
    TemplateConfig,
)

logger = logging.getLogger(__name__)


def read_table_rows(data_reader: DataReader, path: str,
                    sheet_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read one Excel table into a list of row dicts (native cell types).

    Thin total boundary over :meth:`DataReader.read_excel`: a missing file
    (``FileNotFoundError``) yields ``[]`` with a warning instead of raising,
    mirroring the legacy ``Renderer._read_table_data`` behaviour. Corrupt
    files already yield ``[]`` inside ``DataReader``.
    """
    try:
        return data_reader.read_excel(path, sheet_name)
    except FileNotFoundError as e:
        logger.warning('Table file not found, using empty rows: %s', e)
        return []


def _select_row(rows: List[Dict[str, Any]],
                mode_value: RowIterationMode,
                doc_index: int,
                start_offset: int,
                lookup_column: Optional[str],
                lookup_value: Optional[str],
                source_file: str) -> Optional[Dict[str, Any]]:
    """Shared row-selection core (single implementation).

    CONSTANT honors lookup with the M7 miss warning; SEQUENTIAL exhausts
    to None; CIRCULAR wraps. Empty rows → None.
    """
    if not rows:
        return None
    if mode_value == RowIterationMode.CONSTANT:
        if lookup_column and lookup_value is not None:
            wanted = str(lookup_value).strip()
            for row in rows:
                if str(row.get(lookup_column, '')).strip() == wanted:
                    return row
            logger.warning("Lookup '%s=%s' missed in '%s'; no row selected",
                           lookup_column, lookup_value, source_file)
            return None
        return rows[0]

    offset = start_offset + doc_index

    if mode_value == RowIterationMode.SEQUENTIAL:
        if offset < len(rows):
            return rows[offset]
        return None

    if mode_value == RowIterationMode.CIRCULAR:
        return rows[offset % len(rows)]

    logger.warning("Unknown batch mode %r for '%s'; no row selected",
                   mode_value, source_file)
    return None


def resolve_source_row(rows: List[Dict[str, Any]],
                       mode: Any,
                       doc_index: int = 0,
                       start_offset: int = 0,
                       lookup_column: Optional[str] = None,
                       lookup_value: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Select one row for a document index according to the row mode.

    Thin validated adapter over the shared core: mode parsing (string or
    enum, unknown → None), non-negative index/offset guards.
    """
    if not rows:
        return None
    try:
        mode_value = RowIterationMode(mode.value if isinstance(mode, RowIterationMode) else mode)
    except ValueError:
        logger.warning("Unknown batch mode %r; no row selected", mode)
        return None
    return _select_row(rows, mode_value, max(0, int(doc_index)),
                       max(0, int(start_offset)), lookup_column,
                       lookup_value, '')


def resolve_source_row_for_config(rows: List[Dict[str, Any]],
                                  config: BatchSourceConfig,
                                  doc_index: int = 0,
                                  resume: Optional[ResumeState] = None) -> Optional[Dict[str, Any]]:
    """Select one row using a ``BatchSourceConfig`` + ``ResumeState``.

    Computes ``start_offset`` from ``resume.sources`` when the resume
    state says to continue from the last row, then delegates to
    :func:`resolve_source_row`. ``config.file`` is used as the resume key
    (same key the legacy loop uses).
    """
    start_offset = 0
    if resume is not None and resume.continue_from_last:
        try:
            start_offset = int(resume.sources.get(config.file, 0))
        except (TypeError, ValueError) as e:
            logger.warning('Broken resume offset for %r, using 0: %s',
                           config.file, e)
            start_offset = 0
    return resolve_source_row(
        rows, config.mode, doc_index, start_offset,
        lookup_column=config.lookup_column,
        lookup_value=config.lookup_value,
    )


def resolve_document_fields(
    config: TemplateConfig,
    all_raw_phs: List[str],
    doc_index: int,
    per_source_rows: Dict[str, Optional[Dict[str, str]]],
    all_table_data: Dict[str, List[Dict[str, str]]],
    cycle_data: Dict[str, List[Dict[str, str]]],
    resume_compute: ResumeState,
    now: datetime,
    user_values: Dict[str, str],
):
    """Build the effective field_values dict for a single document.

    Canonical implementation (moved verbatim from the legacy render loop):
    user_values base → raw-template today → counter → config today →
    constants → primary TABLE (legacy unmanaged fallback, M7 no-masking) →
    linked TABLE → aggregations → image paths. Returns ``(effective,
    image_paths)``. Coercion is plain ``str()`` (legacy M6 behavior);
    stripped/int-fixed coercion lives in :func:`value_to_str` for new paths.
    """
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

    # 5. TABLE — primary (not linked)
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

    # 6. TABLE — linked (same table → same row; different table → find by value)
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


def scan_project_template(project_dir: str, template_name: str) -> list:
    """Raw ``{{...}}`` placeholders of a project's template (for today-raw).

    Keeps template scanning inside the data layer so callers (prefill)
    never touch XML helpers directly.
    """
    import zipfile as _zipfile

    from docxforge.engine.render_loop import scan_raw_placeholders

    template_path = os.path.join(project_dir, 'Шаблоны', template_name)
    with _zipfile.ZipFile(template_path, 'r') as zf:
        zdata = {name: zf.read(name) for name in zf.namelist()}
    return scan_raw_placeholders(zdata)


def read_project_table(data_reader: DataReader, project_dir: str,
                       table_file: str) -> List[Dict[str, Any]]:
    """Read ``Данные/<table_file>`` of a project (verbatim legacy read).

    Missing file → ``[]`` silently; corrupt content → whatever
    ``DataReader.read_excel`` yields (``[]`` + its own error log).
    """
    path = os.path.join(project_dir, 'Данные', table_file)
    if os.path.exists(path):
        return data_reader.read_excel(path)
    return []


def resolve_legacy_source_row(
        all_rows: Optional[List[Dict[str, Any]]],
        bsc,
        source_file: str,
        doc_index: int,
        resume=None) -> Optional[Dict[str, Any]]:
    """Select one row with legacy loop semantics (adapter over shared core).

    ``bsc`` is a ``BatchSourceConfig`` or None (no config → first row);
    the resume offset comes from ``resume.sources`` exactly like the old
    loop (raw value, no coercion guards — validated configs carry ints).
    """
    if not all_rows:
        return None
    if not bsc:
        return all_rows[0]
    start_offset = 0
    if resume and resume.continue_from_last:
        start_offset = resume.sources.get(source_file, 0)
    try:
        mode_value = RowIterationMode(bsc.mode.value if isinstance(bsc.mode, RowIterationMode) else bsc.mode)
    except ValueError:
        logger.warning("Unknown batch mode %r for '%s'; no row selected",
                       bsc.mode, source_file)
        return None
    return _select_row(all_rows, mode_value, doc_index, start_offset,
                       bsc.lookup_column, bsc.lookup_value, source_file)


def build_fillings(data_reader: DataReader,
                   project_dir: str,
                   config: TemplateConfig,
                   batch_configs: dict,
                   resume_compute: ResumeState,
                   user_values: dict,
                   total_docs: int,
                   all_raw_phs: list,
                   now_factory=None) -> tuple:
    """Replicate the legacy batch iteration, emitting Filling JSON dicts.

    Reads every table once, then per document selects source rows
    (SEQUENTIAL exhaustion stops the run — never a garbage document),
    resolves ``(effective, image_paths)`` and returns one
    ``{"fields": ..., "images": ...}`` per document. Warning texts and
    stop rules are verbatim legacy (EMPTY_SEQUENTIAL/TABLE_EXHAUSTED).
    Returns ``(fillings, cycle_data)`` — cycle tables are read once here
    and travel with the run (needed by table-cycle expansion downstream).

    ``now_factory`` supplies per-document time (default ``datetime.now``);
    callers pass their own (mockable) clock.
    """
    all_table_data = {}
    for _fn, fm in config.fields.items():
        if fm.type == FieldType.TABLE and fm.file and fm.file not in all_table_data:
            all_table_data[fm.file] = read_project_table(
                data_reader, project_dir, fm.file)
    for source_file in batch_configs:
        if source_file not in all_table_data:
            all_table_data[source_file] = read_project_table(
                data_reader, project_dir, source_file)

    cycle_data = {}
    for cycle in config.cycles:
        if cycle.table not in all_table_data:
            cycle_data[cycle.table] = read_project_table(
                data_reader, project_dir, cycle.table)
        else:
            cycle_data[cycle.table] = all_table_data[cycle.table]

    # Also load tables referenced by aggregations
    for agg in config.aggregations.values():
        if agg.table not in cycle_data:
            if agg.table not in all_table_data:
                cycle_data[agg.table] = read_project_table(
                    data_reader, project_dir, agg.table)
            else:
                cycle_data[agg.table] = all_table_data[agg.table]

    fillings = []
    doc_index = 0
    clock = now_factory or datetime.now
    while doc_index < total_docs:
        now = clock()
        per_source_rows: Dict[str, Optional[Dict[str, str]]] = {}
        stopped = False
        for source_file, bsc in batch_configs.items():
            rows = all_table_data.get(source_file, [])
            row = resolve_legacy_source_row(
                rows, bsc, source_file, doc_index, resume_compute)
            if row is None and bsc.mode == RowIterationMode.SEQUENTIAL:
                if doc_index == 0:
                    logger.warning(message_for_code(
                        EMPTY_SEQUENTIAL, source=source_file))
                stopped = True
                break
            per_source_rows[source_file] = row

        if not stopped:
            for source_file, bsc in batch_configs.items():
                if bsc.mode == RowIterationMode.SEQUENTIAL:
                    rows = all_table_data.get(source_file, [])
                    start_offset = 0
                    if resume_compute and resume_compute.continue_from_last:
                        start_offset = resume_compute.sources.get(source_file, 0)
                    if start_offset + doc_index >= len(rows):
                        stopped = True
                        if doc_index == 0:
                            logger.warning(message_for_code(
                                TABLE_EXHAUSTED, source=source_file,
                                rows=len(rows), start=start_offset))

        if stopped:
            # Never render a garbage document: a SEQUENTIAL source with no
            # data for doc_index means there is nothing to render (on the
            # first document the whole run is empty).
            if doc_index == 0:
                logger.error(
                    'No documents rendered: SEQUENTIAL batch source has '
                    'no data rows for the first document.')
            break

        effective, image_paths = resolve_document_fields(
            config, all_raw_phs, doc_index, per_source_rows,
            all_table_data, cycle_data, resume_compute, now, user_values)
        fillings.append({'fields': effective, 'images': image_paths})
        doc_index += 1

    return fillings, cycle_data
