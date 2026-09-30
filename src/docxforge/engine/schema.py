# -*- coding: utf-8 -*-
""".docxforge project file schema — defines the JSON structure and defaults."""

import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


logger = logging.getLogger(__name__)


def atomic_write_json(path: str, data: dict, backup_ext: Optional[str] = None) -> str:
    """Write JSON atomically: tmp-write + flush + fsync + os.replace.

    The payload is written to ``path + '.tmp'`` in the same directory
    (same filesystem, so ``os.replace`` is atomic), flushed and fsynced,
    then moved over ``path`` with ``os.replace``. The destination is
    never left half-written: a crash between tmp-write and replace
    leaves the old file intact. Optionally keeps a backup copy when
    ``backup_ext`` is given (e.g. ``'.bak'``).

    Returns ``path``.
    """
    tmp_file = path + '.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    if backup_ext and os.path.exists(path):
        try:
            os.replace(path, path + backup_ext)
        except Exception as e:
            logger.exception(f'Could not back up {path}: {e}')
    os.replace(tmp_file, path)
    try:
        dir_name = os.path.dirname(os.path.abspath(path)) or '.'
        fd = os.open(dir_name, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception as e:
        logger.exception(f'Could not fsync directory for {path}: {e}')
    return path


class FieldType(str, Enum):
    CONSTANT = 'constant'
    TABLE = 'table'
    COUNTER = 'counter'
    TODAY = 'today'
    IMAGE = 'image'


class AggregationFunction(str, Enum):
    SUM = 'sum'
    SUM_MULTIPLY = 'sum_multiply'
    COUNT = 'count'
    MAX = 'max'
    MIN = 'min'


class RowIterationMode(str, Enum):
    CONSTANT = 'constant'       # одна и та же строка во всех документах (lookup)
    SEQUENTIAL = 'sequential'   # по порядку, стоп при исчерпании
    CIRCULAR = 'circular'       # по кругу


# Backward compatibility alias
BatchMode = RowIterationMode


@dataclass
class FieldMapping:
    type: FieldType = FieldType.CONSTANT     # default to constant
    value: Optional[str] = None
    file: Optional[str] = None
    column: Optional[str] = None
    linked_to: Optional[str] = None
    start: int = 1
    step: int = 1
    format: str = '0001'
    multiplier: Optional[float] = None


@dataclass
class CycleMapping:
    table: str
    columns: Dict[str, str] = field(default_factory=dict)


@dataclass
class AggregationMapping:
    function: AggregationFunction
    table: str
    column: str
    multiplier: Optional[float] = None


@dataclass
class BatchSourceConfig:
    file: str = ''
    mode: RowIterationMode = RowIterationMode.CONSTANT
    # For CONSTANT mode: lookup by column value
    lookup_column: Optional[str] = None  # column to search value in
    lookup_value: Optional[str] = None   # value to find in lookup_column
    # Per-table resume: continue from last row for this specific table
    continue_from_last: bool = True
    # Per-source counter settings (for sequential and circular modes)
    counter_column: Optional[str] = None  # column to use as counter
    counter_current_row: int = 1          # current row number (1-based)
    # B4: skip copying this table's file into generated projects
    skip_copy: bool = False


@dataclass
class ResumeState:
    """Runtime state: where generation last stopped (saved in project, gitignored)."""
    last_counter_value: int = 0
    sources: Dict[str, int] = field(default_factory=dict)  # file → last_row (0-based)
    continue_from_last: bool = True  # чекбокс «Продолжить»


def advance_counter_after_creation(resume: ResumeState, created_count: int) -> int:
    """Advance the generation counter after creation-from-generation (B6).

    Mirrors normal generation math in ``render_loop.update_resume_state``
    (``last_counter_value = offset + rendered``): each created project
    counts like one generated document. Only the counter moves; per-source
    row offsets are out of scope (owned by project-creation logic).

    Args:
        resume: Source template resume state (mutated in place).
        created_count: Number of projects actually created (<= 0 = no-op).

    Returns:
        The new ``last_counter_value``.
    """
    if created_count <= 0:
        return resume.last_counter_value
    base = resume.last_counter_value if resume.continue_from_last else 0
    resume.last_counter_value = base + created_count
    return resume.last_counter_value


@dataclass
class TemplateConfig:
    fields: Dict[str, FieldMapping] = field(default_factory=dict)
    cycles: List[CycleMapping] = field(default_factory=list)
    aggregations: Dict[str, AggregationMapping] = field(default_factory=dict)
    batch_sources: Dict[str, BatchSourceConfig] = field(default_factory=dict)
    total_docs: Optional[int] = None  # None = auto (min rows of SEQUENTIAL sources)
    filename_template: Optional[str] = None  # Template for output filenames
    directory_template: Optional[str] = None  # Template for output subdirectories
    create_projects: bool = False  # Create project folders instead of documents
    folder_name_template: Optional[str] = None  # Template for project folder names
    generated_project_fields: List[str] = field(default_factory=list)  # B1: subset for the generated per-project config ([] = all)
    resume: ResumeState = field(default_factory=ResumeState)
    ui_state: Dict[str, Any] = field(default_factory=dict)  # UI-specific state


@dataclass
class Project:
    version: int = 2
    templates: Dict[str, TemplateConfig] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> 'Project':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> 'Project':
        project = cls(version=data.get('version', 2))
        for tpl_name, tpl_data in data.get('templates', {}).items():
            tc = TemplateConfig()
            for fname, fdata in tpl_data.get('fields', {}).items():
                try:
                    field_type = FieldType(fdata.get('type'))
                except ValueError as e:
                    raise ValueError(
                        f"Unknown field type {fdata.get('type')!r} for field {fname!r} "
                        f"in template {tpl_name!r}"
                    ) from e
                tc.fields[fname] = FieldMapping(
                    type=field_type,
                    value=fdata.get('value'),
                    file=fdata.get('file'),
                    column=fdata.get('column'),
                    linked_to=fdata.get('linked_to'),
                    start=fdata.get('start', 1),
                    step=fdata.get('step', 1),
                    format=fdata.get('format', '0001'),
                    multiplier=fdata.get('multiplier'),
                )
            for cd in tpl_data.get('advanced', {}).get('cycles', []):
                tc.cycles.append(CycleMapping(
                    table=cd['table'],
                    columns=cd['columns'],
                ))
            for aname, adata in tpl_data.get('advanced', {}).get('aggregations', {}).items():
                tc.aggregations[aname] = AggregationMapping(
                    function=AggregationFunction(adata['function']),
                    table=adata['table'],
                    column=adata['column'],
                    multiplier=adata.get('multiplier'),
                )
            # Batch sources
            for bname, bdata in tpl_data.get('batch', {}).get('sources', {}).items():
                # Support both old BatchMode and new RowIterationMode
                mode_str = bdata.get('mode', 'constant')
                # Legacy migration: single → constant, all_rows → sequential, n_rows → sequential
                _legacy_map = {
                    'single': 'constant',
                    'all_rows': 'sequential',
                    'n_rows': 'sequential',
                }
                mode_str = _legacy_map.get(mode_str, mode_str)
                tc.batch_sources[bname] = BatchSourceConfig(
                    file=bdata.get('file', ''),
                    mode=RowIterationMode(mode_str),
                    lookup_column=bdata.get('lookup_column'),
                    lookup_value=bdata.get('lookup_value'),
                    continue_from_last=bdata.get('continue_from_last', True),
                    counter_column=bdata.get('counter_column'),
                    counter_current_row=bdata.get('counter_current_row', 1),
                    skip_copy=bdata.get('skip_copy', False),
                )
            tc.total_docs = tpl_data.get('batch', {}).get('total_docs')
            tc.filename_template = tpl_data.get('batch', {}).get('filename_template')
            tc.directory_template = tpl_data.get('batch', {}).get('directory_template')
            # Create-projects mode (absent in older files -> defaults)
            tc.create_projects = tpl_data.get('create_projects', False)
            tc.folder_name_template = tpl_data.get('folder_name_template')
            tc.generated_project_fields = list(tpl_data.get('generated_project_fields', []) or [])
            # Resume
            resume_data = tpl_data.get('resume', {})
            tc.resume = ResumeState(
                last_counter_value=resume_data.get('last_counter_value', 0),
                sources=resume_data.get('sources', {}),
                continue_from_last=resume_data.get('continue_from_last', True),
            )
            # UI state
            tc.ui_state = tpl_data.get('ui_state', {})
            project.templates[tpl_name] = tc
        return project

    def to_file(self, path: str):
        atomic_write_json(path, self._to_dict())

    def _to_dict(self) -> dict:
        result = {'version': self.version, 'templates': {}}
        for tpl_name, tc in self.templates.items():
            td = {'fields': {}}
            for fname, fm in tc.fields.items():
                fd = {'type': fm.type.value}
                if fm.value is not None: fd['value'] = fm.value
                if fm.file is not None: fd['file'] = fm.file
                if fm.column is not None: fd['column'] = fm.column
                if fm.linked_to is not None: fd['linked_to'] = fm.linked_to
                if fm.type == FieldType.COUNTER:
                    fd['start'] = fm.start
                    fd['step'] = fm.step
                    fd['format'] = fm.format
                if fm.format and fm.type == FieldType.TODAY:
                    fd['format'] = fm.format
                if fm.multiplier is not None: fd['multiplier'] = fm.multiplier
                td['fields'][fname] = fd

            advanced = {}
            if tc.cycles:
                advanced['cycles'] = [{'table': c.table, 'columns': c.columns} for c in tc.cycles]
            if tc.aggregations:
                advanced['aggregations'] = {}
                for aname, am in tc.aggregations.items():
                    ad = {'function': am.function.value, 'table': am.table, 'column': am.column}
                    if am.multiplier is not None:
                        ad['multiplier'] = am.multiplier
                    advanced['aggregations'][aname] = ad
            if advanced:
                td['advanced'] = advanced

            # Batch config
            batch = {}
            if tc.batch_sources:
                batch['sources'] = {}
                for bname, bsc in tc.batch_sources.items():
                    bd = {'file': bsc.file, 'mode': bsc.mode.value}
                    if bsc.mode == RowIterationMode.CONSTANT:
                        if bsc.lookup_column is not None:
                            bd['lookup_column'] = bsc.lookup_column
                        if bsc.lookup_value is not None:
                            bd['lookup_value'] = bsc.lookup_value
                    # Per-table resume setting
                    bd['continue_from_last'] = bsc.continue_from_last
                    # Counter settings for sequential/circular
                    if bsc.counter_column is not None:
                        bd['counter_column'] = bsc.counter_column
                    if bsc.counter_current_row != 1:
                        bd['counter_current_row'] = bsc.counter_current_row
                    if bsc.skip_copy:
                        bd['skip_copy'] = True
                    batch['sources'][bname] = bd
            if tc.total_docs is not None:
                batch['total_docs'] = tc.total_docs
            if tc.filename_template is not None:
                batch['filename_template'] = tc.filename_template
            if tc.directory_template is not None:
                batch['directory_template'] = tc.directory_template
            if batch:
                td['batch'] = batch

            # Create-projects mode (only when used; older readers ignore it)
            if tc.create_projects:
                td['create_projects'] = True
            if tc.folder_name_template is not None:
                td['folder_name_template'] = tc.folder_name_template
            if tc.generated_project_fields:
                td['generated_project_fields'] = list(tc.generated_project_fields)

            # Resume
            td['resume'] = {
                'last_counter_value': tc.resume.last_counter_value,
                'sources': tc.resume.sources,
                'continue_from_last': tc.resume.continue_from_last,
            }

            # UI state
            if tc.ui_state:
                td['ui_state'] = tc.ui_state

            result['templates'][tpl_name] = td
        return result


# Minimal folder-name helpers copied from docxforge.generate (kept local:
# engine must not import the upper generate layer). Used by create_projects
# to resolve directory_template the same way: resolve → sanitize → unique.
_INVALID_FOLDER_CHARS = '<>:"/\\|?*'

_GENERIC_PLACEHOLDER_RE = re.compile(r'\{\{\s*([^}/]+?)\s*\}\}')


def substitute_placeholders(template: str, values: Optional[Dict[str, Any]],
                            on_missing: str = 'keep'):
    """Canonical whitespace-tolerant ``{{key}}`` substitution (M1, single core).

    All folder-name resolvers (``generate`` flat/nested, ``render_loop``,
    ``_resolve_directory_template``) build their own value dict and share
    this core, so whitespace tolerance and missing-key behaviour are uniform.

    Args:
        template: string with ``{{ name }}`` placeholders (any whitespace).
        values: mapping of placeholder name to replacement value.
        on_missing: ``'keep'`` leaves unresolved ``{{name}}`` intact (callers
            fall back to numbered names); ``'empty'`` replaces them with ``''``.

    Returns:
        Tuple ``(result, unresolved)`` where ``unresolved`` is the list of
        placeholder names left unsubstituted.
    """
    result = str(template)
    for key, value in (values or {}).items():
        result = re.sub(
            r'\{\{\s*' + re.escape(str(key)) + r'\s*\}\}',
            str(value), result)
    unresolved = _GENERIC_PLACEHOLDER_RE.findall(result)
    if unresolved:
        logger.warning(
            'Unresolved placeholders %s in template %r',
            unresolved, template)
        if on_missing == 'empty':
            result = _GENERIC_PLACEHOLDER_RE.sub('', result)
    return result, unresolved


def limit_rows(rows, max_projects: Optional[int]):
    """Unified row-cap semantics (M8): ``None`` or ``<= 0`` means all rows.

    Previously ``generate`` treated ``<= 0`` as "no cap" while
    ``schema.create_projects`` returned ``[]``; every entry point now shares
    this helper. Returns a list.
    """
    items = list(rows)
    if max_projects is None:
        return items
    try:
        cap = int(max_projects)
    except (TypeError, ValueError):
        logger.warning(
            'Invalid max_projects=%r; using all %d rows',
            max_projects, len(items))
        return items
    if cap <= 0:
        return items
    return items[:cap]


def _resolve_directory_template(template: str, row_data: Dict[str, Any]) -> str:
    """Resolve {{placeholders}} (any whitespace) from row values."""
    result, _unresolved = substitute_placeholders(template, row_data or {})
    return result.strip()


def _sanitize_folder_name(name: Optional[str]) -> str:
    """Make a filesystem-safe folder name (single path segment)."""
    if name is None:
        return ''
    text = ''.join('_' if (ch in _INVALID_FOLDER_CHARS or ord(ch) < 32) else ch
                   for ch in str(name).strip())
    text = text.strip().rstrip('.')
    if len(text) > 100:
        text = text[:100].rstrip('.').strip()
    return text


def _sanitize_relpath(relpath: str) -> str:
    """Sanitize each '/'-separated segment, preserving nesting."""
    parts = []
    for part in str(relpath).replace('\\', '/').split('/'):
        safe = _sanitize_folder_name(part)
        if safe:
            parts.append(safe)
    return '/'.join(parts)


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


def create_project(project_dir: str) -> str:
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Результат'), exist_ok=True)
    project_file = default_project_file(project_dir)
    Project().to_file(project_file)
    return project_file


def create_projects(
    source_project_dir: str,
    output_base_dir: str,
    template_name: str,
    batch_source_name: str,
    max_projects: Optional[int] = None,
) -> List[str]:
    """
    Create multiple projects from a template project and batch source.

    Each row in the batch source (sequential mode) becomes a separate project
    with constant fields populated from that row's data.

    Args:
        source_project_dir: Path to source project with configured template
        output_base_dir: Base directory where new projects will be created
        template_name: Name of template in source project to use
        batch_source_name: Name of batch source in template config to iterate
        max_projects: Cap on created projects (None or <= 0 = all rows)

    Returns:
        List of created project directory paths.

    See also (M2): ``generate.create_projects_from_template`` — the full
    pipeline entry point (freezes TABLE→CONSTANT, routes composite
    templates to nested generation). Both share the folder-name contract
    (resolve→sanitize→unique); see ``tests/test_m2_contract.py``.
    """
    from docxforge.engine.data_reader import DataReader

    source_file = resolve_project_file(source_project_dir)
    if source_file is None:
        raise ValueError(
            f'Project config not found in: {source_project_dir}')
    source_project = Project.from_file(source_file)

    if template_name not in source_project.templates:
        raise ValueError(f'Template not found: {template_name}')

    template_config = source_project.templates[template_name]

    if batch_source_name not in template_config.batch_sources:
        raise ValueError(f'Batch source not found: {batch_source_name}')

    batch_config = template_config.batch_sources[batch_source_name]

    if batch_config.mode != RowIterationMode.SEQUENTIAL:
        raise ValueError('create_projects only supports SEQUENTIAL mode batch sources')

    data_reader = DataReader()
    batch_file = batch_config.file
    all_rows = data_reader.read_excel(os.path.join(source_project_dir, 'Данные', batch_file))

    if not all_rows:
        return []

    all_rows = limit_rows(all_rows, max_projects)

    created_projects = []
    used_folder_names = set()
    os.makedirs(output_base_dir, exist_ok=True)

    for row_idx, row_data in enumerate(all_rows):
        # Resolve folder name from directory_template (resolve→sanitize→unique)
        fallback = f'project_{row_idx + 1}'
        folder_name = fallback
        if template_config.directory_template:
            resolved = _resolve_directory_template(
                template_config.directory_template, row_data)
            if _GENERIC_PLACEHOLDER_RE.search(resolved):
                logger.warning(
                    'directory_template %r did not fully resolve for row %d; '
                    'using fallback %r',
                    template_config.directory_template, row_idx, fallback)
            else:
                sanitized = _sanitize_relpath(resolved)
                if sanitized:
                    folder_name = sanitized
                else:
                    logger.warning(
                        'directory_template %r resolved to an unusable name '
                        'for row %d; using fallback %r',
                        template_config.directory_template, row_idx, fallback)
        else:
            folder_name = _sanitize_relpath(folder_name) or fallback
        folder_name = _unique_folder_name(
            folder_name, used_folder_names, output_base_dir)

        project_dir = os.path.join(output_base_dir, folder_name)
        os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)
        os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
        os.makedirs(os.path.join(project_dir, 'Результат'), exist_ok=True)

        # Copy template file
        src_template = os.path.join(source_project_dir, 'Шаблоны', template_name)
        dst_template = os.path.join(project_dir, 'Шаблоны', template_name)
        if os.path.exists(src_template):
            shutil.copy2(src_template, dst_template)

        # Copy data file
        src_data = os.path.join(source_project_dir, 'Данные', batch_file)
        dst_data = os.path.join(project_dir, 'Данные', batch_file)
        if os.path.exists(src_data):
            shutil.copy2(src_data, dst_data)

        # Create new project config with row data as constants
        new_project = Project()
        new_template = TemplateConfig()

        # Copy fields, converting table fields to constants with row values
        for fname, fm in template_config.fields.items():
            new_fm = FieldMapping()
            if fm.type == FieldType.CONSTANT:
                new_fm.type = FieldType.CONSTANT
                new_fm.value = fm.value
            elif fm.type == FieldType.TABLE and fm.file == batch_file and fm.column in row_data:
                # Convert table field to constant with row value
                new_fm.type = FieldType.CONSTANT
                new_fm.value = str(row_data[fm.column])
            elif fm.type == FieldType.COUNTER:
                # Reset counter to start value
                new_fm.type = FieldType.COUNTER
                new_fm.start = fm.start
                new_fm.step = fm.step
                new_fm.format = fm.format
            elif fm.type == FieldType.TODAY:
                new_fm.type = FieldType.TODAY
                new_fm.format = fm.format
            elif fm.type == FieldType.IMAGE:
                new_fm.type = FieldType.IMAGE
                new_fm.value = fm.value
            else:
                # Keep other table fields as-is (they'll need their data files copied)
                new_fm.type = fm.type
                new_fm.value = fm.value
                new_fm.file = fm.file
                new_fm.column = fm.column
                new_fm.linked_to = fm.linked_to
                new_fm.start = fm.start
                new_fm.step = fm.step
                new_fm.format = fm.format
                new_fm.multiplier = fm.multiplier
            new_template.fields[fname] = new_fm

        # Copy cycles
        new_template.cycles = template_config.cycles.copy()

        # Copy aggregations
        new_template.aggregations = template_config.aggregations.copy()

        # Copy batch config - convert all sources to CONSTANT mode
        new_batch_sources = {}
        for bname, bsc in template_config.batch_sources.items():
            new_bsc = BatchSourceConfig(
                file=bsc.file,
                mode=RowIterationMode.CONSTANT,
                lookup_column=None,
                lookup_value=None,
                continue_from_last=False,
            )
            new_batch_sources[bname] = new_bsc
        new_template.batch_sources = new_batch_sources

        new_template.total_docs = 1  # Each project generates 1 document
        new_template.filename_template = template_config.filename_template
        new_template.directory_template = template_config.directory_template

        new_project.templates[template_name] = new_template

        project_file = default_project_file(project_dir)
        new_project.to_file(project_file)

        created_projects.append(project_dir)

    if created_projects:
        # B6: creation-from-generation advances the source counter just like
        # normal generation; persist the source project to its own file.
        advance_counter_after_creation(template_config.resume, len(created_projects))
        source_project.to_file(source_file)

    return created_projects


