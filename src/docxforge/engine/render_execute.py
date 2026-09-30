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
    scan_raw_placeholders, process_xml,
    write_output_doc, update_resume_state,
)
from .data_formatting import build_fillings


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
        output_dir = os.path.join(renderer.project_dir, 'Результат')
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

    all_raw_phs = scan_raw_placeholders(zdata)

    total_docs = renderer._compute_total_docs(config, batch_configs, resume_compute)
    if max_docs is not None and max_docs > 0:
        if total_docs is None:
            total_docs = max_docs
        else:
            total_docs = min(total_docs, max_docs)
    if total_docs is None or total_docs <= 0:
        total_docs = 1

    # 003-json: reads happen once inside build_fillings (data layer).
    batch_primary = None
    if batch_table:
        batch_primary = batch_table
    elif batch_configs:
        for name, bsc in batch_configs.items():
            if bsc.mode == RowIterationMode.SEQUENTIAL:
                batch_primary = name
                break

    # 003-json: the single filling mechanism. Batch iteration is materialized
    # into Filling JSON by the data layer; rendering below is pure.
    fillings, cycle_data = build_fillings(
        renderer.data_reader, renderer.project_dir, config, batch_configs,
        resume_compute, user_values, total_docs, all_raw_phs,
        now_factory=datetime.now)
    if total_docs and not fillings:
        logger.error(
            'No documents rendered: SEQUENTIAL batch source has '
            'no data rows for the first document.')

    outputs = execute_render_fillings(
        renderer, template_rel_path, fillings, output_dir,
        filename_template=config.filename_template,
        directory_template=config.directory_template,
        batch_primary=batch_primary, total_docs=total_docs,
        cycles=config.cycles, cycle_data=cycle_data)
    doc_index = len(outputs)

    if resume:
        update_resume_state(resume, resume_compute, config, batch_configs, doc_index)
        # Persist updated resume state back to config only if caller provided resume
        if resume_provided:
            config.resume.last_counter_value = resume.last_counter_value
            config.resume.sources = resume.sources
            config.resume.continue_from_last = resume.continue_from_last

    return outputs


def render_effective(renderer, template_rel_path: str,
                     effective: Dict[str, str],
                     image_paths: Optional[Dict[str, str]] = None,
                     output_dir: str = None,
                     filename_template: Optional[str] = None,
                     directory_template: Optional[str] = None,
                     doc_index: int = 0,
                     total_docs: int = 1,
                     batch_primary: Optional[str] = None,
                     cycles=(), cycle_data=None) -> str:
    """Render ONE document from resolved data (the single filling mechanism).

    No config reads, no Excel, no row selection: ``effective`` is the final
    ``{field: value}`` mapping (a Filling JSON's ``fields``), ``image_paths``
    its ``images``. Only XML substitution and file writing happen here.
    """
    template_path = renderer.get_template_path(template_rel_path)
    if output_dir is None:
        output_dir = os.path.join(renderer.project_dir, 'Результат')
    os.makedirs(output_dir, exist_ok=True)

    with zipfile.ZipFile(template_path, 'r') as zf:
        zdata = {name: zf.read(name) for name in zf.namelist()}

    zdata = process_xml(zdata, cycles, cycle_data or {}, effective,
                        image_paths=image_paths or {},
                        project_dir=renderer.project_dir)
    return write_output_doc(
        zdata, output_dir, template_rel_path, doc_index, total_docs,
        batch_primary, filename_template=filename_template,
        directory_template=directory_template,
        effective_values=effective)


def execute_render_fillings(renderer, template_rel_path: str,
                            fillings: list,
                            output_dir: str = None,
                            filename_template: Optional[str] = None,
                            directory_template: Optional[str] = None,
                            batch_primary: Optional[str] = None,
                            total_docs: Optional[int] = None,
                            cycles=(), cycle_data=None) -> List[str]:
    """Render one document per Filling JSON (pure iteration, no reads)."""
    if total_docs is None:
        total_docs = len(fillings)
    outputs = []
    for doc_index, filling in enumerate(fillings):
        outputs.append(render_effective(
            renderer, template_rel_path, filling.get('fields', {}),
            image_paths=filling.get('images') or {},
            output_dir=output_dir, filename_template=filename_template,
            directory_template=directory_template, doc_index=doc_index,
            total_docs=total_docs, batch_primary=batch_primary,
            cycles=cycles, cycle_data=cycle_data))
    return outputs

