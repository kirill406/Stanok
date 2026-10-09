# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Excel table reading implementation."""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import get_column_letter

from ..gui.strings import STRINGS

logger = logging.getLogger(__name__)


class TableReadError(Exception):
    def __init__(self, path: Path, cause: Exception):
        self.path = path
        self.cause = cause
        super().__init__(STRINGS.TBL_READ_FAILED.format(path=path, cause=cause))


class ExcelReader:
    def read(self, path: Path) -> list[dict[str, Any]]:
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                ws = wb.active
                rows = ws.iter_rows(values_only=True)
                headers = self._read_headers(path, next(rows, []))
                width = len(headers)
                result = []
                for row in rows:
                    cells = list(row[:width]) + [None] * max(0, width - len(row))
                    if all(v is None or v == "" for v in cells):
                        # Пустая строка — dict с None значениями
                        result.append({h: None for h in headers})
                        continue
                    result.append({h: self._normalize(v) for h, v in zip(headers, cells)})
                return result
            finally:
                wb.close()
        except TableReadError:
            raise
        except Exception as e:
            logger.error(f"read table {path}: {e}", exc_info=True)
            raise TableReadError(path, e) from e

    @staticmethod
    def _read_headers(path: Path, raw_row: tuple) -> list[str]:
        raw = [str(h).strip() if h is not None else "" for h in raw_row]
        # Хвостовые пустые колонки — обрезать (обычное дело в живых файлах).
        last = max((i for i, h in enumerate(raw) if h), default=-1)
        if last < 0:
            raise TableReadError(path, ValueError(STRINGS.TBL_NO_HEADERS))
        headers = raw[: last + 1]
        # Пустой заголовок в середине — колонку нельзя адресовать.
        for i, h in enumerate(headers):
            if not h:
                raise TableReadError(
                    path,
                    ValueError(STRINGS.TBL_BLANK_HEADER.format(column=get_column_letter(i + 1))),
                )
        # Дубли — тихая потеря данных, запрещены.
        seen, dups = set(), set()
        for h in headers:
            if h in seen:
                dups.add(h)
            seen.add(h)
        if dups:
            raise TableReadError(
                path,
                ValueError(STRINGS.TBL_DUP_HEADERS.format(headers=", ".join(sorted(dups)))),
            )
        return headers

    def _normalize(self, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v) if v.is_integer() else v
        if isinstance(v, (datetime, date)):
            return v
        s = str(v).strip()
        return s if s else None