# ---------------------------------------------------------------------------
# Project config files: every project owns `<name>.docxforge` named after
# itself (no fixed file name). Generated folders carry it next to Данные/;
# on open it migrates to `~/.docxforge` and opening resolves folder-first,
# Home-second.
# ---------------------------------------------------------------------------

INVALID_FOLDER_CHARS = '<>:"/\\|?*'


def sanitize_folder_name(name) -> str:
    """Filesystem-safe stem: replaces Windows-unsafe/control chars."""
    if name is None:
        return ''
    text = ''.join('_' if (ch in INVALID_FOLDER_CHARS or ord(ch) < 32)
                   else ch for ch in str(name).strip())
    text = text.strip().rstrip('.')
    if len(text) > 100:
        text = text[:100].rstrip('.').strip()
    return text


def get_home_dir() -> str:
    """Return the user's Home directory."""
    return os.path.expanduser('~')


def get_docxforge_home() -> str:
    """Return ``~/.docxforge`` (configs, logs, settings), creating it."""
    path = os.path.join(get_home_dir(), '.docxforge')
    os.makedirs(path, exist_ok=True)
    return path


def unique_home_project_file(project_name: str, home_dir: str = None) -> str:
    """Non-existing ``<name>.docxforge`` path in ``~/.docxforge``.

    Collision renames the new file (``name (1)``, ``name (2)``, …),
    the existing file is never touched.
    """
    base_dir = home_dir or get_docxforge_home()
    safe = sanitize_folder_name(project_name) or 'project'
    candidate = os.path.join(base_dir, safe + '.docxforge')
    if not os.path.exists(candidate):
        return candidate
    root, ext = os.path.splitext(candidate)
    index = 1
    while True:
        renamed = '%s (%d)%s' % (root, index, ext)
        if not os.path.exists(renamed):
            logger.info('Home config %r exists; using %r instead',
                        candidate, renamed)
            return renamed
        index += 1


