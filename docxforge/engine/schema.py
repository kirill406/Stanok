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
    project_file = os.path.join(project_dir, 'проект.docxforge')
    Project().to_file(project_file)
    return project_file
