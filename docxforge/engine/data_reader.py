# -*- coding: utf-8 -*-
"""Read Excel files into list-of-dicts format used by the renderer."""

from typing import Dict, List
import openpyxl


class DataReader:
    """Reads Excel data files."""

    def read_excel(self, path: str, sheet_name: str = None) -> List[Dict[str, str]]:
        """Read an Excel file and return list of rows as dicts.

        First row is treated as headers.
        Empty rows and rows with fewer than 2 non-empty cells are skipped.
        """
        wb = openpyxl.load_workbook(path, data_only=True)
        if sheet_name:
            ws = wb[sheet_name]
        else:
            ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        # Find header row (first non-empty row)
        header = None
        data_start = 0
        for i, row in enumerate(rows):
            # Check if this row looks like a header
            non_empty = sum(1 for c in row if c is not None)
            if non_empty >= 1:
                header = [str(c).strip() if c is not None else f'col_{j}'
                          for j, c in enumerate(row)]
                data_start = i + 1
                break

        if header is None:
            return []

        result = []
        for row in rows[data_start:]:
            values = {}
            empty_count = 0
            for j, val in enumerate(row):
                if j < len(header):
                    if val is None:
                        values[header[j]] = ''
                        empty_count += 1
                    else:
                        values[header[j]] = str(val).strip()
            # Skip completely empty rows
            if empty_count < len(header):
                result.append(values)

        wb.close()
        return result

    def get_columns(self, path: str, sheet_name: str = None) -> List[str]:
        """Get list of column names from an Excel file."""
        wb = openpyxl.load_workbook(path, data_only=True)
        if sheet_name:
            ws = wb[sheet_name]
        else:
            ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        for row in rows:
            non_empty = sum(1 for c in row if c is not None)
            if non_empty >= 1:
                cols = [str(c).strip() if c is not None else '' for c in row]
                wb.close()
                return cols

        wb.close()
        return []

    def get_distinct_values(self, path: str, column: str,
                             sheet_name: str = None) -> List[str]:
        """Get distinct values from a column for dropdown lists."""
        data = self.read_excel(path, sheet_name)
        seen = set()
        result = []
        for row in data:
            val = row.get(column, '')
            if val and val not in seen:
                seen.add(val)
                result.append(val)
        return result