def unique_project_file_in_folder(project_dir: str, stem: str) -> str:
    """Non-existing ``<stem>.docxforge`` path inside a project folder."""
    safe = sanitize_folder_name(stem) or 'project'
    candidate = os.path.join(project_dir, safe + '.docxforge')
    if not os.path.exists(candidate):
        return candidate
    root, ext = os.path.splitext(candidate)
    index = 1
    while True:
        renamed = '%s (%d)%s' % (root, index, ext)
        if not os.path.exists(renamed):
            return renamed
        index += 1


def default_project_file(project_dir: str) -> str:
    """Default config path for a folder: ``<folder-basename>.docxforge``."""
    base = sanitize_folder_name(
        os.path.basename(os.path.normpath(project_dir))) or 'project'
    return os.path.join(project_dir, base + '.docxforge')


def resolve_project_file(project_dir: str, home_dir: str = None):
    """Locate the config for a project folder.

    1. ``<folder>/<folder-basename>.docxforge`` (named config).
    2. ``<folder>/проект.docxforge`` (legacy, migrates on open).
    3. The single ``<folder>/*.docxforge`` (unmigrated generated folder).
    4. ``~/.docxforge/<folder>.docxforge`` — migrated copy (exact stem,
       then ``<stem> (n)`` variants, newest wins).
    Returns path or None.
    """
    base = sanitize_folder_name(
        os.path.basename(os.path.normpath(project_dir))) or 'project'
    named = os.path.join(project_dir, base + '.docxforge')
    if os.path.isfile(named):
        return named
    legacy = os.path.join(project_dir, 'проект.docxforge')
    if os.path.isfile(legacy):
        return legacy
    try:
        names = sorted(os.listdir(project_dir))
    except OSError:
        names = []
    singles = [n for n in names
               if n.endswith('.docxforge') and not n.endswith(('.bak', '.tmp'))]
    if len(singles) == 1:
        return os.path.join(project_dir, singles[0])
    home = home_dir or get_docxforge_home()
    try:
        hnames = os.listdir(home)
    except OSError:
        return None
    exact = base + '.docxforge'
    if exact in hnames:
        return os.path.join(home, exact)
    variants = [os.path.join(home, n) for n in hnames
                if n.startswith(base + ' (') and n.endswith(').docxforge')]
    if not variants:
        return None
    variants.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return variants[0]


