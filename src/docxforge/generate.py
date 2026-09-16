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
    BatchSourceConfig, RowIterationMode, limit_rows, substitute_placeholders,
    advance_counter_after_creation,
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.errors import (
    EMPTY_SEQUENTIAL,
    NO_DOCUMENTS_GENERATED,
    EngineError,
    message_for_code,
)
from docxforge.engine.renderer import Renderer


logger = logging.getLogger(__name__)


class GenerationError(EngineError):
    """Raised when document generation fails (carries ``code``)."""


# Placeholder patterns for composite (employee/project) folder templates.
# Placeholder names are dynamic: the {{...}} before '/' names the employee
# (grouping) column, the one after '/' names the project column, e.g.
# "{{фио_сотрудника}}/{{проект}}". Whitespace inside braces is tolerated.
_GENERIC_PLACEHOLDER_RE = re.compile(r'\{\{\s*([^}/]+?)\s*\}\}')


def _extract_first_placeholder_name(part: str) -> Optional[str]:
    """Return the first {{name}} placeholder name in a template part, or None."""
    if not part:
        return None
    match = _GENERIC_PLACEHOLDER_RE.search(part)
    if not match:
        return None
    return match.group(1).strip() or None


def parse_composite_template(template: Optional[str]) -> Dict[str, Any]:
    """
    Parse a folder-name template and detect composite (employee/project) mode.

    A template is composite only if ALL of the following hold:
      - it is a non-empty string,
      - it contains ``/``,
      - the part before the first ``/`` contains a ``{{...}}`` placeholder
        (names the employee/grouping column),
      - the part after the first ``/`` contains a ``{{...}}`` placeholder
        (names the project column).

    Placeholder names are dynamic and taken from table columns, e.g.
    ``"{{фио_сотрудника}}/{{проект}}"``. The legacy
    ``"{{employee}}/{{project_name}}"`` keeps working: its column names are
    ``employee`` and ``project_name``.

    Everything else (empty/None template, no ``/``, placeholder on only
    one side) is flat mode for backward compatibility.

    Args:
        template: Folder-name template, e.g. ``"{{фио_сотрудника}}/{{проект}}"``.

    Returns:
        Dict with keys:
          - ``is_composite`` (bool): True if composite mode detected.
          - ``employee_part`` (str): segment before the first ``/``
            (empty string when not composite).
          - ``project_part`` (str): remainder after the first ``/``
            (the original template, or "" when not composite).
          - ``employee_column`` (str|None): placeholder name from the
            employee part (None when not composite).
          - ``project_column`` (str|None): placeholder name from the
            project part (None when not composite).
    """
    if not template or not isinstance(template, str) or not template.strip():
        return {'is_composite': False, 'employee_part': '', 'project_part': template or '',
                'employee_column': None, 'project_column': None}

    if '/' not in template:
        return {'is_composite': False, 'employee_part': '', 'project_part': template,
                'employee_column': None, 'project_column': None}

    employee_part, project_part = template.split('/', 1)
    employee_column = _extract_first_placeholder_name(employee_part)
    project_column = _extract_first_placeholder_name(project_part)

    if not employee_column or not project_column:
        return {'is_composite': False, 'employee_part': '', 'project_part': template,
                'employee_column': None, 'project_column': None}

    return {
        'is_composite': True,
        'employee_part': employee_part,
        'project_part': project_part,
        'employee_column': employee_column,
        'project_column': project_column,
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
        output_dir = os.path.join(project_path, 'Результат')
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
    except GenerationError:
        raise
    except EngineError as e:
        raise GenerationError(str(e), code=getattr(e, 'code', None)) from e
    except Exception as e:
        raise GenerationError(f'Generation failed: {e}') from e

    if not outputs:
        raise GenerationError(
            message_for_code(NO_DOCUMENTS_GENERATED),
            code=EMPTY_SEQUENTIAL)

    renderer.save_project()
    return outputs


def create_projects_from_template(
    project_path: str,
    template_name: str,
    folder_name_template: str,
    max_projects: Optional[int] = None,
    home_dir: Optional[str] = None,
) -> Tuple[str, int]:
    """Create per-row projects for a flat template (full pipeline).

    TABLE fields are frozen to row values as CONSTANT; the whole Данные/
    folder is copied per project. Composite templates are routed to
    ``create_nested_employee_projects``.

    See also (M2): ``schema.create_projects`` — the engine-level entry
    point (keeps TABLE mappings). Both share the folder-name contract
    (resolve→sanitize→unique); see ``tests/test_m2_contract.py``.
    """
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
            project_path, template_name, folder_name_template, max_projects,
            employee_column=parsed.get('employee_column') or 'employee',
            project_column=parsed.get('project_column') or 'project_name',
            home_dir=home_dir,
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

    primary_rows = limit_rows(primary_rows, max_projects)
    num_rows = len(primary_rows)

    projects_dir = os.path.join(project_path, 'Projects')
    try:
        os.makedirs(projects_dir, exist_ok=True)
    except PermissionError as e:
        raise GenerationError(f'Permission denied creating Projects directory: {e}') from e

    created_count = 0
    used_folder_names = set()
    created_paths: List[str] = []
    src_data_dir = _resolve_source_data_dir(project_path)

    try:
        for row_idx in range(num_rows):
            row_data = primary_rows[row_idx]

            folder_name = _resolve_folder_name_template(
                folder_name_template, row_data, template_config
            )

            if not folder_name or folder_name.strip() == '':
                folder_name = f'project_{row_idx + 1}'
            if _GENERIC_PLACEHOLDER_RE.search(folder_name):
                # Never create literal "{{ ... }}" folders: fall back to
                # a numbered name (field mapping incomplete).
                logger.warning(
                    'Folder template %r did not resolve for row %s; '
                    'using numbered fallback', folder_name_template, row_idx)
                folder_name = f'project_{row_idx + 1}'
            folder_base = _sanitize_folder_name(folder_name)
            if not folder_base:
                folder_base = f'project_{row_idx + 1}'
            folder_name = _unique_folder_name(
                folder_base, used_folder_names, projects_dir)

            project_subdir = os.path.join(projects_dir, folder_name)
            try:
                os.makedirs(project_subdir, exist_ok=False)
                created_paths.append(project_subdir)
                templates_subdir = os.path.join(project_subdir, 'Шаблоны')
                os.makedirs(templates_subdir, exist_ok=False)
            except PermissionError as e:
                raise GenerationError(
                    f'Permission denied creating project directory: {e}') from e
            except FileExistsError as e:
                raise GenerationError(
                    f'Project directory already exists: {project_subdir}') from e

            new_config = _build_project_config(
                template_config, row_data, primary_source_config.file)

            new_project_file = os.path.join(project_subdir, 'проект.docxforge')
            new_project = Project(version=2)
            new_project.templates[template_name] = new_config
            try:
                new_project.to_file(new_project_file)
            except Exception as e:
                raise GenerationError(
                    f'Failed to write project config: {e}') from e

            try:
                _copy_template_files(template_full, templates_subdir)
            except Exception as e:
                raise GenerationError(
                    f'Failed to copy template files: {e}') from e

            try:
                data_subdir = os.path.join(project_subdir, 'Данные')
                if src_data_dir is not None:
                    shutil.copytree(src_data_dir, data_subdir)
                else:
                    os.makedirs(data_subdir, exist_ok=True)
                os.makedirs(os.path.join(project_subdir, 'Результат'),
                            exist_ok=True)
            except PermissionError as e:
                raise GenerationError(
                    f'Permission denied copying data folder: {e}') from e
            except OSError as e:
                raise GenerationError(
                    f'Failed to copy data folder: {e}') from e

            # B1: Home snapshot + prefilled documents — only after the
            # project folder is fully assembled (template + data + config).
            try:
                save_project_snapshot_to_home(
                    folder_name, new_project, home_dir=home_dir)
            except Exception as e:
                logger.warning('Home snapshot for %r skipped: %s', folder_name, e)

            _render_prefilled_project_docs(project_subdir, template_name)

            created_count += 1
    except GenerationError:
        _rollback_created(created_paths)
        raise
    except Exception as e:
        _rollback_created(created_paths)
        raise GenerationError(f'Failed to create projects: {e}') from e

    if created_count > 0:
        # B6: creation-from-generation advances the source counter just like
        # normal generation; persist the source project.
        advance_counter_after_creation(template_config.resume, created_count)
        project.to_file(project_file)

    return projects_dir, created_count


def _resolve_folder_name_template(
    template: str,
    row_data: Dict[str, str],
    config: TemplateConfig,
) -> str:
    effective = {}

    for fn, fm in config.fields.items():
        if fm.type == FieldType.CONSTANT:
            effective[fn] = fm.value or ''

    for fn, fm in config.fields.items():
        if fm.type == FieldType.TABLE and not fm.linked_to:
            # The file only designates the source table; the value always
            # comes from the current row, so a missing file selection must
            # not block resolution when the column is present in the row.
            if fm.column and fm.column in row_data:
                effective[fn] = row_data.get(fm.column, '')

    for key, value in row_data.items():
        if key not in effective:
            effective[key] = value

    result, unresolved = substitute_placeholders(template, effective)
    if unresolved:
        logger.warning(
            'Unresolved placeholders %s in folder template %r '
            '(check field table/column mapping)', unresolved, template)

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


# ---------------------------------------------------------------------------
# B4: skip-copy flags (excluded tables are not copied into generated projects).
# New functions only — project-creation functions (B1 zone) are untouched;
# B1 wires these flags into the creation paths.
# ---------------------------------------------------------------------------

def get_skip_copy_tables(batch_sources) -> set:
    """Return file names of batch sources flagged to skip copying.

    The flag is read via ``getattr(bsc, 'skip_copy', False)`` so no schema
    change is required: once ``BatchSourceConfig`` gains a real ``skip_copy``
    field this keeps working unchanged.

    Args:
        batch_sources: Mapping of name to batch source config (any object
            with ``file`` and optional ``skip_copy`` attributes).

    Returns:
        Set of data file names (``bsc.file``) whose ``skip_copy`` is truthy.
    """
    skipped = set()
    for name, bsc in (batch_sources or {}).items():
        if getattr(bsc, 'skip_copy', False):
            skipped.add(getattr(bsc, 'file', None) or name)
    return skipped


def copy_data_tree(src_data_dir: str, dst_data_dir: str,
                   exclude_names=None) -> str:
    """Copy a data folder, skipping excluded table files.

    Every entry of ``src_data_dir`` is copied into ``dst_data_dir`` except
    files whose base name is in ``exclude_names``. Excluded tables are
    logged and left out; everything else is copied as before.

    Args:
        src_data_dir: Existing source ``Данные/`` folder.
        dst_data_dir: Destination folder (created if missing).
        exclude_names: Optional iterable of file base names to skip.

    Returns:
        Destination path.

    Raises:
        GenerationError: Source folder missing or copy failure.
    """
    if not os.path.isdir(src_data_dir):
        raise GenerationError(
            f'Data folder not found: {src_data_dir}'
        )
    excluded = set(exclude_names or ())
    try:
        os.makedirs(dst_data_dir, exist_ok=True)
        for entry in sorted(os.listdir(src_data_dir)):
            src_entry = os.path.join(src_data_dir, entry)
            if os.path.isfile(src_entry) and entry in excluded:
                logger.info('Skipped excluded table: %s', entry)
                continue
            dst_entry = os.path.join(dst_data_dir, entry)
            if os.path.isdir(src_entry):
                shutil.copytree(src_entry, dst_entry, dirs_exist_ok=True)
            else:
                shutil.copy2(src_entry, dst_entry)
    except PermissionError as e:
        raise GenerationError(
            f'Permission denied copying data folder: {e}') from e
    except OSError as e:
        raise GenerationError(
            f'Failed to copy data folder: {e}') from e
    logger.info('Copied data folder (excluded=%s): %s -> %s',
                sorted(excluded), src_data_dir, dst_data_dir)
    return dst_data_dir


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
    home_dir: Optional[str] = None,
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

    The grouping/project column names are inferred from the template
    placeholders (``{{фио_сотрудника}}/{{проект}}`` groups by the batch
    column behind the ``фио_сотрудника`` field), unless explicit
    ``employee_column`` / ``project_column`` arguments are passed.
    Placeholders name fields: a TABLE field's file/column mapping is
    resolved, so ``{{фио_клиента}}`` (Таблица "клиенты", столбец "фио")
    groups by the ``фио`` batch column.

    NOTE: ``max_projects`` is the 4th positional parameter so the composite
    routing in ``create_projects_from_template`` can pass it positionally.

    Args:
        project_path: Source project directory (with проект.docxforge).
        template_name: Template filename (relative to Шаблоны/).
        folder_name_template: Composite template, e.g. "{{employee}}/{{project_name}}".
        max_projects: Cap on the TOTAL number of projects (None or <= 0 = all).
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
    # Template placeholders name FIELDS, not batch columns: "{{фио_клиента}}"
    # may be a TABLE field reading column "фио" from "клиенты.xlsx".
    # Infer placeholder names from the template, then resolve each one to
    # the real batch column via the field mapping (TABLE file/column).
    # A placeholder with no field entry names a batch column directly.
    _parsed_columns = parse_composite_template(folder_name_template or '')
    if _parsed_columns['is_composite']:
        if employee_column == 'employee' and _parsed_columns.get('employee_column'):
            employee_column = _parsed_columns['employee_column']
        if project_column == 'project_name' and _parsed_columns.get('project_column'):
            project_column = _parsed_columns['project_column']
    _employee_field = template_config.fields.get(employee_column)
    _project_field = template_config.fields.get(project_column)
    if (_employee_field is not None and _employee_field.type == FieldType.TABLE
            and _employee_field.column):
        if _employee_field.column in available_columns or employee_column not in available_columns:
            employee_column = _employee_field.column
    if (_project_field is not None and _project_field.type == FieldType.TABLE
            and _project_field.column):
        if _project_field.column in available_columns or project_column not in available_columns:
            project_column = _project_field.column
    if employee_column not in available_columns:
        raise GenerationError(
            f'Column "{employee_column}" not found in batch source '
            f'"{primary_source_config.file}" (required for employee grouping)')
    if project_column not in available_columns:
        raise GenerationError(
            f'Column "{project_column}" not found in batch source '
            f'"{primary_source_config.file}" (required for project folders)')

    indexed_rows = list(enumerate(limit_rows(primary_rows, max_projects)))

    groups: Dict[str, list] = {}
    for row_idx, row in indexed_rows:
        key = str(row.get(employee_column, '') or '').strip()
        if not key:
            # M9: never merge unrelated rows into a shared '' group.
            key = f'unassigned_{row_idx}'
            logger.warning(
                'Empty employee value at row %d; using fallback group %r',
                row_idx, key)
        groups.setdefault(key, []).append((row_idx, row))

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
                    employee_part, items[0][1], template_config)
            else:
                resolved_employee = raw_employee
            if _GENERIC_PLACEHOLDER_RE.search(resolved_employee):
                # Never create literal "{{ ... }}" folders: fall back to the
                # grouped batch value (field mapping incomplete).
                logger.warning(
                    'Employee part %r did not resolve for row %s; '
                    'using batch value %r', employee_part,
                    items[0][0], raw_employee)
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
                    row, template_config)
                if _GENERIC_PLACEHOLDER_RE.search(resolved_project):
                    # Never create literal "{{ ... }}" folders: fall back to
                    # the batch value (field mapping incomplete).
                    fallback_project = str(row.get(project_column, '') or '').strip()
                    logger.warning(
                        'Project part %r did not resolve for row %s; '
                        'using batch value %r', project_part,
                        row_idx, fallback_project)
                    resolved_project = fallback_project
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

                try:
                    save_project_snapshot_to_home(
                        project_folder, new_project, home_dir=home_dir)
                except Exception as e:
                    logger.warning('Home snapshot for %r skipped: %s', project_folder, e)

                _render_prefilled_project_docs(project_dir, template_name)

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
    if project_count > 0:
        # B6: creation-from-generation advances the source counter just like
        # normal generation; persist the source project.
        advance_counter_after_creation(template_config.resume, project_count)
        project.to_file(project_file)
    return projects_dir, employee_counter, project_count


