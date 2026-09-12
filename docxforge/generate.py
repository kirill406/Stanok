# -*- coding: utf-8 -*-
"""Project generation function: UI-free entry point for rendering documents."""

import os
import shutil
import logging
from typing import List, Optional, Tuple, Dict

from docxforge.engine.schema import (
    Project, ResumeState, TemplateConfig, FieldMapping, FieldType,
    BatchSourceConfig, RowIterationMode
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer
from docxforge.engine.template_parser import scan_template


logger = logging.getLogger(__name__)


class GenerationError(Exception):
    """Raised when document generation fails."""
    pass


def generate_project(
    project_path: str,
    template_name: Optional[str] = None,
    num_docs: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> List[str]:
    project_file = os.path.join(project_path, 'проект.docxforge')
    if not os.path.exists(project_file):
        raise GenerationError(f'Project file not found: {project_file}')

    project = Project.from_file(project_file)
    if not project.templates:
        raise GenerationError('No templates configured in project')

    if template_name is None:
        template_name = next(iter(project.templates.keys()))
    elif template_name not in project.templates:
        raise GenerationError(f'Template not configured: {template_name}')

    template_full = os.path.join(project_path, 'Шаблоны', template_name)
    if not os.path.exists(template_full):
        raise GenerationError(f'Template file not found: {template_full}')

    data_reader = DataReader()
    renderer = Renderer(project_path, data_reader)
    renderer.project = project

    if output_dir is None:
        legacy_output = os.path.join(project_path, 'output')
        new_output = os.path.join(project_path, 'Результат')
        if os.path.exists(legacy_output):
            output_dir = legacy_output
        else:
            output_dir = new_output
    os.makedirs(output_dir, exist_ok=True)

    template_config = project.templates[template_name]
    resume = template_config.resume
    if resume is None:
        resume = ResumeState(continue_from_last=True)

    try:
        outputs = renderer.render(
            template_name,
            {},
            output_dir=output_dir,
            max_docs=num_docs,
            resume=resume,
        )
    except Exception as e:
        raise GenerationError(f'Generation failed: {e}') from e

    if not outputs:
        raise GenerationError('No documents generated (check data sources and batch config)')

    renderer.save_project()
    return outputs


def create_projects_from_template(
    project_path: str,
    template_name: str,
    folder_name_template: str,
    max_projects: Optional[int] = None,
) -> Tuple[str, int]:
    project_file = os.path.join(project_path, 'проект.docxforge')
    if not os.path.exists(project_file):
        raise GenerationError(f'Project file not found: {project_file}')

    project = Project.from_file(project_file)
    if not project.templates:
        raise GenerationError('No templates configured in project')

    if template_name not in project.templates:
        raise GenerationError(f'Template not configured: {template_name}')

    template_config = project.templates[template_name]
    template_full = os.path.join(project_path, 'Шаблоны', template_name)
    if not os.path.exists(template_full):
        raise GenerationError(f'Template file not found: {template_full}')

    if not template_config.batch_sources:
        raise GenerationError('No batch sources configured for this template')

    primary_source_config = None
    for name, bsc in template_config.batch_sources.items():
        if bsc.mode == RowIterationMode.SEQUENTIAL:
            primary_source_config = bsc
            break

    if primary_source_config is None:
        raise GenerationError('No sequential batch source found (required for project creation)')

    data_reader = DataReader()
    all_batch_data = data_reader.read_all_batch_sources(project_path, template_config.batch_sources)

    primary_rows = all_batch_data.get(primary_source_config.file, [])
    if not primary_rows:
        raise GenerationError(f'Primary batch source "{primary_source_config.file}" has no data rows')

    num_rows = len(primary_rows)
    if max_projects is not None and max_projects > 0:
        num_rows = min(num_rows, max_projects)

    projects_dir = os.path.join(project_path, 'Projects')
    try:
        os.makedirs(projects_dir, exist_ok=True)
    except PermissionError as e:
        raise GenerationError(f'Permission denied creating Projects directory: {e}') from e

    raw_placeholders = []
    try:
        scan_result = scan_template(template_full)
        raw_placeholders = scan_result.get('all', [])
    except Exception as e:
        logger.warning(f'Could not scan template for placeholders: {e}')

    created_count = 0
    used_folder_names = set()

    for row_idx in range(num_rows):
        row_data = primary_rows[row_idx]

        folder_name = _resolve_folder_name_template(
            folder_name_template, row_data, template_config, raw_placeholders
        )

        if not folder_name or folder_name.strip() == '':
            folder_name = f'project_{row_idx + 1}'

        original_folder_name = folder_name
        counter = 1
        while folder_name in used_folder_names:
            folder_name = f'{original_folder_name}_{counter}'
            counter += 1
        used_folder_names.add(folder_name)

        project_subdir = os.path.join(projects_dir, folder_name)
        try:
            os.makedirs(project_subdir, exist_ok=False)
            templates_subdir = os.path.join(project_subdir, 'Шаблоны')
            os.makedirs(templates_subdir, exist_ok=False)
        except PermissionError as e:
            raise GenerationError(f'Permission denied creating project directory: {e}') from e
        except FileExistsError as e:
            raise GenerationError(f'Project directory already exists: {project_subdir}') from e

        new_config = _build_project_config(template_config, row_data, primary_source_config.file)

        new_project_file = os.path.join(project_subdir, 'проект.docxforge')
        new_project = Project(version=2)
        new_project.templates[template_name] = new_config
        try:
            new_project.to_file(new_project_file)
        except Exception as e:
            shutil.rmtree(project_subdir, ignore_errors=True)
            raise GenerationError(f'Failed to write project config: {e}') from e

        try:
            _copy_template_files(template_full, templates_subdir)
        except Exception as e:
            shutil.rmtree(project_subdir, ignore_errors=True)
            raise GenerationError(f'Failed to copy template files: {e}') from e

        created_count += 1

    return projects_dir, created_count


def _resolve_folder_name_template(
    template: str,
    row_data: Dict[str, str],
    config: TemplateConfig,
    raw_placeholders: List[str],
) -> str:
    effective = {}

    for fn, fm in config.fields.items():
        if fm.type == FieldType.CONSTANT:
            effective[fn] = fm.value or ''

    for fn, fm in config.fields.items():
        if fm.type == FieldType.TABLE and not fm.linked_to:
            if fm.file and fm.column and fm.file in row_data:
                effective[fn] = row_data.get(fm.column, '')

    for key, value in row_data.items():
        if key not in effective:
            effective[key] = value

    result = template
    for key, value in effective.items():
        result = result.replace('{{ ' + key + ' }}', str(value))
        result = result.replace('{{' + key + '}}', str(value))

    return result.strip()


def _build_project_config(
    template_config: TemplateConfig,
    row_data: Dict[str, str],
    primary_source_file: str,
) -> TemplateConfig:
    """Build per-project config: TABLE→CONSTANT, COUNTER reset, batch→CONSTANT.

    Args:
        template_config: Source template configuration.
        row_data: Resolved row as {column: value} dict (keys are column names).
        primary_source_file: Name of the primary batch file (kept for signature
            compatibility; row_data already holds the resolved row values).

    Returns:
        New TemplateConfig with transformed fields and CONSTANT batch sources.
    """
    new_config = TemplateConfig()

    for fn, fm in template_config.fields.items():
        if fm.type == FieldType.CONSTANT:
            new_config.fields[fn] = FieldMapping(type=FieldType.CONSTANT, value=fm.value)
        elif fm.type == FieldType.TABLE:
            if fm.column and fm.column in row_data:
                value = row_data.get(fm.column, '')
                new_config.fields[fn] = FieldMapping(
                    type=FieldType.CONSTANT,
                    value=str(value) if value is not None else '',
                )
            else:
                # No row value available: keep original mapping as-is.
                new_config.fields[fn] = FieldMapping(
                    type=fm.type,
                    value=fm.value,
                    file=fm.file,
                    column=fm.column,
                    linked_to=fm.linked_to,
                    start=fm.start,
                    step=fm.step,
                    format=fm.format,
                    multiplier=fm.multiplier,
                )
        elif fm.type == FieldType.COUNTER:
            # Reset to start: fresh counter, resume state cleared below.
            new_config.fields[fn] = FieldMapping(
                type=FieldType.COUNTER,
                start=fm.start,
                step=fm.step,
                format=fm.format,
            )
        else:
            new_fm = FieldMapping(type=fm.type)
            new_fm.value = fm.value
            new_fm.format = fm.format
            new_fm.file = fm.file
            new_fm.column = fm.column
            new_fm.linked_to = fm.linked_to
            new_fm.function = fm.function
            new_fm.multiplier = fm.multiplier
            new_fm.start = fm.start
            new_fm.step = fm.step
            new_config.fields[fn] = new_fm

    # All batch sources → CONSTANT (project data already copied into данные/).
    new_config.batch_sources = {}
    for name, bsc in template_config.batch_sources.items():
        new_config.batch_sources[name] = BatchSourceConfig(
            file=bsc.file,
            mode=RowIterationMode.CONSTANT,
            lookup_column=None,
            lookup_value=None,
            continue_from_last=False,
            counter_column=None,
            counter_current_row=1,
        )

    new_config.cycles = list(template_config.cycles)
    new_config.aggregations = dict(template_config.aggregations)
    new_config.filename_template = template_config.filename_template
    new_config.directory_template = template_config.directory_template
    new_config.resume = ResumeState(continue_from_last=False)

    return new_config


def _copy_template_files(src_template: str, dst_templates_dir: str) -> None:
    dst_template = os.path.join(dst_templates_dir, os.path.basename(src_template))
    if os.path.exists(src_template):
        shutil.copy2(src_template, dst_template)


def generate_cli(project_path: str, template: str = None, count: int = None, out: str = None) -> List[str]:
    """CLI-friendly wrapper that prints progress."""
    print(f'Project: {project_path}')
    print(f'Template: {template or "first configured"}')
    print(f'Count: {count or "auto"}')
    print(f'Output: {out or "<project>/output/"}')

    outputs = generate_project(project_path, template, count, out)

    print(f'Generated: {len(outputs)} document(s)')
    for o in outputs:
        print(f'  {os.path.basename(o)}')
    return outputs