def is_project_folder(path: str, home_dir: str = None) -> bool:
    """True if a folder looks like an openable project."""
    try:
        names = os.listdir(path)
    except OSError:
        return False
    for name in names:
        if name.endswith('.docxforge') and not name.endswith(('.bak', '.tmp')):
            return True
    if 'Данные' in names or 'Шаблоны' in names:
        return resolve_project_file(path, home_dir) is not None
    return False


# ---------------------------------------------------------------------------
# 003-json Phase 3: Project JSON validation / normalization.
#
# Normative example: specs/003-json/project_generation.json
# (dict-shaped `templates`, relative paths, field types
# constant/table/counter/today/image, dict-shaped batch sources, `resume`).
# Messages are English technical strings (no hardcoded Russian strings).
# ---------------------------------------------------------------------------

#: Field types accepted by Project JSON (legacy `number` migrates to `counter`).
PROJECT_FIELD_TYPES = frozenset(
    ft.value for ft in FieldType)  # constant/table/counter/today/image

#: Batch/row-iteration modes accepted by Project JSON.
PROJECT_BATCH_MODES = frozenset(
    m.value for m in RowIterationMode)  # constant/sequential/circular

#: Legacy batch modes migrated by normalize_project_json().
_LEGACY_BATCH_MODES = {
    'single': RowIterationMode.CONSTANT.value,
    'all_rows': RowIterationMode.SEQUENTIAL.value,
    'n_rows': RowIterationMode.SEQUENTIAL.value,
}