# ---------------------------------------------------------------------------
# B1 (002-stabilization): Home snapshots + prefilled documents.
# Each generated project additionally leaves a `<project>.docxforge` snapshot
# named after the project itself in the user's Home directory, and is born
# with its documents already rendered (TABLE fields were frozen to row
# values as CONSTANT, so a plain render resolves everything).
# ---------------------------------------------------------------------------

def get_home_dir() -> str:
    """Return the user's Home directory (B1 snapshot location)."""
    return os.path.expanduser('~')


def unique_home_project_file(
    project_name: str,
    home_dir: Optional[str] = None,
) -> str:
    """Return a non-existing ``<project_name>.docxforge`` path in Home.

    On name collision the file being created is renamed (``name (1)``,
    ``name (2)``, …) while the existing file is left untouched — the same
    rule as B5 output files, applied to Home snapshots.
    """
    base_dir = home_dir or get_home_dir()
    safe = _sanitize_folder_name(project_name) or 'project'
    candidate = os.path.join(base_dir, safe + '.docxforge')
    if not os.path.exists(candidate):
        return candidate
    root, ext = os.path.splitext(candidate)
    index = 1
    while True:
        renamed = '%s (%d)%s' % (root, index, ext)
        if not os.path.exists(renamed):
            logger.info('Home snapshot %r exists; using %r instead',
                        candidate, renamed)
            return renamed
        index += 1


