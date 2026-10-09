# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end generation: tables → resolve → render → docx (single entry)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..engine.render import render
from ..engine.resolve import resolve_rows
from ..engine.schema import DataSourceDef, ProjectJSON, TemplateDef, validate_pj
from ..tables.excel import ExcelReader
from .storage import ProjectStore

if TYPE_CHECKING:
    from docx.document import Document

logger = logging.getLogger(__name__)

RESULT_DIR = "Результат"


class TemplateError(Exception):
    """Template/config selection error (fail-fast, aborts the whole run)."""


@dataclass(frozen=True)
class GenerateCommand:
    """Generation run parameters (single entry point for CLI/GUI)."""

    project_ref: str | Path
    template: str | None = None
    data_source: str | None = None
    max_docs: int | None = None
    resume: bool = False


@dataclass
class GenerateReport:
    """Generation run outcome."""

    created: int = 0
    skipped: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)
    output_paths: list[Path] = field(default_factory=list)
    elapsed: float = 0.0


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


def _resolve_project_dir(
    ref: str | Path, pj: ProjectJSON, config_path: Path, store: ProjectStore
) -> Path:
    """Find project folder: direct dir ref, else AJ recent lookup by config."""
    ref_path = Path(ref) if isinstance(ref, str) else ref
    if ref_path.exists() and ref_path.is_dir():
        return ref_path.resolve()
    # Config-name ref: folder remembered in recent projects.
    for item in store.get_recent():
        if item.config == ref_path.name or item.config == config_path.stem:
            folder = Path(item.folder)
            if folder.is_dir():
                return folder.resolve()
    raise TemplateError(
        f"project folder not found for '{ref}': pass a project folder path"
    )


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


def _pick_data_source(pj: ProjectJSON, name: str | None) -> tuple[int, DataSourceDef]:
    if not pj.data_sources:
        raise TemplateError("no data sources defined in project")
    if name is None:
        if len(pj.data_sources) > 1:
            logger.warning(f"multiple data sources, using first: {pj.data_sources[0].file}")
        return 0, pj.data_sources[0]
    for i, ds in enumerate(pj.data_sources):
        if ds.file == name:
            return i, ds
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
) -> GenerateReport:
    """Run tables → resolve → render → docx pipeline, return report.

    Fail-fast (exception out): project/template/data config errors.
    Per-row (collected into report.errors): render/save errors.
    """
    started = time.monotonic()
    report = GenerateReport()
    store = store or ProjectStore()
    logger.info(f"generate started: ref={cmd.project_ref} resume={cmd.resume}")

    pj, config_path = store.resolve_project(cmd.project_ref)
    project_dir = _resolve_project_dir(cmd.project_ref, pj, config_path, store)

    template_name, template_def = _pick_template(pj, cmd.template)
    ds_index, ds = _pick_data_source(pj, cmd.data_source)
    template_path = project_dir / template_def.file
    if not template_path.is_file():
        raise TemplateError(f"template file not found: {template_path}")

    rows = ExcelReader().read(project_dir / ds.file)
    logger.debug(f"read {len(rows)} rows from {ds.file}")
    if not rows:
        logger.info("generate finished: empty data source")
        report.elapsed = time.monotonic() - started
        return report

    # Work copy: single template + single source, effective cursor.
    work = pj.model_copy(deep=True)
    work.templates = {template_name: template_def}
    work_ds = work.data_sources[ds_index]
    start = max(0, ds.start_row if cmd.resume else 0)
    work_ds.start_row = 0
    work = validate_pj(work.model_dump(mode="json"))

    indexed = [(i, r) for i, r in enumerate(rows[start:], start)]
    nonempty = [(i, r) for i, r in indexed if not _is_empty_row(r)]
    report.skipped = len(indexed) - len(nonempty)
    if not nonempty:
        logger.info("generate finished: only empty rows")
        report.elapsed = time.monotonic() - started
        return report

    limit = cmd.max_docs
    if limit is not None and limit <= 0:
        report.elapsed = time.monotonic() - started
        return report
    if ds.mode == "constant":
        attempt = [(nonempty[0][0], nonempty[0][1])] * (
            limit if limit is not None else len(nonempty)
        )
        consumed_through = nonempty[0][0]
    else:
        attempt = nonempty if limit is None else nonempty[:limit]
        consumed_through = attempt[-1][0]
    if not attempt:  # pragma: no cover - defensive, nonempty is non-empty here
        report.elapsed = time.monotonic() - started
        return report

    fillings, counters = resolve_rows([r for _, r in attempt], work, today)
    logger.debug(f"resolved {len(fillings)} fillings, mode={ds.mode}")

    out_dir = project_dir / RESULT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for (abs_index, _), fj in zip(attempt, fillings):
        try:
            doc = render(fj, template_path)
            path = _save_document(doc, out_dir, fj.dist, abs_index)
            report.output_paths.append(path)
            report.created += 1
        except Exception as e:
            logger.warning(f"row {abs_index} failed: {e}", exc_info=True)
            report.errors.append((abs_index, str(e)))

    if report.created:
        for name in pj.counters:
            if name in counters:
                pj.counters[name].last = counters[name]
        # Counters for docs that failed to render keep resolved numbers
        # (gaps are accepted); cursor advances past all attempted rows.
        pj.data_sources[ds_index].start_row = consumed_through + 1
        store.save(pj, name=config_path.stem)
        logger.info(
            f"saved PJ counters/start_row={consumed_through + 1} to {config_path}"
        )

    report.elapsed = time.monotonic() - started
    logger.info(
        f"generate finished: created={report.created} skipped={report.skipped} "
        f"errors={len(report.errors)} elapsed={report.elapsed:.2f}s"
    )
    return report
