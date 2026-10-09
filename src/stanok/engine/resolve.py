# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve: Excel rows + ProjectJSON → list[FillingJSON]. Pure, no side effects."""

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

logger = logging.getLogger(__name__)


def _format_dist(template: str, fields: dict[str, Any], index: int, template_name: str) -> str:
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
    if fmt == "month":
        if value > 999:
            raise ResolveError(
                f"counters.{counter_name}",
                ["counter overflow: month counter exceeded 999"],
            )
        return f"{today.strftime('%Y-%m')}-{value:03d}"
    return str(value)


def _resolve_field(
    row: dict[str, Any],
    field_name: str,
    field_def: FieldDef,
    pj: ProjectJSON,
    counters: dict[str, int],
    today: date,
) -> Any:
    """Resolve a single field value based on its source."""
    if field_def.source == FieldSource.CONSTANT:
        return field_def.value
    if field_def.source == FieldSource.TABLE:
        col_name = field_def.value
        if col_name not in row:
            raise ResolveError(
                f"fields.{field_name}",
                [f"column '{col_name}' not found in data source"],
            )
        return row.get(col_name)
    if field_def.source == FieldSource.COUNTER:
        counter_name = field_def.value
        if counter_name not in pj.counters:
            raise ResolveError(
                f"fields.{field_name}",
                [f"counter '{counter_name}' not defined in project"],
            )
        new_value = counters.get(counter_name, pj.counters[counter_name].last) + 1
        counters[counter_name] = new_value
        return _format_counter(
            new_value, pj.counters[counter_name].format, counter_name, today
        )
    if field_def.source == FieldSource.TODAY:
        return today
    raise ResolveError(
        f"fields.{field_name}",
        [f"unknown field source: {field_def.source}"],
    )


def _build_filling_json(
    row: dict[str, Any],
    template_name: str,
    template_def: TemplateDef,
    pj: ProjectJSON,
    counters: dict[str, int],
    doc_index: int,
    today: date,
) -> FillingJSON:
    """Build a single FillingJSON from a row."""
    fields: dict[str, Any] = {}
    for field_name, field_def in template_def.fields.items():
        try:
            fields[field_name] = _resolve_field(
                row, field_name, field_def, pj, counters, today
            )
        except ResolveError:
            raise
        except Exception as e:
            logger.error(f"resolve field {field_name}: {e}", exc_info=True)
            raise ResolveError(f"fields.{field_name}", [str(e)]) from e

    try:
        return FillingJSON(
            version=pj.version,
            template=template_name,
            fields=fields,
            dist=_format_dist(pj.filename_template, fields, doc_index, template_name),
        )
    except ResolveError:
        raise
    except Exception as e:
        logger.error(f"build filling row {doc_index}: {e}", exc_info=True)
        raise ResolveError("dist", [str(e)]) from e


def _pick_template(pj: ProjectJSON) -> tuple[str, TemplateDef]:
    if not pj.templates:
        raise ResolveError("templates", ["no templates defined in project"])
    names = list(pj.templates)
    if len(names) > 1:
        logger.warning("multiple templates, using first: %s", names[0])
    return names[0], pj.templates[names[0]]


def resolve_rows(
    rows: list[dict[str, Any]],
    pj: ProjectJSON,
    today: date | None = None,
) -> tuple[list[FillingJSON], dict[str, int]]:
    """Resolve Excel rows + ProjectJSON → (FillingJSON list, new counter state).

    Pure function: input PJ is never mutated. Caller (services) persists
    counters (`counters_state`) and `start_row` into PJ via storage.

    Args:
        rows: list of dicts from ExcelReader (including empty rows as Nones).
        pj: validated ProjectJSON.
        today: date for TODAY fields / month counters (default: date.today()).

    Returns:
        (filling list, counters) — counters map name → new last value.
    """
    if not pj.data_sources:
        raise ResolveError("data_sources", ["no data sources defined in project"])

    template_name, template_def = _pick_template(pj)

    # MVP: single data source.
    ds = pj.data_sources[0]
    if len(pj.data_sources) > 1:
        logger.warning("multiple data sources, using first: %s", ds.file)
    mode = ds.mode
    start_row = max(0, ds.start_row)

    today = today or date.today()
    counters: dict[str, int] = {n: c.last for n, c in pj.counters.items()}

    data_rows = rows[start_row:]
    if not data_rows:
        return [], counters

    if mode == "sequential":
        selected = data_rows
    elif mode == "constant":
        selected = [data_rows[0]] * len(data_rows)
    elif mode == "circular":
        # До FR-18 (max_docs): один круг, как sequential.
        selected = data_rows
    else:
        raise ResolveError("mode", [f"unknown mode: {mode}"])

    results = [
        _build_filling_json(row, template_name, template_def, pj, counters, i, today)
        for i, row in enumerate(selected, start=1)
    ]
    return results, counters
