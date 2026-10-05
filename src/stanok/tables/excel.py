# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Excel table reading implementation."""

from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl


class TableReadError(Exception):
    def __init__(self, path: Path, cause: Exception):
        self.path = path
        self.cause = cause
        super().__init__(f"Не удалось прочитать таблицу {path}: {cause}")


class ExcelReader:
    def read(self, path: Path) -> list[dict[str, Any]]:
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            rows = ws.iter_rows(values_only=True)
            headers = [str(h).strip() if h is not None else "" for h in next(rows)]
            result = []
            for row in rows:
                if all(v is None or v == "" for v in row):
                    # Пустая строка — dict с None значениями
                    result.append({h: None for h in headers})
                    continue
                row_dict = {h: self._normalize(v) for h, v in zip(headers, row)}
                result.append(row_dict)
            return result
        except Exception as e:
            raise TableReadError(path, e)

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