_ABSOLUTE_PATH_RE = re.compile(r'^[a-zA-Z]:[\\/]')


def _is_absolute_path(value: Any) -> bool:
    """Cross-platform absolute-path check (str only; non-str is False)."""
    if not isinstance(value, str) or not value:
        return False
    text = value.replace('\\', '/')
    if text.startswith('/') or _ABSOLUTE_PATH_RE.match(value):
        return True
    try:
        if os.path.isabs(value):
            return True
    except Exception as e:
        logger.exception(f'Absolute-path check failed for {value!r}: {e}')
    return False


def validate_project_json(data: dict) -> List[str]:
    """Validate a Project JSON dict, returning a list of error strings.

    Checks: required `templates` dict (non-empty) and per-template `fields`
    dict (non-empty); known field types; required `file`+`column` on `table`
    fields; batch `mode` in constant/sequential/circular; relative paths
    only (absolute paths are errors — template names, field/batch `file`
    values, `filename_template`, `directory_template`, `folder_name_template`).

    An empty list means the document is valid.
    """
    errors: List[str] = []
    if not isinstance(data, dict):
        return ['project: must be an object']
    templates = data.get('templates')
    if not isinstance(templates, dict) or not templates:
        errors.append('templates: must be a non-empty object')
        return errors
    for tpl_name, tpl in templates.items():
        loc = 'templates[%r]' % (tpl_name,)
        if _is_absolute_path(tpl_name):
            errors.append('%s: template name must be a relative path' % loc)
        if not isinstance(tpl, dict):
            errors.append('%s: must be an object' % loc)
            continue
        fields = tpl.get('fields')
        if not isinstance(fields, dict) or not fields:
            errors.append('%s.fields: must be a non-empty object' % loc)
        else:
            for fname, fdata in fields.items():
                floc = '%s.fields[%r]' % (loc, fname)
                if not isinstance(fdata, dict):
                    errors.append('%s: must be an object' % floc)
                    continue
                ftype = fdata.get('type')
                if ftype not in PROJECT_FIELD_TYPES:
                    errors.append(
                        '%s.type: unknown field type %r '
                        '(expected one of constant/table/counter/today/image)'
                        % (floc, ftype))
                    continue
                if ftype == FieldType.TABLE.value:
                    if not fdata.get('file'):
                        errors.append(
                            '%s: table field requires "file"' % floc)
                    elif _is_absolute_path(fdata.get('file')):
                        errors.append(
                            '%s.file: must be a relative path' % floc)
                    if not fdata.get('column'):
                        errors.append(
                            '%s: table field requires "column"' % floc)
                else:
                    for key in ('file', 'path'):
                        if key in fdata and fdata[key] is not None \
                                and _is_absolute_path(fdata[key]):
                            errors.append(
                                '%s.%s: must be a relative path'
                                % (floc, key))
        batch = tpl.get('batch', {})
        if not isinstance(batch, dict):
            errors.append('%s.batch: must be an object' % loc)
        else:
            sources = batch.get('sources', {})
            if sources is not None and not isinstance(sources, dict):
                errors.append('%s.batch.sources: must be an object' % loc)
            elif isinstance(sources, dict):
                for sname, sdata in sources.items():
                    sloc = '%s.batch.sources[%r]' % (loc, sname)
                    if not isinstance(sdata, dict):
                        errors.append('%s: must be an object' % sloc)
                        continue
                    mode = sdata.get('mode', RowIterationMode.CONSTANT.value)
                    if mode not in PROJECT_BATCH_MODES:
                        errors.append(
                            '%s.mode: unknown batch mode %r '
                            '(expected one of constant/sequential/circular)'
                            % (sloc, mode))
                    for key in ('file', 'path'):
                        if key in sdata and sdata[key] is not None \
                                and _is_absolute_path(sdata[key]):
                            errors.append(
                                '%s.%s: must be a relative path'
                                % (sloc, key))
            for key in ('filename_template', 'directory_template',
                        'folder_name_template'):
                val = batch.get(key, tpl.get(key))
                if val is not None and _is_absolute_path(val):
                    errors.append(
                        '%s.%s: must be a relative path' % (loc, key))
    return errors


