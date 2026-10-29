# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end generation: tables → resolve → render → docx (single entry).

021: all sources participating in the template run at once; each counter holds
one position (`pos`) that is both its source row and printed number and persists
per `resume`. No launch-point/selection dependency.
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..engine.render import RenderError, render
from ..engine.resolve import (
    available_documents,
    modes_of,
    participating_sources,
    resolve_rows,
)
from ..engine.schema import ProjectJSON, TemplateDef
from ..gui.strings import STRINGS
from ..tables.excel import ExcelReader, TableReadError
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
    resolved: int = 0  # fillings produced by resolve
    limit: int = 0  # template limit (0 = unlimited)
    skipped_limit: int = 0  # available rows not taken because of the limit
    skipped_exhausted: int = 0  # limit not reached because data ended
    skipped_columns: dict[str, list[str]] = field(default_factory=dict)
    output_dir: Path | None = None


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


def _duplicate_result(path: Path, out_dir: Path, dest_dirs: list[str]) -> list[str]:
    """Copy one saved result into each extra folder (025); return error messages.

    The copy keeps the path below out_dir, so a dist with subfolders stays intact.
    A failing folder does not stop the others and does not undo the document.
    """
    rel = path.relative_to(out_dir.resolve())
    errors: list[str] = []
    for dest in dest_dirs:
        if Path(dest).resolve() == out_dir.resolve():
            continue  # the project's own result folder is never a copy target
        try:
            target = _unique_path(Path(dest) / rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        except OSError as e:
            logger.warning(f"copy {path} to {dest} failed: {e}", exc_info=True)
            errors.append(STRINGS.GEN_COPY_FAILED.format(dest=dest, cause=e))
        else:
            logger.debug(f"result copied: {target}")
    return errors


def _save_document(doc: Document, out_dir: Path, dist: str, row_index: int) -> Path:
    """Save rendered doc under out_dir/dist with unique name (FR-11)."""
    target = (out_dir / dist).resolve()
    # Append, not replace: "Договор №1.2" must keep its dots.
    if target.suffix.lower() != ".docx":
        target = target.with_name(target.name + ".docx")
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
    logger.debug(
        f"generate command: ref={cmd.project_ref} "
        f"template={cmd.template or 'default'}"
    )

    pj, config_path = store.resolve_project(cmd.project_ref)
    project_dir = project_folder(cmd.project_ref, pj, config_path, store)

    template_name, template_def = _pick_template(pj, cmd.template)
    template_path = project_dir / template_def.file
    if not template_path.is_file():
        raise TemplateError(f"template file not found: {template_path}")

    out_dir = project_dir / RESULT_DIR
    report.output_dir = out_dir
    logger.info(
        f"generate started: ref={cmd.project_ref} config={config_path.name} "
        f"project_dir={project_dir} template={template_name} "
        f"file={template_def.file} limit={template_def.limit} out_dir={out_dir}"
    )

    participating = participating_sources(pj, template_name)
    logger.debug(f"generate participating sources: {participating}")
    for source in pj.data_sources:
        if source.file not in participating:
            logger.info(
                f"source {source.file} not used by template {template_name} "
                f"(mode={source.mode})"
            )

    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    reader = ExcelReader()
    for file in participating:
        path = project_dir / file
        logger.debug(f"reading source {file}: {path}")
        try:
            rows_by_source[file] = reader.read(path)
        except TableReadError as e:
            logger.error(f"source {file} failed: {e}", exc_info=True)
            raise TemplateError(f"data source not readable: {file}: {e}") from e
        except Exception as e:
            logger.critical(
                f"unexpected source read failure {file}: {e}", exc_info=True
            )
            raise TemplateError(f"data source not readable: {file}: {e}") from e
        logger.debug(f"source {file}: rows={len(rows_by_source[file])}")
        skipped = reader.skipped_columns.get(path, [])
        if skipped:
            report.skipped_columns[file] = skipped
            logger.warning(f"source {file} skipped columns: {skipped}")

    _check_table_columns(rows_by_source, template_def, pj)

    fillings, used = resolve_rows(rows_by_source, pj, template_name, today)
    modes = modes_of(pj)
    origin = {name: pj.counters[name].pos for name in used}
    total = len(fillings)
    available = available_documents(pj, template_name, rows_by_source)
    logger.debug(
        f"resolved {total} fillings for {template_name}: "
        f"available={available} limit={template_def.limit} "
        f"modes={modes} start_positions={origin}"
    )

    report.planned = total
    report.resolved = total
    report.limit = template_def.limit
    if template_def.limit > 0:
        report.skipped_limit = max(0, available - total)
        report.skipped_exhausted = max(0, template_def.limit - total)
    if total == 0:
        logger.warning(
            f"generate produced no documents: template={template_name} "
            f"available={available} limit={template_def.limit}"
        )

    cancelled = False
    processed = 0
    logger.debug(f"creating result dir: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, fj in enumerate(fillings, start=1):
        processed += 1
        try:
            doc = render(fj, template_path)
            path = _save_document(doc, out_dir, fj.dist, k)
            report.output_paths.append(path)
            report.created += 1
            for message in _duplicate_result(path, out_dir, pj.result_dirs):
                report.errors.append((k, message))
            logger.debug(f"document {k}/{total} created: {path}")
        except (RenderError, TemplateError, OSError, ValueError) as e:
            logger.warning(f"row {k}/{total} failed: {e}", exc_info=True)
            report.errors.append((k, str(e)))
        except Exception as e:
            logger.critical(
                f"row {k}/{total} unexpected failure: {e}", exc_info=True
            )
            report.errors.append((k, str(e)))
        if progress is not None:
            try:
                if progress(report.created, total):
                    logger.info(
                        f"generate cancelled after {report.created}/{total} docs"
                    )
                    cancelled = True
                    break
            except Exception as e:
                logger.critical(
                    f"progress callback failed at {report.created}/{total}: {e}",
                    exc_info=True,
                )
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
        f"generate finished: ref={cmd.project_ref} template={template_name} "
        f"planned={report.planned} resolved={report.resolved} "
        f"created={report.created} errors={len(report.errors)} "
        f"skipped_limit={report.skipped_limit} "
        f"skipped_exhausted={report.skipped_exhausted} "
        f"elapsed={report.elapsed:.2f}s out_dir={out_dir}"
    )
    return report
