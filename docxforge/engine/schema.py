# -*- coding: utf-8 -*-
""".docxforge project file schema — defines the JSON structure and defaults."""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum


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


@dataclass
class ResumeState:
    """Runtime state: where generation last stopped (saved in project, gitignored)."""
    last_counter_value: int = 0
    sources: Dict[str, int] = field(default_factory=dict)  # file → last_row (0-based)
    continue_from_last: bool = True  # чекбокс «Продолжить»


@dataclass
class TemplateConfig:
    fields: Dict[str, FieldMapping] = field(default_factory=dict)
    cycles: List[CycleMapping] = field(default_factory=list)
    aggregations: Dict[str, AggregationMapping] = field(default_factory=dict)
    batch_sources: Dict[str, BatchSourceConfig] = field(default_factory=dict)
    total_docs: Optional[int] = None  # None = auto (min rows of SEQUENTIAL sources)
    filename_template: Optional[str] = None  # Template for output filenames
    directory_template: Optional[str] = None  # Template for output subdirectories
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
                tc.fields[fname] = FieldMapping(
                    type=FieldType(fdata['type']),
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
                )
            tc.total_docs = tpl_data.get('batch', {}).get('total_docs')
            tc.filename_template = tpl_data.get('batch', {}).get('filename_template')
            tc.directory_template = tpl_data.get('batch', {}).get('directory_template')
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
        data = self._to_dict()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
                    batch['sources'][bname] = bd
            if tc.total_docs is not None:
                batch['total_docs'] = tc.total_docs
            if tc.filename_template is not None:
                batch['filename_template'] = tc.filename_template
            if tc.directory_template is not None:
                batch['directory_template'] = tc.directory_template
            if batch:
                td['batch'] = batch

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


def create_project(project_dir: str) -> str:
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Результат'), exist_ok=True)
    project_file = os.path.join(project_dir, 'проект.docxforge')
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
        max_projects: Maximum number of projects to create (None = all rows)

    Returns:
        List of created project directory paths.
    """
    from docxforge.engine.data_reader import DataReader

    source_project = Project.from_file(
        os.path.join(source_project_dir, 'проект.docxforge')
    )

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

    if max_projects is not None:
        if max_projects <= 0:
            return []
        all_rows = all_rows[:max_projects]

    created_projects = []

    for row_idx, row_data in enumerate(all_rows):
        # Resolve folder name from directory_template
        folder_name = f'project_{row_idx + 1}'
        if template_config.directory_template:
            dir_template = template_config.directory_template
            for key, value in row_data.items():
                placeholder = f'{{{{ {key} }}}}'
                dir_template = dir_template.replace(placeholder, str(value))
                placeholder2 = f'{{{{{key}}}}}'
                dir_template = dir_template.replace(placeholder2, str(value))
            folder_name = dir_template.strip()

        project_dir = os.path.join(output_base_dir, folder_name)
        os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)
        os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
        os.makedirs(os.path.join(project_dir, 'Результат'), exist_ok=True)

        # Copy template file
        import shutil
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

        project_file = os.path.join(project_dir, 'проект.docxforge')
        new_project.to_file(project_file)

        created_projects.append(project_dir)

    return created_projects
