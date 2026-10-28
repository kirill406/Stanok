# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve: Excel rows + ProjectJSON → list[FillingJSON]. Pure, no side effects.

021: a document is composed from several sources at once. A table field points to
a counter (`counter_name`); the counter is bound to a source (`table`) and holds
one position (`pos`) that is both the source row and the printed number.
Number of documents N = min(limit, available rows of sequential counters);
with no sequential counters — one circle of circular ones.
"""

import logging
import re
from datetime import date
from typing import Any

from .schema import (
    FieldDef,
    FieldSource,
    FillingJSON,
    ProjectJSON,
    ResolveError,
    TemplateDef,
)
from ..gui.strings import STRINGS

logger = logging.getLogger(__name__)

RU_MONTHS_GENITIVE = STRINGS.RU_MONTHS_GENITIVE.split("|")

#: today presets (FieldDef.value) → formatter; None/unknown = legacy date object.
TODAY_PRESETS = ("dmy", "day", "month_ru", "month_num", "year", "ru_long")

COUNTER_WIDTHS = ("1", "01", "001", "0001")


def _format_dist(
    template: str, fields: dict[str, Any], index: int, template_name: str
) -> str:
    """Render filename_template with fields + index + template name."""
    subs = {**fields, "i": str(index), "template": template_name}
    result = template
    for key, value in subs.items():
        placeholder = f"{{{key}}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
    unresolved = re.findall(r"\{([^}]+)\}", result)
    if unresolved:
        raise ResolveError("dist", [f"unknown placeholder {{{u}}}" for u in unresolved])
    return result


def _format_counter(value: int, fmt: str, counter_name: str, today: date) -> str:
    """Format counter value according to format."""
    if fmt == "month":  # legacy (020: GUI no longer offers it)
        if value > 999:
            raise ResolveError(
                f"counters.{counter_name}",
                ["counter overflow: month counter exceeded 999"],
            )
        return f"{today.strftime('%Y-%m')}-{value:03d}"
    if fmt in COUNTER_WIDTHS:
        return str(value).zfill(len(fmt))
    return str(value)  # "1", "plain" (legacy), unknown


def format_today(value: Any, today: date) -> Any:
    """Format today field by preset; legacy None/unknown → date object."""
    if value == "dmy":
        return today.strftime("%d.%m.%Y")
    if value == "day":
        return str(today.day)
    if value == "month_ru":
        return RU_MONTHS_GENITIVE[today.month - 1]
    if value == "month_num":
        return today.strftime("%m")
    if value == "year":
        return str(today.year)
    if value == "ru_long":
        return f"{today.day} {RU_MONTHS_GENITIVE[today.month - 1]} {today.year}"
    return today


def used_counters(pj: ProjectJSON, template_name: str) -> list[str]:
    """Ordered unique counter names referenced by the template (any field)."""
    tdef = pj.templates[template_name]
    names: list[str] = []
    for fdef in tdef.fields.values():
        if fdef.source == FieldSource.TABLE and fdef.counter_name:
            if fdef.counter_name not in names:
                names.append(fdef.counter_name)
        elif fdef.source == FieldSource.COUNTER and fdef.value:
            if fdef.value not in names:
                names.append(fdef.value)
    return names


def participating_sources(pj: ProjectJSON, template_name: str) -> list[str]:
    """Data-source files used by the template (via table-field counters).

    Counters that are referenced but not defined are skipped here; the
    counter guard lives in `resolve_rows` (clean ResolveError, not KeyError).
    """
    files: list[str] = []
    for cname in used_counters(pj, template_name):
        cdef = pj.counters.get(cname)
        if cdef is None:
            continue
        table = cdef.table
        if table is not None and table not in files:
            files.append(table)
    return files


def _modes(pj: ProjectJSON) -> dict[str, str]:
    return {ds.file: ds.mode for ds in pj.data_sources}


def _row_index(mode: str, pos: int, k: int, length: int) -> int | None:
    if length <= 0:
        return None
    if mode == "sequential":
        idx = pos + k
    elif mode == "circular":
        idx = (pos + k) % length
    elif mode == "constant":
        idx = pos
    else:
        raise ResolveError("mode", [f"unknown mode: {mode}"])
    return idx if 0 <= idx < length else None


def _document_count(
    pj: ProjectJSON,
    tdef: TemplateDef,
    names: list[str],
    rows_by_source: dict[str, list[dict]],
    modes: dict[str, str],
    *,
    ignore_limit: bool = False,
) -> int:
    seq_avail: list[int] = []
    circ_lens: list[int] = []
    for name in names:
        cdef = pj.counters[name]
        if cdef.table is None:
            continue
        rows = rows_by_source.get(cdef.table, [])
        mode = modes.get(cdef.table, "sequential")
        if mode == "sequential":
            seq_avail.append(max(0, len(rows) - cdef.pos))
        elif mode == "circular":
            circ_lens.append(len(rows))
    candidates: list[int] = []
    if tdef.limit > 0 and not ignore_limit:
        candidates.append(tdef.limit)
    if seq_avail:
        candidates.append(min(seq_avail))
    if candidates:
        n = min(candidates)
    elif circ_lens:
        n = min(circ_lens)
    else:
        n = 1
    n = max(0, n)
    logger.debug(
        f"document count: limit={tdef.limit} ignore_limit={ignore_limit} "
        f"seq_avail={seq_avail} circ_lens={circ_lens} n={n}"
    )
    return n


def available_documents(
    pj: ProjectJSON,
    template_name: str,
    rows_by_source: dict[str, list[dict]],
) -> int:
    """Rows available for a template without applying its document limit."""
    if template_name not in pj.templates:
        raise ResolveError("templates", [f"template not found: {template_name}"])
    tdef = pj.templates[template_name]
    names = used_counters(pj, template_name)
    for name in names:
        if name not in pj.counters:
            raise ResolveError("counters", [f"counter not defined: {name}"])
    return _document_count(
        pj, tdef, names, rows_by_source, _modes(pj), ignore_limit=True
    )


def _resolve_field(
    fdef: FieldDef,
    pj: ProjectJSON,
    rows_by_source: dict[str, list[dict]],
    modes: dict[str, str],
    k: int,
    today: date,
) -> Any:
    if fdef.source == FieldSource.CONSTANT:
        return fdef.value
    if fdef.source == FieldSource.TABLE:
        cname = fdef.counter_name
        cdef = pj.counters[cname]
        rows = rows_by_source.get(cdef.table, [])
        mode = modes.get(cdef.table, "sequential")
        idx = _row_index(mode, cdef.pos, k, len(rows))
        if idx is None:
            return None
        col_name = fdef.value
        row = rows[idx]
        if col_name not in row:
            raise ResolveError(
                f"fields.{col_name}",
                [f"column '{col_name}' not found (counter '{cname}')"],
            )
        return row.get(col_name)
    if fdef.source == FieldSource.COUNTER:
        cname = fdef.value
        cdef = pj.counters[cname]
        mode = modes.get(cdef.table) if cdef.table is not None else None
        value = cdef.pos if mode == "constant" else cdef.pos + k
        return _format_counter(value, cdef.format, cname, today)
    if fdef.source == FieldSource.TODAY:
        return format_today(fdef.value, today)
    raise ResolveError("fields", [f"unknown field source: {fdef.source}"])


def resolve_rows(
    rows_by_source: dict[str, list[dict[str, Any]]],
    pj: ProjectJSON,
    template_name: str,
    today: date | None = None,
) -> tuple[list[FillingJSON], list[str]]:
    """Compose documents from all participating sources (021).

    Pure function: input PJ is never mutated. Caller (services) persists
    counter positions into PJ (advancement depends on how many documents
    actually got written, so finalization lives in the service).

    Args:
        rows_by_source: data-source file → its data rows (dicts, no header).
        pj: validated ProjectJSON.
        template_name: template to run.
        today: date for TODAY fields / month counters (default: date.today()).

    Returns:
        (filling list, ordered list of counter names used by the template).
    """
    if template_name not in pj.templates:
        raise ResolveError("templates", [f"template not found: {template_name}"])

    tdef = pj.templates[template_name]
    today = today or date.today()
    modes = _modes(pj)
    names = used_counters(pj, template_name)
    for name in names:
        if name not in pj.counters:
            raise ResolveError("counters", [f"counter not defined: {name}"])

    logger.debug(
        f"resolve template {template_name}: sources={list(rows_by_source)} "
        f"counters={names} modes={modes}"
    )
    n = _document_count(pj, tdef, names, rows_by_source, modes)
    logger.debug(f"resolve {template_name}: {n} documents")

    results: list[FillingJSON] = []
    for k in range(n):
        fields: dict[str, Any] = {}
        for fname, fdef in tdef.fields.items():
            try:
                fields[fname] = _resolve_field(
                    fdef, pj, rows_by_source, modes, k, today
                )
            except ResolveError:
                raise
            except Exception as e:
                logger.error(f"resolve field {fname}: {e}", exc_info=True)
                raise ResolveError(f"fields.{fname}", [str(e)]) from e
        try:
            dist = _format_dist(pj.filename_template, fields, k + 1, template_name)
        except ResolveError:
            raise
        except Exception as e:
            logger.error(f"build filling row {k + 1}: {e}", exc_info=True)
            raise ResolveError("dist", [str(e)]) from e
        try:
            results.append(
                FillingJSON(
                    version=pj.version, template=template_name, fields=fields, dist=dist
                )
            )
            logger.debug(f"filling {k + 1}/{n}: {dist}")
        except ResolveError:
            raise
        except Exception as e:
            logger.error(f"build filling row {k + 1}: {e}", exc_info=True)
            raise ResolveError("dist", [str(e)]) from e

    return results, names


def modes_of(pj: ProjectJSON) -> dict[str, str]:
    """Public: data-source file → mode (for the service's cursor finalization)."""
    return _modes(pj)
