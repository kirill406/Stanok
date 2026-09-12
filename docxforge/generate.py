# -*- coding: utf-8 -*-
"""Project generation function: UI-free entry point for rendering documents."""

import json
import os
import re
import shutil
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

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


# Placeholder patterns for composite (employee/project) folder templates.
# Whitespace inside braces is tolerated, e.g. both "{{employee}}" and "{{ employee }}".
_EMPLOYEE_PLACEHOLDER_RE = re.compile(r'\{\{\s*employee\s*\}\}')
_PROJECT_NAME_PLACEHOLDER_RE = re.compile(r'\{\{\s*project_name\s*\}\}')


def parse_composite_template(template: Optional[str]) -> Dict[str, Any]:
    """
    Parse a folder-name template and detect composite (employee/project) mode.

    A template is composite only if ALL of the following hold:
      - it is a non-empty string,
      - it contains ``/``,
      - it contains the ``{{employee}}`` placeholder,
      - it contains the ``{{project_name}}`` placeholder.

    Everything else (empty/None template, no ``/``, only one placeholder)
    is flat mode for backward compatibility.

    Args:
        template: Folder-name template, e.g. ``"{{employee}}/{{project_name}}"``.

    Returns:
        Dict with keys:
          - ``is_composite`` (bool): True if composite mode detected.
          - ``employee_part`` (str): segment before the first ``/``
            (empty string when not composite).
          - ``project_part`` (str): remainder after the first ``/``
            (the original template, or "" when not composite).
    """
    if not template or not isinstance(template, str) or not template.strip():
        return {'is_composite': False, 'employee_part': '', 'project_part': template or ''}

    if '/' not in template:
        return {'is_composite': False, 'employee_part': '', 'project_part': template}

    if not _EMPLOYEE_PLACEHOLDER_RE.search(template):
        return {'is_composite': False, 'employee_part': '', 'project_part': template}

    if not _PROJECT_NAME_PLACEHOLDER_RE.search(template):
        return {'is_composite': False, 'employee_part': '', 'project_part': template}

    employee_part, project_part = template.split('/', 1)
    return {
        'is_composite': True,
        'employee_part': employee_part,
        'project_part': project_part,
    }


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
    # Phase 2: detect composite (employee/project) vs flat mode up front.
    # Composite templates are delegated to create_nested_employee_projects()
    # (Phase 3); flat templates continue on the unchanged path below.
    parsed = parse_composite_template(folder_name_template)
    if parsed['is_composite']:
        logger.info(
            'Composite folder template detected (employee=%r project=%r); '
            'routing to nested employee/project generation.',
            parsed['employee_part'], parsed['project_part'],
        )
        return create_nested_employee_projects(
            project_path, template_name, folder_name_template, max_projects
        )

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


# ---------------------------------------------------------------------------
# Phase 4: nested project file operations (used by Phase 3 grouping core).
# Layout per SPEC: <project>/данные/ + <project>/шаблоны/ + <project>/результат/
#                  + <project>/проект.docxforge ; settings live in employee dir.
# ---------------------------------------------------------------------------

#: Accepted source data-folder spellings (existing projects use capital).
DATA_DIR_CANDIDATES = ('Данные', 'данные')
#: Nested project subfolder names (SPEC, lowercase).
NESTED_DATA_DIR = 'данные'
NESTED_TEMPLATES_DIR = 'шаблоны'
NESTED_RESULT_DIR = 'результат'
NESTED_PROJECT_FILE = 'проект.docxforge'
EMPLOYEE_SETTINGS_FILE = 'docxforge_settings.json'


def _resolve_source_data_dir(src_project_dir: str) -> Optional[str]:
    """Return existing data folder in source project (tries both spellings)."""
    for name in DATA_DIR_CANDIDATES:
        candidate = os.path.join(src_project_dir, name)
        if os.path.isdir(candidate):
            return candidate
    return None