def save_project_snapshot_to_home(
    project_name: str,
    project: 'Project',
    home_dir: Optional[str] = None,
) -> str:
    """Write a ``<project_name>.docxforge`` snapshot to Home. Returns path."""
    path = unique_home_project_file(project_name, home_dir)
    project.to_file(path)
    logger.info('Wrote home snapshot: %s', path)
    return path


def _render_prefilled_project_docs(
    project_dir: str,
    template_name: str,
) -> List[str]:
    """Render prefilled documents into a generated project's ``Результат/``.

    Best-effort: failures are logged with a warning and never abort project
    creation (the project folder + config already exist at this point).
    """
    try:
        renderer = Renderer(project_dir, DataReader())
        renderer.load_project()
        outputs = renderer.render(
            template_name, {},
            output_dir=os.path.join(project_dir, 'Результат'),
            max_docs=1,
        )
        renderer.save_project()
        logger.info('Prefilled %d document(s) in %s', len(outputs), project_dir)
        return outputs
    except Exception as e:
        logger.warning('Prefill render skipped for %s: %s', project_dir, e)
        return []


def generate_cli(project_path: str, template: str = None, count: int = None, out: str = None) -> List[str]:
    """CLI-friendly wrapper that prints progress."""
    print(f'Project: {project_path}')
    print(f'Template: {template or "first configured"}')
    print(f'Count: {count or "auto"}')
    print(f'Output: {out or "<project>/Результат/"}')

    outputs = generate_project(project_path, template, count, out)

    print(f'Generated: {len(outputs)} document(s)')
    for o in outputs:
        print(f'  {os.path.basename(o)}')
    return outputs
