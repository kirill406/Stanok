# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve: Excel rows + ProjectJSON → list[FillingJSON]."""

import itertools
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .schema import (
    DataSourceDef,
    FillingJSON,
    ProjectJSON,
    ResolveError,
)

logger = logging.getLogger(__name__)


def _format_dist(template: str, fields: dict[str, Any], index: int, template_name: str) -> str:
    """Render filename_template with fields + index + template name."""
    # Build substitution dict
    subs = {**fields, "i": str(index), "template": template_name}
    result = template
    for key, value in subs.items():
        placeholder = f"{{{key}}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
    # Check for unresolved placeholders
    import re
    unresolved = re.findall(r"\{([^}]+)\}", result)
    if unresolved:
        raise ResolveError("dist", [f"unknown placeholder {{{u}}}" for u in unresolved])
    return result


def _normalize_counter_format(value: int, fmt: str, counter_name: str) -> str:
    """Format counter value according to format."""
    if fmt == "plain":
        return str(value)
    if fmt == "month":
        month_prefix = date.today().strftime("%Y-%m")
        if value > 999:
            raise ResolveError(
                f"counters.{counter_name}",
                ["counter overflow: month counter exceeded 999"],
            )
        return f"{month_prefix}-{value:03d}"
    # default to plain
    return str(value)


def _resolve_field(
    row: dict[str, Any],
    template_name: str,
    template_def,
    pj,
    counters_state: dict[str, int],
    field_name: str,
    field_def,
) -> Any:
    """Resolve a single field value based on its source."""
    if field_def.source == "constant":
        return field_def.value
    elif field_def.source == "table":
        col_name = field_def.value
        if col_name not in row:
            raise ResolveError(
                f"fields.{field_name}",
                [f"column '{col_name}' not found in data source"],
            )
        return row.get(col_name)
    elif field_def.source == "counter":
        counter_name = field_def.value
        if counter_name not in pj.counters:
            raise ResolveError(
                f"fields.{field_name}",
                [f"counter '{counter_name}' not defined in project"],
            )
        # Increment and get value
        current = counters_state.get(counter_name, 0)
        new_value = current + 1
        counters_state[counter_name] = new_value
        # Update PJ counter (will be persisted later)
        pj.counters[field_def.value].last = new_value
        counter_def = pj.counters[field_def.value]
        return _normalize_counter_format(new_value, counter_def.format, field_def.value)
    elif field_def.source == "today":
        return date.today()
    else:
        raise ResolveError(
            f"fields.{field_name}",
            [f"unknown field source: {field_def.source}"],
        )


def _build_filling_json(
    row: dict[str, Any],
    template_name: str,
    pj: "ProjectJSON",
    counters_state: dict[str, int],
    doc_index: int,
) -> "FillingJSON":
    """Build a single FillingJSON from a row."""
    if template_name not in pj.templates:
        raise ResolveError(
            "template",
            [f"template '{template_name}' not found in project"],
        )

    template_def = pj.templates[template_name]
    fields: dict[str, Any] = {}

    for field_name, field_def in template_def.fields.items():
        try:
            value = _resolve_field(
                row, pj.templates.keys().__iter__().__next__(), template_def, pj,
                counters_state, field_name, field_def
            )
        except ResolveError:
            raise
        except Exception as e:
            raise ResolveError(f"fields.{field_name}", [str(e)]) from e
        fields[field_name] = value

    # Build dist
    dist = _format_dist(
        pj.filename_template,
        fields,
        doc_index,
        template_name
    )

    return FillingJSON(
        version=pj.version,
        template=template_name,
        fields=fields,
        dist=dist,
    )


def resolve_rows(
    rows: list[dict[str, Any]],
    pj: ProjectJSON,
) -> list["FillingJSON"]:
    """Resolve Excel rows + ProjectJSON → list[FillingJSON].

    Args:
        rows: list of dicts from ExcelReader (all rows including empty ones with None values)
        pj: validated ProjectJSON

    Returns:
        list of FillingJSON ready for rendering
    """
    if not pj.templates:
        raise ResolveError("templates", ["no templates defined in project"])

    if not pj.data_sources:
        raise ResolveError("data_sources", ["no data sources defined in project"])

    # Use first data source (MVP: single source)
    ds = pj.data_sources[0]
    mode = ds.mode
    start_row = max(0, ds.start_row)

    # Initialize counters state from PJ
    counters_state = {name: counter.last for name, counter in pj.counters.items()}

    # Slice rows according to mode and start_row
    data_rows = rows[start_row:]
    if not data_rows:
        return []

    results: list[FillingJSON] = []
    doc_index = 1

    if mode == "sequential":
        for row in data_rows:
            fj = _build_filling_json(row, pj.templates.keys().__iter__().__next__(), pj, {}, 0)
            fj = _build_filling_json(row, list(pj.templates.keys())[0], pj, {}, 0)
            # Fix: need to pass correct template name
            template_name = list(pj.templates.keys())[0]
            fj = _build_filling_json(row, template_name, pj, counters_state.copy(), len(results) + 1)
            results.append(fj)

    elif mode == "constant":
        # Use only the first row, repeat for max_docs (default 1)
        if not data_rows:
            return []
        row = data_rows[0]
        template_name = list(pj.templates.keys())[0]
        for i in range(len(rows) - start_row):  # repeat for each logical row
            fj = _build_filling_json(row, template_name, pj, counters_state.copy(), len(results) + 1)
            results.append(fj)

    elif mode == "circular":
        # Cycle through rows, limit by max_docs (not implemented yet, use total rows * 10 as cap)
        max_docs = len(rows) * 10  # arbitrary cap
        for i, row in enumerate(itertools.islice(itertools.cycle(data_rows), max_docs)):
            template_name = list(pj.templates.keys())[0]
            fj = _build_filling_json(row, template_name, pj, counters_state.copy(), len(results) + 1)
            results.append(fj)

    else:
        raise ResolveError("mode", [f"unknown mode: {mode}"])

    return results