def _basename_of(path_value: Any) -> Any:
    """Return the final segment of a path-like string (forward-slash aware)."""
    if not isinstance(path_value, str):
        return path_value
    return path_value.replace('\\', '/').rstrip('/').split('/')[-1]


def _normalize_fields(raw: Any) -> Dict[str, dict]:
    """Normalize a fields mapping: legacy list-of-{name,...} → dict."""
    if isinstance(raw, list):
        out: Dict[str, dict] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            if not name:
                logger.warning('Skipping legacy field without name: %r', item)
                continue
            rest = {k: v for k, v in item.items() if k != 'name'}
            out[str(name)] = rest
        return out
    if isinstance(raw, dict):
        return {str(k): (dict(v) if isinstance(v, dict) else v)
                for k, v in raw.items()}
    return {}


def _normalize_batch_sources(raw: Any) -> Dict[str, dict]:
    """Normalize batch sources: legacy list-of-{name,...} → dict."""
    if isinstance(raw, list):
        out: Dict[str, dict] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get('name') or item.get('file')
            if not name:
                logger.warning(
                    'Skipping legacy batch source without name: %r', item)
                continue
            rest = {k: v for k, v in item.items() if k != 'name'}
            out[str(name)] = rest
        return out
    if isinstance(raw, dict):
        return {str(k): (dict(v) if isinstance(v, dict) else v)
                for k, v in raw.items()}
    return {}


