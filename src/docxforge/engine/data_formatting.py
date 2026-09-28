# -*- coding: utf-8 -*-
"""Excel → JSON boundary: read tables once, resolve Filling JSON fields.

Strangler step (003 Phase 2): this module lives *next to* the legacy
Excel-direct path. Nothing here is wired into generate/render yet; the
old reading path keeps working untouched. Downstream code (counters,
tests, render-from-JSON) will consume the resolved JSON data produced
here.
"""

import logging
from typing import Any, Dict, List, Optional

from docxforge.engine.data_reader import DataReader
from docxforge.engine.schema import (
    BatchSourceConfig,
    ResumeState,
    RowIterationMode,
)

logger = logging.getLogger(__name__)


def value_to_str(value: Any) -> str:
    """Coerce one native Excel cell value to a Filling JSON string.

    Contract: ``None`` → ``''``; ``bool``/``int`` → ``str()``;
    integral ``float`` → ``int`` first (``10000.0`` → ``'10000'``);
    ``str`` → stripped; anything else → best-effort ``str()``.
    Broken cells (``str()`` raising) → ``''`` with a warning, never raise.
    """
    if value is None:
        return ''
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value)
    except Exception as e:
        logger.warning('Broken cell value %r coerced to empty string: %s',
                       type(value).__name__, e)
        return ''


def read_table_rows(data_reader: DataReader, path: str,
                    sheet_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read one Excel table into a list of row dicts (native cell types).

    Thin total boundary over :meth:`DataReader.read_excel`: a missing file
    (``FileNotFoundError``) yields ``[]`` with a warning instead of raising,
    mirroring the legacy ``Renderer._read_table_data`` behaviour. Corrupt
    files already yield ``[]`` inside ``DataReader``.
    """
    try:
        return data_reader.read_excel(path, sheet_name)
    except FileNotFoundError as e:
        logger.warning('Table file not found, using empty rows: %s', e)
        return []


def resolve_source_row(rows: List[Dict[str, Any]],
                       mode: Any,
                       doc_index: int = 0,
                       start_offset: int = 0,
                       lookup_column: Optional[str] = None,
                       lookup_value: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Select one row for a document index according to the row mode.

    Mirrors the legacy ``Renderer._resolve_row_for_source`` selection
    semantics without touching it:

    - ``constant``: single lookup row — first row by default, or the row
      whose ``lookup_column`` equals ``lookup_value`` (miss → ``None``).
    - ``sequential``: ``rows[start_offset + doc_index]`` in order,
      exhausted → ``None`` (render must stop, never garbage).
    - ``circular``: ``rows[(start_offset + doc_index) % len(rows)]``.
    - Empty ``rows`` or unknown mode → ``None`` (with a warning).

    Args:
        rows: table rows with native cell types (see :func:`read_table_rows`).
        mode: ``RowIterationMode`` or its string value.
        doc_index: 0-based index of the document being resolved.
        start_offset: resume offset (0-based first row for this run).
        lookup_column: column to search (constant mode only).
        lookup_value: value to find in ``lookup_column`` (constant mode only).
    """
    if not rows:
        return None
    try:
        mode_value = RowIterationMode(mode.value if isinstance(mode, RowIterationMode) else mode)
    except ValueError:
        logger.warning("Unknown batch mode %r; no row selected", mode)
        return None

    if mode_value == RowIterationMode.CONSTANT:
        if lookup_column and lookup_value is not None:
            wanted = str(lookup_value).strip()
            for row in rows:
                if str(row.get(lookup_column, '')).strip() == wanted:
                    return row
            logger.warning("Lookup '%s=%s' missed; no row selected",
                           lookup_column, lookup_value)
            return None
        return rows[0]

    offset = max(0, int(start_offset)) + max(0, int(doc_index))

    if mode_value == RowIterationMode.SEQUENTIAL:
        if offset < len(rows):
            return rows[offset]
        return None

    if mode_value == RowIterationMode.CIRCULAR:
        return rows[offset % len(rows)]

    logger.warning("Unknown batch mode %r; no row selected", mode)
    return None


def resolve_source_row_for_config(rows: List[Dict[str, Any]],
                                  config: BatchSourceConfig,
                                  doc_index: int = 0,
                                  resume: Optional[ResumeState] = None) -> Optional[Dict[str, Any]]:
    """Select one row using a ``BatchSourceConfig`` + ``ResumeState``.

    Computes ``start_offset`` from ``resume.sources`` when the resume
    state says to continue from the last row, then delegates to
    :func:`resolve_source_row`. ``config.file`` is used as the resume key
    (same key the legacy loop uses).
    """
    start_offset = 0
    if resume is not None and resume.continue_from_last:
        try:
            start_offset = int(resume.sources.get(config.file, 0))
        except (TypeError, ValueError) as e:
            logger.warning('Broken resume offset for %r, using 0: %s',
                           config.file, e)
            start_offset = 0
    return resolve_source_row(
        rows, config.mode, doc_index, start_offset,
        lookup_column=config.lookup_column,
        lookup_value=config.lookup_value,
    )
