# -*- coding: utf-8 -*-
"""Core rendering engine: project I/O, row resolution, and render orchestration."""

import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from .schema import (
    Project, TemplateConfig, FieldMapping, CycleMapping,
    AggregationMapping, FieldType, AggregationFunction,
    BatchSourceConfig, RowIterationMode, ResumeState,
)
from .data_reader import DataReader
from .render_loop import (
    scan_raw_placeholders, resolve_field_values, process_xml,
    write_output_doc, update_resume_state,
)


class Renderer:
    def __init__(self, project_dir: str, data_reader: DataReader):
        self.project_dir = project_dir
        self.data_reader = data_reader
        self.project: Optional[Project] = None
        self._template_path_cache = {}

    def load_project(self):
        from docxforge.generate import resolve_project_file
        project_file = resolve_project_file(self.project_dir)
        if project_file is None:
            project_file = os.path.join(self.project_dir, 'проект.docxforge')
        self.project_file = project_file
        self.project = Project.from_file(project_file) if os.path.exists(project_file) else Project()

    def save_project(self):
        self._atomic_write_project()

    def _atomic_write_project(self):
        """Atomically write project file via the shared schema helper."""
        from .schema import atomic_write_json
        project_file = getattr(self, 'project_file',
                               os.path.join(self.project_dir, 'проект.docxforge'))
        data = self.project._to_dict()
        atomic_write_json(project_file, data, backup_ext='.bak')

    def get_template_path(self, template_name: str) -> str:
        # M17: cache the directory walk (per Renderer instance, so tests
        # with fresh instances never see stale entries).
        cached = self._template_path_cache.get(template_name)
        if cached is not None:
            return cached
        base = os.path.join(self.project_dir, 'Шаблоны')
        direct = os.path.join(base, template_name)
        if os.path.exists(direct):
            self._template_path_cache[template_name] = direct
            return direct
        for root, dirs, files in os.walk(base):
            if os.path.basename(template_name) in files:
                found = os.path.join(root, os.path.basename(template_name))
                self._template_path_cache[template_name] = found
                return found
        self._template_path_cache[template_name] = direct
        return direct

    def _read_table_data(self, table_file: str) -> List[Dict[str, str]]:
        path = os.path.join(self.project_dir, 'Данные', table_file)
        if os.path.exists(path):
            return self.data_reader.read_excel(path)
        return []

    def _resolve_constant_row(self, table_file: str,
                               batch_configs: Optional[Dict[str, BatchSourceConfig]] = None,
                               all_rows: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, str]]:
        """Resolve the row for a CONSTANT-mode source (lookup by column value)."""
        if not batch_configs:
            return None
        bsc = batch_configs.get(table_file)
        if not bsc or bsc.mode != RowIterationMode.CONSTANT:
            return None
        if all_rows is None:
            all_rows = self._read_table_data(table_file)
        if not all_rows:
            return None
        if bsc.lookup_column and bsc.lookup_value:
            for row in all_rows:
                if str(row.get(bsc.lookup_column, '')).strip() == bsc.lookup_value.strip():
                    return row
            # M7: lookup miss is missing data, not rows[0].
            logger.warning(
                "Lookup '%s=%s' missed in '%s'; no row selected",
                bsc.lookup_column, bsc.lookup_value, table_file)
            return None
        return all_rows[0]

    def _resolve_row_for_source(self, source_file: str, doc_index: int,
                                 batch_configs: Dict[str, BatchSourceConfig],
                                 resume: Optional[ResumeState] = None,
                                 all_rows: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, str]]:
        """Resolve the data row for a given source at a given document index."""
        if all_rows is None:
            all_rows = self._read_table_data(source_file)
        if not all_rows:
            return None

        bsc = batch_configs.get(source_file)
        if not bsc:
            return all_rows[0]

        if bsc.mode == RowIterationMode.CONSTANT:
            return self._resolve_constant_row(source_file, batch_configs, all_rows)

        start_offset = 0
        if resume and resume.continue_from_last:
            start_offset = resume.sources.get(source_file, 0)

        effective_i = start_offset + doc_index

        if bsc.mode == RowIterationMode.SEQUENTIAL:
            if effective_i < len(all_rows):
                return all_rows[effective_i]
            else:
                return None

        if bsc.mode == RowIterationMode.CIRCULAR:
            return all_rows[effective_i % len(all_rows)]

        # M7: unknown iteration mode selects no row (was rows[0]).
        logger.warning("Unknown batch mode %r for '%s'; no row selected",
                       bsc.mode, source_file)
        return None

    def count_source_rows(self, source_file: str) -> int:
        """Return the number of data rows in a batch source file (M3).

        Single engine row-count reused by the GUI (fill-form primary-row
        count, auto-info) and by :meth:`_compute_total_docs`, so the three
        previously duplicated counters cannot drift apart.
        """
        return len(self._read_table_data(source_file))

    def _compute_total_docs(self, config: TemplateConfig,
                            batch_configs: Dict[str, BatchSourceConfig],
                            resume: Optional[ResumeState] = None) -> Optional[int]:
        """Determine total number of documents to generate."""
        if config.total_docs is not None and config.total_docs > 0:
            return config.total_docs

        sequential_sources = [
            (name, bsc) for name, bsc in batch_configs.items()
            if bsc.mode == RowIterationMode.SEQUENTIAL
        ]
        if not sequential_sources:
            return None

        min_remaining = None
        for name, bsc in sequential_sources:
            start_offset = 0
            if resume and resume.continue_from_last:
                start_offset = resume.sources.get(name, 0)
            remaining = max(0, self.count_source_rows(name) - start_offset)
            if min_remaining is None or remaining < min_remaining:
                min_remaining = remaining

        return min_remaining if min_remaining and min_remaining > 0 else None

    def render(self, template_rel_path: str,
               user_values: Dict[str, str],
               batch_table: Optional[str] = None,
               output_dir: str = None,
               batch_configs: Optional[Dict[str, BatchSourceConfig]] = None,
               max_docs: Optional[int] = None,
               resume: Optional[ResumeState] = None) -> List[str]:
        """Render template into one or more output documents."""
        from .render_execute import execute_render
        return execute_render(
            self, template_rel_path, user_values,
            batch_table=batch_table,
            output_dir=output_dir,
            batch_configs=batch_configs,
            max_docs=max_docs,
            resume=resume,
        )