def _normalize_field_entry(fdata: Any) -> dict:
    """Migrate one field entry: `number` → `counter`, absolute file → basename."""
    if not isinstance(fdata, dict):
        return fdata
    fd = dict(fdata)
    if fd.get('type') == 'number':
        logger.info('Migrating legacy field type number -> counter')
        fd['type'] = FieldType.COUNTER.value
        fd.setdefault('start', 1)
    for key in ('file', 'path'):
        if key in fd and _is_absolute_path(fd[key]):
            logger.info('Relativizing absolute %s %r -> basename', key, fd[key])
            if key == 'path' and not _is_absolute_path(fd.get('file', '')):
                fd.pop(key, None)
                continue
            fd[key] = _basename_of(fd[key])
    # Legacy 'path' alongside a relative 'file' carries no extra meaning.
    if 'path' in fd and 'file' in fd \
            and not _is_absolute_path(fd.get('file', '')):
        fd.pop('path', None)
    return fd


def _normalize_source_entry(sdata: Any) -> dict:
    """Migrate one batch source: legacy mode, absolute file → basename."""
    if not isinstance(sdata, dict):
        return sdata
    sd = dict(sdata)
    mode = sd.get('mode')
    if mode in _LEGACY_BATCH_MODES:
        logger.info('Migrating legacy batch mode %r -> %r',
                    mode, _LEGACY_BATCH_MODES[mode])
        sd['mode'] = _LEGACY_BATCH_MODES[mode]
    for key in ('file', 'path'):
        if key in sd and _is_absolute_path(sd[key]):
            logger.info('Relativizing absolute %s %r -> basename', key, sd[key])
            if key == 'path' and not _is_absolute_path(sd.get('file', '')):
                sd.pop(key, None)
                continue
            sd[key] = _basename_of(sd[key])
    if 'path' in sd and 'file' in sd \
            and not _is_absolute_path(sd.get('file', '')):
        sd.pop('path', None)
    sd.setdefault('continue_from_last', True)
    return sd