def copy_data_folder(src_project_dir: str, dst_project_dir: str) -> str:
    """Copy the entire source `Данные/` folder (no slicing, all files as-is).

    Returns destination path. Raises GenerationError if source data missing.
    """
    src_data = _resolve_source_data_dir(src_project_dir)
    if src_data is None:
        raise GenerationError(
            f'Data folder not found in source project: {src_project_dir}'
        )
    dst_data = os.path.join(dst_project_dir, NESTED_DATA_DIR)
    try:
        shutil.copytree(src_data, dst_data, dirs_exist_ok=True)
    except PermissionError as e:
        raise GenerationError(f'Permission denied copying data folder: {e}') from e
    except OSError as e:
        raise GenerationError(f'Failed to copy data folder: {e}') from e
    logger.info(f'Copied data folder: {src_data} -> {dst_data}')
    return dst_data


def copy_template_file(src_template_path: str, dst_project_dir: str) -> str:
    """Copy template .docx into nested `<project>/шаблоны/`. Returns dst path."""
    if not os.path.exists(src_template_path):
        raise GenerationError(f'Template file not found: {src_template_path}')
    dst_dir = os.path.join(dst_project_dir, NESTED_TEMPLATES_DIR)
    os.makedirs(dst_dir, exist_ok=True)
    dst_template = os.path.join(dst_dir, os.path.basename(src_template_path))
    try:
        shutil.copy2(src_template_path, dst_template)
    except PermissionError as e:
        raise GenerationError(f'Permission denied copying template: {e}') from e
    except OSError as e:
        raise GenerationError(f'Failed to copy template file: {e}') from e
    logger.info(f'Copied template: {src_template_path} -> {dst_template}')
    return dst_template


def create_result_folder(dst_project_dir: str) -> str:
    """Create empty nested `<project>/результат/`. Returns its path."""
    result_dir = os.path.join(dst_project_dir, NESTED_RESULT_DIR)
    try:
        os.makedirs(result_dir, exist_ok=True)
    except PermissionError as e:
        raise GenerationError(
            f'Permission denied creating result folder: {e}'
        ) from e
    return result_dir


def write_nested_project_config(
    dst_project_dir: str,
    template_name: str,
    new_config: TemplateConfig,
    version: int = 2,
) -> str:
    """Write `проект.docxforge` for a nested project. Returns file path."""
    new_project = Project(version=version)
    new_project.templates[template_name] = new_config
    config_path = os.path.join(dst_project_dir, NESTED_PROJECT_FILE)
    try:
        new_project.to_file(config_path)
    except (PermissionError, OSError) as e:
        raise GenerationError(f'Failed to write project config: {e}') from e
    return config_path


def write_employee_settings(
    employee_dir: str,
    employee: str,
    employee_folder: str,
    projects: List[Dict[str, Any]],
) -> str:
    """Write `docxforge_settings.json` listing employee's projects (SPEC schema)."""
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    payload = {
        'employee': employee,
        'employee_folder': employee_folder,
        'created_at': now,
        'projects': [
            {
                'name': p.get('name', ''),
                'folder': p.get('folder', ''),
                'template': p.get('template', ''),
                'row_index': p.get('row_index', 0),
                'created_at': p.get('created_at', now),
            }
            for p in projects
        ],
    }
    settings_path = os.path.join(employee_dir, EMPLOYEE_SETTINGS_FILE)
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except (PermissionError, OSError) as e:
        raise GenerationError(f'Failed to write employee settings: {e}') from e
    logger.info(f'Wrote employee settings: {settings_path}')
    return settings_path


def setup_nested_project_files(
    src_project_dir: str,
    dst_project_dir: str,
    src_template_path: str,
    template_name: str,
    new_config: TemplateConfig,
    version: int = 2,
) -> Dict[str, str]:
    """Per-project file assembly for the Phase 3 nested loop.

    Creates <project>/{данные/,шаблоны/,результат/,проект.docxforge}.
    Rolls back (removes dst dir) on any failure. Returns dict of created paths.
    """
    os.makedirs(dst_project_dir, exist_ok=True)
    try:
        data_dir = copy_data_folder(src_project_dir, dst_project_dir)
        template_copy = copy_template_file(src_template_path, dst_project_dir)
        result_dir = create_result_folder(dst_project_dir)
        config_path = write_nested_project_config(
            dst_project_dir, template_name, new_config, version
        )
    except Exception:
        shutil.rmtree(dst_project_dir, ignore_errors=True)
        raise
    return {
        'project_dir': dst_project_dir,
        'data_dir': data_dir,
        'template': template_copy,
        'result_dir': result_dir,
        'config': config_path,
    }


