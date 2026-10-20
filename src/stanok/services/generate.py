# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end generation: tables → resolve → render → docx (single entry).

021: all sources participating in the template run at once; each counter holds
one position (`pos`) that is both its source row and printed number and persists
per `resume`. No launch-point/selection dependency.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..engine.render import render
from ..engine.resolve import modes_of, participating_sources, resolve_rows
from ..engine.schema import ProjectJSON, TemplateDef
from ..gui.strings import STRINGS
from ..tables.excel import ExcelReader
from .storage import ProjectStore, project_folder

if TYPE_CHECKING:
    from docx.document import Document

logger = logging.getLogger(__name__)

RESULT_DIR = STRINGS.GEN_RESULT_DIR


class TemplateError(Exception):
    """Template/config selection error (fail-fast, aborts the whole run)."""


@dataclass(frozen=True)
class GenerateCommand:
    """Generation run parameters (single entry point for CLI/GUI)."""

    project_ref: str | Path
    template: str | None = None  # None = project default_template (021)


@dataclass
class GenerateReport:
    """Generation run outcome."""

    created: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)
    output_paths: list[Path] = field(default_factory=list)
    elapsed: float = 0.0
    planned: int = 0  # documents resolved for this run (before errors)
    limit: int = 0  # template limit (0 = unlimited)


def _unique_path(base: Path) -> Path:
    """Return base or first free `name (1).ext`, `name (2).ext`, ... variant."""
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    i = 1
    while True:
        candidate = base.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def _pick_template(pj: ProjectJSON, name: str | None) -> tuple[str, TemplateDef]:
    if not pj.templates:
        raise TemplateError("no templates defined in project")
    if name:
        if name not in pj.templates:
            raise TemplateError(f"template not found: {name}")
        return name, pj.templates[name]
    default = pj.default_template or next(iter(pj.templates))
    if default not in pj.templates:
        raise TemplateError(f"default template not found: {default}")
    return default, pj.templates[default]


def _check_table_columns(
    rows_by_source: dict[str, list[dict]],
    template_def: TemplateDef,
    pj: ProjectJSON,
) -> None:
    """Fail fast when a table field's column is missing from its source (021).

    The source of a table field comes from its counter's `table`. Headers are
    the union of row keys (ragged rows safe).
    """
    for field_name, fdef in template_def.fields.items():
        if fdef.source.value != "table":
            continue
        cdef = pj.counters.get(fdef.counter_name) if fdef.counter_name else None
        if cdef is None:
            raise TemplateError(
                f"field '{field_name}': counter '{fdef.counter_name}' not defined"
            )
        rows = rows_by_source.get(cdef.table, [])
        headers: list[str] = []
        for r in rows:
            for h in r.keys():
                if h not in headers:
                    headers.append(h)
        if not headers:
            continue  # empty source: no documents will be produced
        column = str(fdef.value)
        if column not in headers:
            raise TemplateError(
                f"field '{field_name}': column '{column}' "
                f"not found in {cdef.table}"
            )


def _save_document(doc: Document, out_dir: Path, dist: str, row_index: int) -> Path:
    """Save rendered doc under out_dir/dist with unique name (FR-11)."""
    target = (out_dir / dist).resolve()
    if not target.suffix:
        target = target.with_suffix(".docx")
    try:
        target.relative_to(out_dir.resolve())
    except ValueError:
        raise TemplateError(f"row {row_index}: dist escapes result dir: {dist}")
    target.parent.mkdir(parents=True, exist_ok=True)
    final = _unique_path(target)
    doc.save(str(final))
    return final


def generate_documents(
    cmd: GenerateCommand,
    *,
    store: ProjectStore | None = None,
    today: date | None = None,
    progress: Callable[[int, int], bool] | None = None,
) -> GenerateReport:
    """Run tables → resolve → render → docx pipeline, return report.

    021: the template's participating sources are read and composed together;
    counters/cursors persist according to each counter's `resume`.
    Fail-fast (exception out): project/template/data config errors.
    Per-row render/save errors are collected into report.errors.
    progress(created, total) is called after each created document;
    returning True cancels the run (partial report, created files stay).
    """
    started = time.monotonic()
    report = GenerateReport()
    store = store or ProjectStore()
    logger.info(
        f"generate started: ref={cmd.project_ref} template={cmd.template or 'default'}"
    )

    pj, config_path = store.resolve_project(cmd.project_ref)
    project_dir = project_folder(cmd.project_ref, pj, config_path, store)

    template_name, template_def = _pick_template(pj, cmd.template)
    template_path = project_dir / template_def.file
    if not template_path.is_file():
        raise TemplateError(f"template file not found: {template_path}")

    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    reader = ExcelReader()
    for file in participating_sources(pj, template_name):
        path = project_dir / file
        try:
            rows_by_source[file] = reader.read(path)
        except Exception as e:
            logger.error(f"source {file} failed: {e}", exc_info=True)
            raise TemplateError(f"data source not readable: {file}: {e}") from e

    _check_table_columns(rows_by_source, template_def, pj)

    fillings, used = resolve_rows(rows_by_source, pj, template_name, today)
    logger.debug(f"resolved {len(fillings)} fillings for {template_name}")

    modes = modes_of(pj)
    origin = {name: pj.counters[name].pos for name in used}

    out_dir = project_dir / RESULT_DIR
    total = len(fillings)
    report.planned = total
    report.limit = template_def.limit
    cancelled = False
    processed = 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, fj in enumerate(fillings, start=1):
        processed += 1
        try:
            doc = render(fj, template_path)
            path = _save_document(doc, out_dir, fj.dist, k)
            report.output_paths.append(path)
            report.created += 1
        except Exception as e:
            logger.warning(f"row {k} failed: {e}", exc_info=True)
            report.errors.append((k, str(e)))
        if progress is not None:
            try:
                if progress(report.created, total):
                    logger.info(f"generate cancelled after {report.created} docs")
                    cancelled = True
                    break
            except Exception as e:
                logger.warning(f"progress callback failed: {e}", exc_info=True)
    if cancelled:
        logger.info("generate cancelled by user")

    for name in used:
        cdef = pj.counters[name]
        orig_pos = origin[name]
        if cdef.table is None:
            # Numeric counter: no row cursor, numbering always continues.
            cdef.pos = orig_pos + processed
            continue
        if not cdef.resume:
            continue
        mode = modes.get(cdef.table, "sequential")
        if mode == "constant":
            # Constant source: the position never changes.
            continue
        # Sequential/circular: keep the absolute count; the row wraps at read
        # time, so the printed number keeps growing.
        cdef.pos = orig_pos + processed

    # Persist positions whenever documents were attempted (created + errors).
    # An all-errored run must still advance, matching `processed`.
    if processed:
        store.save(pj, name=config_path.stem)
        logger.info(f"saved PJ counter positions to {config_path}")

    report.elapsed = time.monotonic() - started
    logger.info(
        f"generate finished: created={report.created} "
        f"errors={len(report.errors)} elapsed={report.elapsed:.2f}s"
    )
    return report
