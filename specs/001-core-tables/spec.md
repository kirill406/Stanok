# Спецификация: 001-core-tables — Чтение Excel

**Статус:** Draft
**Версия:** 0.1.0
**Фаза:** 1 (Core Engine)
**Зависит от:** —
**FR:** FR-1, FR-2, FR-7
**NFR:** NFR-1, NFR-4

---

## 1. Назначение

Единственное место в кодовой базе, где происходит чтение Excel-файлов.
Остальные слои (resolve, generate) работают только с plain Python структурами
`list[dict]` — сырые строки таблиц.

---

## 2. Архитектурные решения

### 2.1 Протокол чтения таблиц

```python
# src/stanok/tables/protocols.py
from typing import Protocol, Iterable

class TableReader(Protocol):
    def read(self, path: Path) -> list[dict[str, Any]]:
        """Читает Excel, возвращает список строк.
        Каждая строка — dict: {имя_столбца: значение}.
        Первая строка файла — заголовки.
        Пустые строки пропускаются.
        """
```

### 2.2 Реализация ExcelReader

- Библиотека: `openpyxl` (уже в dev-зависимостях через trufflehog3/pyyaml, добавить явно)
- Чтение только первого листа (`active sheet`)
- Первая строка = заголовки; остальные — данные
- Пустые строки (все ячейки `None`/пустые) — пропуск, но `_row_num` считается от исходной позиции
- Каждая строка возвращается как `dict` с добавленным полем `_row_num` (int, 1-based, номер строки в исходном Excel)
- Типы значений: `str`, `int`, `float`, `date`, `datetime`, `bool`, `None`
- Даты/время: `openpyxl` возвращает `datetime` — оставляем как есть
- Числа: `int` если целое, иначе `float`
- Булевы: ячейки с `TRUE`/`FALSE` → `bool`
- Ошибки чтения: оборачиваем в `TableReadError(path, cause)`

---

## 3. Контракты

### 3.1 Входные данные

| Параметр | Тип | Описание |
|----------|-----|----------|
| `path` | `Path` | Путь к `.xlsx` файлу |

### 3.2 Выходные данные

```python
list[dict[str, Any]]
# Пример:
[
    {"_row_num": 1, "ФИО": "Иванов Иван", "Возраст": 30, "Дата_рождения": date(1994, 5, 12), "Активен": True},
    {"_row_num": 2, "ФИО": "Петров Петр", "Возраст": 25, "Дата_рождения": date(1999, 8, 3), "Активен": False},
]
```

- Поле **`_row_num`** (int) — исходный номер строки в Excel (1-based, заголовок = строка 1, данные с 2).
- Префикс `_` — резервный namespace, не конфликтует с пользовательскими колонками.
- Порядок в списке = порядок строк в Excel (пустые пропущены, `_row_num` отражает исходную позицию).

### 3.3 Ошибки

```python
class TableReadError(Exception):
    def __init__(self, path: Path, cause: Exception):
        self.path = path
        self.cause = cause
        super().__init__(f"Не удалось прочитать таблицу {path}: {cause}")
```

---

## 4. Требования к реализации

| ID | Требование | Приоритет |
|----|------------|-----------|
| TBL-1 | Читать `.xlsx` через `openpyxl` | Must |
| TBL-2 | Возвращать `list[dict]` с заголовками из первой строки | Must |
| TBL-3 | Добавлять поле `_row_num` (int, 1-based) в каждый dict | Must |
| TBL-4 | Пропускать полностью пустые строки | Must |
| TBL-5 | Сохранять типы: `int`, `float`, `date`, `datetime`, `bool`, `str`, `None` | Must |
| TBL-6 | Ошибки оборачивать в `TableReadError` с путем и причиной | Must |
| TBL-7 | Не зависеть от других слоёв (чистый Python, без Qt, без services) | Must |
| TBL-8 | Покрытие тестами ≥ 90% | Must |

---

## 5. Тестирование

### 5.1 Юнит-тесты

Файл: `tests/tables/test_excel.py`

| Сценарий | Ожидаемое поведение |
|----------|---------------------|
| Нормальный файл с разными типами | Возвращает `list[dict]` с правильными типами и `_row_num` |
| Пустые строки в середине/конце | Пропущены, не в результате; `_row_num` следующей строки = исходный номер |
| Заголовки с пробелами/спецсимволами | Сохранены как есть (ключи dict) |
| Пустой файл (только заголовки) | `[]` |
| Несуществующий файл | `TableReadError` |
| Повреждённый xlsx | `TableReadError` |
| Лист с объединёнными ячейками | Значение в левой верхней ячейке |
| Проверка `_row_num` | После пропуска пустых строк `_row_num` = исходный номер строки в Excel |

### 5.2 Фикстуры

Папка: `tests/json/001-tables/`

| Файл | Содержимое |
|------|------------|
| `input.xlsx` | Тестовый Excel с разными типами, пустыми строками, датами |
| `expected.json` | Эталонный `list[dict]` **с полем `_row_num`** для сравнения |

Тест: `read_excel(fixture_path) == expected_json`

---

## 6. Файловая структура

```
src/stanok/
├── tables/
│   ├── __init__.py          # экспорт: TableReader, ExcelReader, TableReadError
│   ├── protocols.py         # Protocol TableReader
│   └── excel.py             # ExcelReader implementation
tests/
├── tables/
│   └── test_excel.py
└── json/
    └── 001-tables/
        ├── input.xlsx
        └── expected.json
```

---

## 7. План задач (tasks.md)

- [ ] Создать `src/stanok/tables/protocols.py` с `TableReader`
- [ ] Создать `src/stanok/tables/excel.py` с `ExcelReader` и `TableReadError`
- [ ] Обновить `src/stanok/tables/__init__.py` (экспорт)
- [ ] Добавить `openpyxl` в `pyproject.toml` dependencies
- [ ] Создать фикстуру `tests/json/001-tables/input.xlsx`
- [ ] Создать `tests/json/001-tables/expected.json`
- [ ] Написать `tests/tables/test_excel.py`
- [ ] Проверить: `pytest tests/tables/ -v` — зелёные
- [ ] Проверить: `pytest tests/ -q` — всё проходит
- [ ] Проверить: pre-commit hook проходит

---

## 8. Критерии приёмки

1. `pytest tests/tables/ -v` — все тесты проходят
2. `pytest tests/ -q` — никаких регрессий
3. `python -m trufflehog3 --no-history . --exclude venv uv.lock` — чисто
4. Импорт `from stanok.tables import ExcelReader, TableReader, TableReadError` работает
5. Код не импортирует Qt, services, engine — только stdlib + openpyxl

---

## 9. Риски и ограничения

| Риск | Митигация |
|------|-----------|
| `openpyxl` медленный на больших файлах | P0 — файлы до ~10к строк; позже — streaming/chunked |
| Разные версии Excel (.xls, .xlsm) | P0 — только `.xlsx`; остальное — later |
| Кодировки/локали | `openpyxl` работает с Unicode нативно |