_INVALID_FOLDER_CHARS = '<>:"/\\|?*'


def _sanitize_folder_name(name: Optional[str]) -> str:
    """Make a filesystem-safe folder name from a resolved value.

    Replaces Windows-unsafe characters and control characters with '_',
    strips trailing dots/spaces and truncates to 100 characters.
    Returns '' when nothing usable is left (caller applies N-fallback).
    """
    if name is None:
        return ''
    text = ''.join('_' if (ch in _INVALID_FOLDER_CHARS or ord(ch) < 32) else ch
                   for ch in str(name).strip())
    text = text.strip().rstrip('.')
    if len(text) > 100:
        text = text[:100].rstrip('.').strip()
    return text


def _unique_folder_name(base: str, used: set, parent_dir: str) -> str:
    """Return a unique folder name, appending _1, _2... on collision.

    Checks both the in-run ``used`` set and pre-existing directories on disk.
    Registers the chosen name in ``used``.
    """
    candidate = base
    suffix = 0
    while candidate in used or os.path.exists(os.path.join(parent_dir, candidate)):
        suffix += 1
        candidate = f'{base}_{suffix}'
    used.add(candidate)
    return candidate


def _rollback_created(paths: List[str]) -> None:
    """Remove directories created during a failed run, in reverse order."""
    for path in reversed(paths):
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            logger.warning(f'Rollback failed for {path}: {e}')


