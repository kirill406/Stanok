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


@dataclass
class FieldMapping:
    type: FieldType
    value: Optional[str] = None         # constant value
    file: Optional[str] = None          # Excel filename for table
    column: Optional[str] = None        # column name in Excel
    linked_to: Optional[str] = None     # field name this is linked to
    start: int = 1                      # counter start
    step: int = 1                       # counter step
    format: str = '0001'               # counter or date format
    multiplier: Optional[float] = None  # for sum_multiply


@dataclass
class CycleMapping:
    table: str                          # Excel filename
    columns: Dict[str, str]             # field_name -> column_name


@dataclass
class AggregationMapping:
    function: AggregationFunction
    table: str
    column: str
    multiplier: Optional[float] = None


@dataclass
class TemplateConfig:
    fields: Dict[str, FieldMapping] = field(default_factory=dict)
    cycles: List[CycleMapping] = field(default_factory=list)
    aggregations: Dict[str, AggregationMapping] = field(default_factory=dict)


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

            result['templates'][tpl_name] = td
        return result


def create_project(project_dir: str) -> str:
    """Create a new project directory with required structure.
    Returns path to .docxforge file."""
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    project_file = os.path.join(project_dir, 'проект.docxforge')
    Project().to_file(project_file)
    return project_file
