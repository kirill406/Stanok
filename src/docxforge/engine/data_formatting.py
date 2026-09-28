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