def create_nested_employee_projects(
    project_path: str,
    template_name: str,
    folder_name_template: str,
    max_projects: Optional[int] = None,
    employee_column: str = 'employee',
    project_column: str = 'project_name',
) -> Tuple[str, int, int]:
    """Create nested Employee/Project folders from a batch source.

    Reads the primary SEQUENTIAL batch source, groups rows by ``employee_column``
    and creates ``Projects/<employee>/<project>/`` folders. Each employee folder
    gets a ``docxforge_settings.json`` listing its projects; each project folder
    gets a full copy of ``Данные/``, the template in ``Шаблоны/``, an empty
    ``Результат/`` and a ``проект.docxforge`` (TABLE fields frozen to row values
    as CONSTANT, COUNTER reset, batch sources forced to CONSTANT).

    Folder parts are obtained via the Phase 2 helper ``parse_composite_template``:
    for a composite template the employee/project parts resolve each folder;
    otherwise the employee folder comes from the raw employee value and the
    whole template resolves the project folder (backward compatible).

    NOTE: ``max_projects`` is the 4th positional parameter so the composite
    routing in ``create_projects_from_template`` can pass it positionally.

    Args:
        project_path: Source project directory (with проект.docxforge).
        template_name: Template filename (relative to Шаблоны/).
        folder_name_template: Composite template, e.g. "{{employee}}/{{project_name}}".
        max_projects: Cap on the TOTAL number of projects (only when > 0).
        employee_column: Batch column used for grouping.
        project_column: Batch column used for project folders/names.

    Returns:
        Tuple (projects_dir, employee_count, project_count).

    Raises:
        GenerationError: Missing project/template/batch config, missing
            employee/project column, empty data, or filesystem failure
            (created directories are rolled back first).
    """
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
    for _name, bsc in template_config.batch_sources.items():
        if bsc.mode == RowIterationMode.SEQUENTIAL:
            primary_source_config = bsc
            break
    if primary_source_config is None:
        raise GenerationError('No sequential batch source found (required for project creation)')

    data_reader = DataReader()
    all_batch_data = data_reader.read_all_batch_sources(project_path, template_config.batch_sources)
    primary_rows = all_batch_data.get(primary_source_config.file, [])
    if not primary_rows:
        raise GenerationError(
            f'Primary batch source "{primary_source_config.file}" has no data rows')

    available_columns = set()
    for row in primary_rows:
        available_columns.update(row.keys())
    if employee_column not in available_columns:
        raise GenerationError(
            f'Column "{employee_column}" not found in batch source '
            f'"{primary_source_config.file}" (required for employee grouping)')
    if project_column not in available_columns:
        raise GenerationError(
            f'Column "{project_column}" not found in batch source '
            f'"{primary_source_config.file}" (required for project folders)')

    indexed_rows = list(enumerate(primary_rows))
    if max_projects is not None and max_projects > 0:
        indexed_rows = indexed_rows[:max_projects]

    groups: Dict[str, list] = {}
    for row_idx, row in indexed_rows:
        key = str(row.get(employee_column, '') or '').strip()
        groups.setdefault(key, []).append((row_idx, row))

    raw_placeholders: List[str] = []
    try:
        scan_result = scan_template(template_full)
        raw_placeholders = scan_result.get('all', [])
    except Exception as e:
        logger.warning(f'Could not scan template for placeholders: {e}')

    parsed = parse_composite_template(folder_name_template or '')
    if parsed['is_composite']:
        employee_part: Optional[str] = parsed['employee_part']
        project_part = parsed['project_part']
    else:
        employee_part = None
        project_part = folder_name_template or ''

    projects_dir = os.path.join(project_path, 'Projects')
    try:
        os.makedirs(projects_dir, exist_ok=True)
    except OSError as e:
        raise GenerationError(f'Permission denied creating Projects directory: {e}') from e

    source_data_dir = os.path.join(project_path, 'Данные')
    created_paths: List[str] = []
    used_employee_names = set()
    employee_counter = 0
    project_count = 0

    try:
        for raw_employee, items in groups.items():
            employee_counter += 1
            if employee_part:
                resolved_employee = _resolve_folder_name_template(
                    employee_part, items[0][1], template_config, raw_placeholders)
            else:
                resolved_employee = raw_employee
            employee_base = _sanitize_folder_name(resolved_employee)
            if not employee_base:
                employee_base = f'employee_{employee_counter}'
            employee_folder = _unique_folder_name(
                employee_base, used_employee_names, projects_dir)
            employee_dir = os.path.join(projects_dir, employee_folder)
            os.makedirs(employee_dir, exist_ok=False)
            created_paths.append(employee_dir)

            display_employee = raw_employee if raw_employee else employee_folder

            used_project_names = set()
            project_counter = 0
            settings_projects = []
            for row_idx, row in items:
                project_counter += 1
                resolved_project = _resolve_folder_name_template(
                    project_part or '{{%s}}' % project_column,
                    row, template_config, raw_placeholders)
                project_base = _sanitize_folder_name(resolved_project)
                if not project_base:
                    project_base = f'project_{project_counter}'
                project_folder = _unique_folder_name(
                    project_base, used_project_names, employee_dir)
                project_dir = os.path.join(employee_dir, project_folder)
                os.makedirs(project_dir, exist_ok=False)
                created_paths.append(project_dir)

                data_dir = os.path.join(project_dir, 'Данные')
                if os.path.isdir(source_data_dir):
                    shutil.copytree(source_data_dir, data_dir)
                else:
                    os.makedirs(data_dir, exist_ok=True)

                templates_subdir = os.path.join(project_dir, 'Шаблоны')
                os.makedirs(templates_subdir, exist_ok=True)
                _copy_template_files(template_full, templates_subdir)

                os.makedirs(os.path.join(project_dir, 'Результат'), exist_ok=True)

                new_config = _build_project_config(
                    template_config, row, primary_source_config.file)
                for bsc in new_config.batch_sources.values():
                    bsc.mode = RowIterationMode.CONSTANT
                    bsc.continue_from_last = False
                new_project = Project(version=2)
                new_project.templates[template_name] = new_config
                new_project.to_file(os.path.join(project_dir, 'проект.docxforge'))

                stamp = datetime.now().isoformat(timespec='seconds')
                settings_projects.append({
                    'name': str(row.get(project_column, '') or project_folder),
                    'folder': project_folder,
                    'template': template_name,
                    'row_index': row_idx,
                    'created_at': stamp,
                })
                project_count += 1

            settings = {
                'employee': display_employee,
                'employee_folder': employee_folder,
                'created_at': datetime.now().isoformat(timespec='seconds'),
                'projects': settings_projects,
            }
            with open(os.path.join(employee_dir, 'docxforge_settings.json'),
                      'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _rollback_created(created_paths)
        raise GenerationError(f'Failed to create nested projects: {e}') from e

    logger.info(
        f'Created {employee_counter} employee(s), {project_count} project(s) in {projects_dir}')
    return projects_dir, employee_counter, project_count


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
