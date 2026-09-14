# -*- coding: utf-8 -*-
"""Execute render loop: the main document generation orchestration."""

import zipfile
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)

from .schema import (
    TemplateConfig, FieldType, BatchSourceConfig, RowIterationMode, ResumeState,
)
from .render_loop import (
    scan_raw_placeholders, resolve_field_values, process_xml,
    write_output_doc, update_resume_state,
)


def execute_render(renderer, template_rel_path: str,
                   user_values: Dict[str, str],
                   batch_table: Optional[str] = None,
                   output_dir: str = None,
                   batch_configs: Optional[Dict[str, BatchSourceConfig]] = None,
                   max_docs: Optional[int] = None,
                   resume: Optional[ResumeState] = None) -> List[str]:
    """Render template into one or more output documents.

    Delegated from Renderer.render() - keeps Renderer class slim.
    """
    template_path = renderer.get_template_path(template_rel_path)
    config = renderer.project.templates.get(template_rel_path, TemplateConfig()) if renderer.project else TemplateConfig()

    if output_dir is None:
        # Backward compatibility: use existing "output" folder if present
        legacy_output = os.path.join(renderer.project_dir, 'output')
        new_output = os.path.join(renderer.project_dir, 'Результат')
        if os.path.exists(legacy_output):
            output_dir = legacy_output
        else:
            output_dir = new_output
    os.makedirs(output_dir, exist_ok=True)

    if batch_configs is None:
        batch_configs = dict(config.batch_sources)

    if batch_table and batch_table not in batch_configs:
        batch_configs[batch_table] = BatchSourceConfig(
            file=batch_table, mode=RowIterationMode.SEQUENTIAL)

    resume_provided = resume is not None
    if resume is None:
        if config.resume:
            # Create a copy to avoid mutating config.resume directly
            resume = ResumeState(
                last_counter_value=config.resume.last_counter_value,
                sources=dict(config.resume.sources),
                continue_from_last=config.resume.continue_from_last,
            )
        else:
            resume = ResumeState(continue_from_last=True)

    resume_compute = ResumeState(
        last_counter_value=resume.last_counter_value,
        sources=dict(resume.sources),
        continue_from_last=resume.continue_from_last,
    )

    with zipfile.ZipFile(template_path, 'r') as zf:
        zdata = {name: zf.read(name) for name in zf.namelist()}

    zdata_orig = {name: data for name, data in zdata.items()}

    all_raw_phs = scan_raw_placeholders(zdata)

    total_docs = renderer._compute_total_docs(config, batch_configs, resume_compute)
    if max_docs is not None and max_docs > 0:
        if total_docs is None:
            total_docs = max_docs
        else:
            total_docs = min(total_docs, max_docs)
    if total_docs is None or total_docs <= 0:
        total_docs = 1

    # Pre-read all table data
    all_table_data = {}
    for fn, fm in config.fields.items():
        if fm.type == FieldType.TABLE and fm.file and fm.file not in all_table_data:
            all_table_data[fm.file] = renderer._read_table_data(fm.file)
    for source_file in batch_configs:
        if source_file not in all_table_data:
            all_table_data[source_file] = renderer._read_table_data(source_file)

    cycle_data = {}
    for cycle in config.cycles:
        if cycle.table not in all_table_data:
            cycle_data[cycle.table] = renderer._read_table_data(cycle.table)
        else:
            cycle_data[cycle.table] = all_table_data[cycle.table]

    # Also load tables referenced by aggregations
    for agg in config.aggregations.values():
        if agg.table not in cycle_data:
            if agg.table not in all_table_data:
                cycle_data[agg.table] = renderer._read_table_data(agg.table)
            else:
                cycle_data[agg.table] = all_table_data[agg.table]

    batch_primary = None
    if batch_table:
        batch_primary = batch_table
    elif batch_configs:
        for name, bsc in batch_configs.items():
            if bsc.mode == RowIterationMode.SEQUENTIAL:
                batch_primary = name
                break

    warnings = []
    outputs = []
    doc_index = 0

    while doc_index < total_docs:
        zdata = {name: data for name, data in zdata_orig.items()}
        now = datetime.now()

        per_source_rows: Dict[str, Optional[Dict[str, str]]] = {}
        stopped = False
        for source_file, bsc in batch_configs.items():
            rows = all_table_data.get(source_file, [])
            row = renderer._resolve_row_for_source(
                source_file, doc_index, batch_configs, resume_compute, rows)
            if row is None and bsc.mode == RowIterationMode.SEQUENTIAL:
                if doc_index == 0:
                    warnings.append(
                        'Таблица «%s» не имеет данных для генерации.' % source_file)
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
                            warnings.append(
                                'Таблица «%s» исчерпана (строк: %d, начало: %d).' %
                                (source_file, len(rows), start_offset))

        if stopped:
            # Never render a garbage document: a SEQUENTIAL source with no
            # data for doc_index means there is nothing to render (on the
            # first document the whole run is empty).
            for message in warnings:
                logger.warning(message)
            if doc_index == 0:
                logger.error(
                    'No documents rendered: SEQUENTIAL batch source has '
                    'no data rows for the first document.')
            break

        effective, image_paths = resolve_field_values(
            config, all_raw_phs, doc_index, per_source_rows,
            all_table_data, cycle_data, resume_compute, now, user_values)

        zdata = process_xml(zdata, config, cycle_data, effective,
                           image_paths=image_paths,
                           project_dir=renderer.project_dir)

        out_path = write_output_doc(
            zdata, output_dir, template_rel_path, doc_index, total_docs, batch_primary,
            filename_template=config.filename_template,
            directory_template=config.directory_template,
            effective_values=effective)

        outputs.append(out_path)
        doc_index += 1

    if resume:
        update_resume_state(resume, resume_compute, config, batch_configs, doc_index)
        # Persist updated resume state back to config only if caller provided resume
        if resume_provided:
            config.resume.last_counter_value = resume.last_counter_value
            config.resume.sources = resume.sources
            config.resume.continue_from_last = resume.continue_from_last

    return outputs

