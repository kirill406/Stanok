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
    default_project_file, resolve_project_file,
)
from .data_reader import DataReader
from .render_loop import (
    scan_raw_placeholders, process_xml,
    write_output_doc, update_resume_state,
)


class Renderer:
    def __init__(self, project_dir: str, data_reader: DataReader):
        self.project_dir = project_dir
        self.data_reader = data_reader
        self.project: Optional[Project] = None
        self._template_path_cache = {}

    def load_project(self):
        project_file = resolve_project_file(self.project_dir)
        if project_file is None:
            project_file = default_project_file(self.project_dir)
        self.project_file = project_file
        self.project = Project.from_file(project_file) if os.path.exists(project_file) else Project()

    def save_project(self):
        self._atomic_write_project()

    def _atomic_write_project(self):
        """Atomically write project file via the shared schema helper."""
        from .schema import atomic_write_json
        project_file = getattr(self, 'project_file',
                               default_project_file(self.project_dir))
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

    def count_source_rows(self, source_file: str) -> int:
        """Return the number of data rows in a batch source file (M3).

        Single engine row-count reused by the GUI (fill-form primary-row
        count, auto-info) and by :meth:`_compute_total_docs`, so the three
        previously duplicated counters cannot drift apart.
        """
        from .data_formatting import read_project_table
        return len(read_project_table(
            self.data_reader, self.project_dir, source_file))

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

    def render_from_json(self, filling: dict,
                         output_dir: str = None) -> List[str]:
        """Render a document from Filling JSON (003-json single mechanism).

        ``filling`` is resolved data of a single document:
        ``{"template": "name.docx", "dist": "out/file.docx",
        "fields": {name: value}, "images": {name: path}}`` — values are
        already resolved (no placeholders). Pure path: no config reads,
        no Excel, no row selection — straight to ``execute_render_fillings``.

        ``output_dir`` wins when given; otherwise the directory part
        of ``dist`` is used (relative → under ``project_dir``);
        otherwise the engine default (``Результат``) applies.
        The file name part of ``dist`` is informational
        (naming stays with the project config/auto-naming).

        Raises:
            ValueError: ``filling`` is not a dict, or required
                ``template``/``fields`` are missing or malformed.
                (``ValueError``, not ``GenerationError``: ``renderer``
                cannot import ``docxforge.generate`` — circular
                import — so ``generate.py`` wraps this into
                ``GenerationError`` at its own boundary).

        Returns:
            List of created file paths.
        """
        from .errors import (
            FILLING_FIELDS_NOT_OBJECT,
            FILLING_NOT_OBJECT,
            FILLING_NO_FIELDS,
            FILLING_NO_TEMPLATE,
            message_for_code,
        )
        from .render_execute import execute_render_fillings
        if not isinstance(filling, dict):
            raise ValueError(message_for_code(FILLING_NOT_OBJECT))
        template = filling.get('template')
        if not isinstance(template, str) or not template.strip():
            raise ValueError(message_for_code(FILLING_NO_TEMPLATE))
        if 'fields' not in filling:
            raise ValueError(message_for_code(FILLING_NO_FIELDS))
        fields = filling.get('fields')
        if not isinstance(fields, dict):
            raise ValueError(message_for_code(FILLING_FIELDS_NOT_OBJECT))
        user_values = {
            str(key): ('' if value is None else value
                       if isinstance(value, str) else str(value))
            for key, value in fields.items()
        }
        images = filling.get('images') or {}
        if not isinstance(images, dict):
            raise ValueError(message_for_code(FILLING_FIELDS_NOT_OBJECT))
        if output_dir is None:
            dist = filling.get('dist')
            if isinstance(dist, str) and dist.strip():
                dist_dir = os.path.dirname(dist.strip())
                if dist_dir:
                    output_dir = (dist_dir if os.path.isabs(dist_dir)
                                  else os.path.join(self.project_dir, dist_dir))
        logger.info("Rendering '%s' from Filling JSON (%d fields)",
                    template, len(user_values))
        return execute_render_fillings(
            self, template, [{'fields': user_values, 'images': images}],
            output_dir=output_dir)
