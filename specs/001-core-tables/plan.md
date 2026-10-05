# План: 001-core-tables

> Детализация `spec.md` → пошаговые задачи для реализации.
> Каждый пункт → коммит (или несколько мелких).

---

## День 1: Скелет + openpyxl

### 1.1 Зависимость
```toml
# pyproject.toml
dependencies = [
    "openpyxl>=3.1.0",
    # ...
]
```
- `uv sync` → обновить `uv.lock`

### 1.2 Файлы протокола
```
src/stanok/tables/
├── __init__.py
├── protocols.py    # NEW
├── excel.py        # NEW
```

**protocols.py:**
```python
from typing import Protocol, Any
from pathlib import Path

class TableReader(Protocol):
    def read(self, path: Path) -> list[dict[str, Any]]:
        """Читает таблицу, возвращает список строк (dict: колонка -> значение)."""
```

---

## День 2: ExcelReader — реализация

### 2.1 excel.py — каркас
```python
class TableReadError(Exception):
    def __init__(self, path: Path, cause: Exception):
        self.path = path
        self.cause = cause
        super().__init__(f"Не удалось прочитать таблицу {path}: {cause}")

class ExcelReader:
    def read(self, path: Path) -> list[dict[str, Any]]:
        ...
```

### 2.2 Реализация read()
```python
def read(self, path: Path) -> list[dict[str, Any]]:
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        headers = [str(h).strip() for h in next(rows)]
        result = []
        row_num = 1  # заголовок = 1
        for row in rows:
            row_num += 1
            if all(v is None or v == "" for v in row):
                continue
            row_dict = {h: self._normalize(v) for h, v in zip(headers, row)}
            row_dict["_row_num"] = row_num
            result.append(row_dict)
        return result
    except Exception as e:
        raise TableReadError(path, e) from e
```

### 2.3 Нормализация значений
```python
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
```

---

## День 3: Тесты + фикстуры

### 3.1 Фикстура input.xlsx
Создать `tests/json/001-tables/input.xlsx` (через скрипт или вручную):

| text | integer | float | date | bool | empty_col |
|------|---------|-------|------|------|-----------|
| "А" | 1 | 1.5 | 2024-01-15 | TRUE | |
| "Б" | 2 | 2.7 | 2024-02-20 | FALSE | x |
| "В" | 3 | 3.0 | 2024-03-10 | TRUE | |
| (пусто) | | | | | |
| "Д" | 4 | 4.2 | 2024-04-05 | FALSE | |

### 3.2 expected.json
```json
[
  {"_row_num": 2, "text": "А", "integer": 1, "float": 1.5, "date": "2024-01-15", "bool": true, "empty_col": null},
  {"_row_num": 3, "text": "Б", "integer": 2, "float": 2.7, "date": "2024-02-20", "bool": false, "empty_col": "x"},
  {"_row_num": 4, "text": "В", "integer": 3, "float": 3.0, "date": "2024-03-10", "bool": true, "empty_col": null},
  {"_row_num": 6, "text": "Д", "integer": 4, "float": 4.2, "date": "2024-04-05", "bool": false, "empty_col": null}
]
```

### 3.3 Тесты
```python
def test_read_basic():
    reader = ExcelReader()
    result = reader.read(Path("tests/json/001-tables/input.xlsx"))
    with open("tests/json/001-tables/expected.json") as f:
        expected = json.load(f)
    assert result == expected

def test_skip_empty_rows():
    reader = ExcelReader()
    result = reader.read(Path("tests/json/001-tables/input.xlsx"))
    assert len(result) == 4  # 4 data rows, 1 empty skipped

def test_row_num_preserved():
    reader = ExcelReader()
    result = reader.read(Path("tests/json/001-tables/input.xlsx"))
    assert [r["_row_num"] for r in result] == [2, 3, 4, 6]  # row 5 was empty

def test_types_preserved():
    reader = ExcelReader()
    result = reader.read(Path("tests/json/001-tables/input.xlsx"))
    assert isinstance(result[0]["integer"], int)
    assert isinstance(result[0]["float"], float)
    assert isinstance(result[0]["date"], date)

def test_missing_file_raises():
    with pytest.raises(TableReadError):
        ExcelReader().read(Path("none.xlsx"))
```

---

## День 4: Интеграция + CI

### 4.1 Экспорты
```python
# src/stanok/tables/__init__.py
from .protocols import TableReader
from .excel import ExcelReader, TableReadError

__all__ = ["TableReader", "ExcelReader", "TableReadError"]
```

### 4.2 Проверки
```bash
pytest tests/tables/ -v
pytest tests/ -q
python -m trufflehog3 --no-history . --exclude venv uv.lock
python -c "from stanok.tables import ExcelReader, TableReader, TableReadError; print('OK')"
```

### 4.3 CHANGELOG
```markdown
## [Unreleased]
### Added
- feat(001-core-tables): Excel reading via openpyxl (TableReader protocol, ExcelReader)
```

---

## Definition of Done

- [ ] `pytest tests/tables/ -v` — 100% pass
- [ ] `pytest tests/ -q` — no regressions
- [ ] `python -m trufflehog3 ...` — clean
- [ ] `from stanok.tables import ExcelReader, TableReader, TableReadError` — OK
- [ ] No Qt/services/engine imports in tables/
- [ ] CHANGELOG updated
- [ ] PR opened → squash merge to develop