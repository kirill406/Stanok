# -*- coding: utf-8 -*-
""".docxforge project file schema — defines the JSON structure and defaults."""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
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


class BatchMode(str, Enum):
    SINGLE = 'single'           # константная строка (один документ)
    ALL_ROWS = 'all_rows'       # итерироваться по строкам до конца
    N_ROWS = 'n_rows'           # итерироваться до заданного числа
    CIRCULAR = 'circular'       # итерироваться по кругу


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
    mode: BatchMode = BatchMode.SINGLE
    n_rows: int = 1  # used when mode == N_ROWS or CIRCULAR
    # For SINGLE mode: how to pick the row
    row_index: int = 0  # explicit row number (0-based), -1 means use lookup
    lookup_column: Optional[str] = None  # column to search value in
    lookup_value: Optional[str] = None   # value to find in lookup_column


@dataclass
class TemplateConfig:
    fields: Dict[str, FieldMapping] = field(default_factory=dict)
    cycles: List[CycleMapping] = field(default_factory=list)
    aggregations: Dict[str, AggregationMapping] = field(default_factory=dict)
    batch_sources: Dict[str, BatchSourceConfig] = field(default_factory=dict)
    max_docs: Optional[int] = None  # limit total number of documents


@dataclass
class Project:
    version: int = 1
    templates: Dict[str, TemplateConfig] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> 'Project':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> 'Project':
        project = cls(version=data.get('version', 1))
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
                tc.batch_sources[bname] = BatchSourceConfig(
                    file=bdata.get('file', ''),
                    mode=BatchMode(bdata.get('mode', 'single')),
                    n_rows=bdata.get('n_rows', 1),
                    row_index=bdata.get('row_index', 0),
                    lookup_column=bdata.get('lookup_column'),
                    lookup_value=bdata.get('lookup_value'),
                )
            tc.max_docs = tpl_data.get('batch', {}).get('max_docs')
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
                    if bsc.mode == BatchMode.N_ROWS or bsc.mode == BatchMode.CIRCULAR:
                        bd['n_rows'] = bsc.n_rows
                    if bsc.mode == BatchMode.SINGLE:
                        bd['row_index'] = bsc.row_index
                        if bsc.lookup_column is not None:
                            bd['lookup_column'] = bsc.lookup_column
                        if bsc.lookup_value is not None:
                            bd['lookup_value'] = bsc.lookup_value
                    batch['sources'][bname] = bd
            if tc.max_docs is not None:
                batch['max_docs'] = tc.max_docs
            if batch:
                td['batch'] = batch

            result['templates'][tpl_name] = td
        return result


def create_project(project_dir: str) -> str:
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    project_file = os.path.join(project_dir, 'проект.docxforge')
    Project().to_file(project_file)
    return project_file
