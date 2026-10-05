# Задачи: 001-core-tables

> Порядок выполнения — сверху вниз. Каждая задача = коммит (или несколько).

---

## 1. Подготовка

- [ ] 1.1 Добавить `openpyxl` в `pyproject.toml` → `dependencies`
- [ ] 1.2 `uv sync` — обновить окружение и `uv.lock`

---

## 2. Протокол и ошибки

- [ ] 2.1 Создать `src/stanok/tables/protocols.py`
  - [ ] `TableReader` (Protocol с методом `read(path: Path) -> list[dict]`)
  - [ ] Экспорт в `__init__.py`
- [ ] 2.2 Создать `src/stanok/tables/excel.py`
  - [ ] Класс `TableReadError(Exception)` с полями `path`, `cause`
  - [ ] Класс `ExcelReader` implements `TableReader`
  - [ ] Метод `read(self, path: Path) -> list[dict[str, Any]]`

---

## 3. Реализация ExcelReader

- [ ] 3.1 Открытие книги: `openpyxl.load_workbook(path, read_only=True, data_only=True)`
- [ ] 3.2 Получение активного листа: `wb.active`
- [ ] 3.3 Чтение заголовков: первая строка → список строк
- [ ] 3.4 Итерация по строкам (начиная со 2-й), с счётчиком `row_num`:
  - [ ] Пропуск если все ячейки `None`/пустые
  - [ ] Построение `dict`: `{header: normalized_value, "_row_num": row_num}`
  - [ ] `row_num` увеличивается на каждой итерации (включая пропущенные пустые)
- [ ] 3.5 Нормализация значений (`_normalize_cell`):
  - [ ] `None` → `None`
  - [ ] `bool` → `bool`
  - [ ] `int` → `int`
  - [ ] `float` → `float` (если не целое → float)
  - [ ] `datetime.date` / `datetime.datetime` → оставить как есть
  - [ ] `str` → `str.strip()` (пустая строка → `None`)
- [ ] 3.6 Обработка ошибок: `try/except` → `raise TableReadError(path, e) from e`

---

## 4. Экспорты

- [ ] 4.1 `src/stanok/tables/__init__.py`:
  ```python
  from .protocols import TableReader
  from .excel import ExcelReader, TableReadError
  __all__ = ["TableReader", "ExcelReader", "TableReadError"]
  ```

---

## 5. Тесты

- [ ] 5.1 Создать фикстуру `tests/json/001-tables/input.xlsx`:
  - Лист с колонками: `text`, `integer`, `float`, `date`, `bool`, `empty_col`
  - 5 строк данных + 2 пустые + заголовки
- [ ] 5.2 Создать `tests/json/001-tables/expected.json` (эталонный list[dict] **с полем `_row_num`**)
- [ ] 5.3 Создать `tests/tables/test_excel.py`:
  - [ ] `test_read_basic` — нормальный файл
  - [ ] `test_skip_empty_rows` — пустые строки пропущены
  - [ ] `test_row_num_preserved` — `_row_num` равен исходному номеру строки после пропусков
  - [ ] `test_types_preserved` — типы совпадают с эталоном
  - [ ] `test_empty_file` → `[]`
  - [ ] `test_missing_file_raises` → `TableReadError`
  - [ ] `test_corrupted_file_raises` → `TableReadError`
  - [ ] `test_headers_with_spaces` — заголовки с пробелами сохранены

---

## 6. Проверки

- [ ] 6.1 `pytest tests/tables/ -v` — все зелёные
- [ ] 6.2 `pytest tests/ -q` — без регрессий
- [ ] 6.3 `python -m trufflehog3 --no-history . --exclude venv uv.lock` — чисто
- [ ] 6.4 Импорт: `python -c "from stanok.tables import ExcelReader, TableReader, TableReadError; print('OK')"`
- [ ] 6.4 Проверить отсутствие лишних импортов: `grep -r "PyQt5\|stanok.services\|stanok.engine\|stanok.gui" src/stanok/tables/` — пусто

---

## 7. Документация

- [ ] 7.1 Обновить `CHANGELOG.md` в `[Unreleased]` — добавлена фича 001
- [ ] 7.2 (опционально) Добавить строку в `README.md` Структуру — `tables/` уже есть

---

## 8. Git workflow

- [ ] Каждая логическая группа → отдельный коммит
- [ ] Push в `feat/001-core-tables`
- [ ] Создать PR в `develop` (squash merge после CI)