def _normalize_resume(raw: Any) -> dict:
    """Fill resume defaults (mirrors _from_dict): last 0, sources {}, resume on."""
    resume = dict(raw) if isinstance(raw, dict) else {}
    resume.setdefault('last_counter_value', 0)
    if not isinstance(resume.get('sources'), dict):
        resume['sources'] = {}
    resume.setdefault('continue_from_last', True)
    return resume


def normalize_project_json(data: dict) -> dict:
    """Migrate a Project JSON dict to the normalized schema (deep copy out).

    Legacy migrations: `type: number` → `counter`; `templates_new` array →
    `templates` dict (when present); list-shaped `fields`/`batch.sources` →
    dicts; legacy batch modes (`single`/`all_rows`/`n_rows`); absolute paths →
    basenames (or dropped `path` duplicates); missing `resume` and per-source
    `continue_from_last` defaults filled in. Normalized output validates
    cleanly via :func:`validate_project_json`.
    """
    import copy
    if not isinstance(data, dict):
        logger.warning('normalize_project_json: expected dict, got %r',
                       type(data))
        return {}
    norm = copy.deepcopy(data)
    templates = norm.get('templates')
    if not isinstance(templates, dict):
        templates = {}
    # Legacy: templates_new array → dict (existing `templates` wins on clash).
    legacy = norm.pop('templates_new', None)
    if isinstance(legacy, list):
        for item in legacy:
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            if not name:
                logger.warning(
                    'Skipping legacy templates_new entry without name: %r',
                    item)
                continue
            name = _basename_of(name) if _is_absolute_path(name) else str(name)
            entry: dict = {}
            entry['fields'] = {
                fname: _normalize_field_entry(fdata)
                for fname, fdata in _normalize_fields(
                    item.get('fields', {})).items()
            }
            batch = item.get('batch', {}) if isinstance(
                item.get('batch', {}), dict) else {}
            sources = {
                sname: _normalize_source_entry(sdata)
                for sname, sdata in _normalize_batch_sources(
                    batch.get('sources', {})).items()
            }
            new_batch = {k: v for k, v in batch.items() if k != 'sources'}
            if _is_absolute_path(new_batch.get('filename_template', '')):
                new_batch['filename_template'] = _basename_of(
                    new_batch['filename_template'])
            new_batch['sources'] = sources
            entry['batch'] = new_batch
            resume = item.get('resume')
            entry['resume'] = _normalize_resume(resume)
            if name in templates:
                logger.warning(
                    'templates_new entry %r clashes with templates; '
                    'keeping templates version', name)
            else:
                templates[name] = entry
    # Normalize every template in place.
    for tpl_name, tpl in list(templates.items()):
        if not isinstance(tpl, dict):
            continue
        tpl['fields'] = {
            fname: _normalize_field_entry(fdata)
            for fname, fdata in _normalize_fields(
                tpl.get('fields', {})).items()
        }
        batch = tpl.get('batch', {})
        if not isinstance(batch, dict):
            batch = {}
        sources = {
            sname: _normalize_source_entry(sdata)
            for sname, sdata in _normalize_batch_sources(
                batch.get('sources', {})).items()
        }
        new_batch = {k: v for k, v in batch.items() if k != 'sources'}
        for key in ('filename_template', 'directory_template',
                    'folder_name_template'):
            if _is_absolute_path(new_batch.get(key, '')):
                logger.info('Relativizing absolute %s -> basename', key)
                new_batch[key] = _basename_of(new_batch[key])
        new_batch['sources'] = sources
        tpl['batch'] = new_batch
        tpl['resume'] = _normalize_resume(tpl.get('resume'))
    norm['templates'] = templates
    return norm


def migrate_project_configs_to_home(project_dir: str,
                                    home_dir: str = None) -> list:
    """Move a project folder's configs to ``~/.docxforge``.

    For every ``*.docxforge`` next to ``Данные/``/``Шаблоны/`` (except
    ``*.bak``/``*.tmp``): copy bytes to ``~/.docxforge/<folder-basename>``
    (collision → ``(1)``, ``(2)``…) and delete the source. Best-effort —
    never raises. Returns the created Home paths.
    """
    migrated = []
    try:
        names = os.listdir(project_dir)
    except OSError as e:
        logger.debug('Migration scan failed for %r: %s', project_dir, e)
        return migrated
    if 'Данные' not in names and 'Шаблоны' not in names:
        return migrated
    base = sanitize_folder_name(
        os.path.basename(os.path.normpath(project_dir))) or 'project'
    for name in sorted(names):
        if not name.endswith('.docxforge'):
            continue
        if name.endswith(('.bak', '.tmp')):
            continue
        src = os.path.join(project_dir, name)
        if not os.path.isfile(src):
            continue
        try:
            with open(src, 'rb') as f:
                payload = f.read()
            dst = unique_home_project_file(base, home_dir)
            with open(dst, 'wb') as f:
                f.write(payload)
            os.remove(src)
            logger.info('Migrated project config: %s -> %s', src, dst)
            migrated.append(dst)
        except OSError as e:
            logger.warning('Config migration skipped for %r: %s', src, e)
    return migrated
