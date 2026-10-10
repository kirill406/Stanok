# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end generation: tables → resolve → render → docx (single entry)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..engine.render import render
from ..engine.resolve import resolve_rows
from ..engine.schema import DataSourceDef, ProjectJSON, TemplateDef, validate_pj
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
    template: str | None = None
    data_source: str | None = None  # None = all sources in PJ order (FR-7)
    max_docs: int | None = None  # per-source limit (013)
    resume: bool = False


@dataclass
class GenerateReport:
    """Generation run outcome."""

    created: int = 0
    skipped: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)
    output_paths: list[Path] = field(default_factory=list)
    elapsed: float = 0.0
    resumed_from: int | None = None  # input cursor; None on fresh start


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


def _is_empty_row(row: dict[str, Any]) -> bool:
    return all(v is None or v == "" for v in row.values())


def _pick_template(pj: ProjectJSON, name: str | None) -> tuple[str, TemplateDef]:
    if not pj.templates:
        raise TemplateError("no templates defined in project")
    if name is None:
        picked = next(iter(pj.templates))
        if len(pj.templates) > 1:
            logger.warning(f"multiple templates, using first: {picked}")
        return picked, pj.templates[picked]
    if name not in pj.templates:
        raise TemplateError(f"template not found: {name}")
    return name, pj.templates[name]


def _pick_data_sources(
    pj: ProjectJSON, name: str | None
) -> list[tuple[int, DataSourceDef]]:
    """Select sources to run: all in PJ order (None) or one by file name."""
    if not pj.data_sources:
        raise TemplateError("no data sources defined in project")
    if name is None:
        return list(enumerate(pj.data_sources))
    for i, ds in enumerate(pj.data_sources):
        if ds.file == name:
            return [(i, ds)]
    raise TemplateError(f"data source not found: {name}")


def _save_document(doc: Document, out_dir: Path, dist: str, row_index: int) -> Path:
    """Save rendered doc under out_dir/dist with unique name (FR-11)."""
    target = (out_dir / dist).resolve()
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

    FR-7: data_source=None runs ALL sources in PJ order with shared counters;
    per-source cursors persist independently. max_docs applies per source.
    Fail-fast (exception out): project/template/data config errors.
    Per-source file errors (multi-source only) and per-row render/save errors
    are collected into report.errors.
    progress(created, total) is called after each created document;
    returning True cancels the run (partial report, created files stay).
    """
    started = time.monotonic()
    report = GenerateReport()
    store = store or ProjectStore()
    logger.info(
        f"generate started: ref={cmd.project_ref} resume={cmd.resume} "
        f"source={cmd.data_source or 'all'}"
    )

    pj, config_path = store.resolve_project(cmd.project_ref)
    project_dir = project_folder(cmd.project_ref, pj, config_path, store)

    template_name, template_def = _pick_template(pj, cmd.template)
    sources = _pick_data_sources(pj, cmd.data_source)
    multi = len(sources) > 1
    template_path = project_dir / template_def.file
    if not template_path.is_file():
        raise TemplateError(f"template file not found: {template_path}")

    out_dir = project_dir / RESULT_DIR

    first_ds = sources[0][1]
    first_start = max(0, first_ds.start_row if cmd.resume else 0)
    report.resumed_from = first_start or None

    cancelled = False
    for ds_index, ds in sources:
        if cancelled:
            break
        try:
            rows = ExcelReader().read(project_dir / ds.file)
        except Exception as e:
            if not multi:
                raise
            logger.warning(f"source {ds.file} failed: {e}", exc_info=True)
            report.errors.append((-1, f"{ds.file}: {e}"))
            continue
        logger.debug(f"read {len(rows)} rows from {ds.file}")
        if not rows:
            logger.info(f"generate: empty data source {ds.file}")
            continue

        # Work copy: single template + THIS source only (013: resolve reads [0]).
        work = pj.model_copy(deep=True)
        work.templates = {template_name: template_def}
        src = ds.model_copy()
        start = max(0, ds.start_row if cmd.resume else 0)
        src.start_row = 0
        work.data_sources = [src]
        work = validate_pj(work.model_dump(mode="json"))

        indexed = [(i, r) for i, r in enumerate(rows[start:], start)]
        nonempty = [(i, r) for i, r in indexed if not _is_empty_row(r)]
        report.skipped += len(indexed) - len(nonempty)
        if not nonempty:
            logger.info(f"generate: only empty rows in {ds.file}")
            continue

        limit = cmd.max_docs
        if limit is not None and limit <= 0:
            continue

        # Mode selection (incl. circular cycling) lives in the engine;
        # here only clean rows + limit go in, cursor math stays here.
        clean_idx = [i for i, _ in nonempty]
        fillings, counters = resolve_rows(
            [r for _, r in nonempty], work, today, limit=limit
        )
        logger.debug(f"resolved {len(fillings)} fillings, mode={ds.mode}")
        n = len(clean_idx)
        if ds.mode == "circular" and limit is not None:
            attempt_idx = [clean_idx[k % n] for k in range(len(fillings))]
            new_start = start + len(indexed)
        elif ds.mode == "constant":
            attempt_idx = [clean_idx[0]] * len(fillings)
            new_start = clean_idx[0] + 1
        else:
            attempt_idx = clean_idx[: len(fillings)]
            new_start = start + len(indexed if limit is None else indexed[:limit])
        attempt = list(zip(attempt_idx, fillings))

        total = len(fillings)
        tag = f"{ds.file}: " if multi else ""
        source_created = 0
        out_dir.mkdir(parents=True, exist_ok=True)
        for abs_index, fj in attempt:
            try:
                doc = render(fj, template_path)
                path = _save_document(doc, out_dir, fj.dist, abs_index)
                report.output_paths.append(path)
                report.created += 1
                source_created += 1
            except Exception as e:
                logger.warning(f"row {abs_index} failed: {e}", exc_info=True)
                report.errors.append((abs_index, f"{tag}{e}"))
            if progress is not None:
                try:
                    if progress(report.created, total):
                        logger.info(
                            f"generate cancelled after {report.created} docs"
                        )
                        cancelled = True
                        break
                except Exception as e:
                    logger.warning(f"progress callback failed: {e}", exc_info=True)
        if cancelled:
            logger.info("generate cancelled by user")

        if source_created:
            for name in pj.counters:
                if name in counters:
                    pj.counters[name].last = counters[name]
            # Counters for docs that failed to render keep resolved numbers
            # (gaps are accepted); cursor advances per mode (§2.2 spec 012).
            pj.data_sources[ds_index].start_row = new_start

    if report.created:
        store.save(pj, name=config_path.stem)
        logger.info(f"saved PJ counters/cursors to {config_path}")

    report.elapsed = time.monotonic() - started
    logger.info(
        f"generate finished: created={report.created} skipped={report.skipped} "
        f"errors={len(report.errors)} elapsed={report.elapsed:.2f}s"
    )
    return report
