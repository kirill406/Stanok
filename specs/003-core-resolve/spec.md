# Спецификация: 003-core-resolve — Строки Excel + PJ → Filling JSON

**Статус:** Draft
**Версия:** 0.1.0
**Фаза:** 1 (Core Engine)
**Зависит от:** 001-core-tables (ExcelReader), 002-core-schema (PJ/AJ/FJ модели)
**FR:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-7, FR-10, FR-13
**NFR:** NFR-4

---

## 1. Назначение

Единственный модуль, где происходит **сборка Filling JSON**: берёт сырые строки из ExcelReader (`list[dict]`) + конфиг проекта (PJ) → строит `list[FillingJSON]` для рендера. Здесь и только здесь происходит логика выбора значений по `FieldSource` (CONSTANT/TABLE/COUNTER/TODAY), применение режимов строк, счётчиков и дат.

---

## 2. Архитектурные решения

### 2.1 Продукт функции

```python
# src/stanok/engine/resolve.py
def resolve_rows(rows: list[dict], pj: ProjectJSON) -> list[FillingJSON]:
    """Строит Filling JSON для каждой строки данных."""
```

- На входе: `rows: list[dict[str, Any]]` — уже валидированные строки от `ExcelReader.read()` (все строки, пустые с `None`).
- На выходе: `list[FillingJSON]` — готовые к рендеру объекты (включая `dist`).
- Пустые строки: **не пропускаются**, для них строятся FJ с пустыми `fields` (value = None для table-полей) — рендер решит, что делать (обычно: пропуск или предупреждение).

### 2.2 Контракты источников данных

| Источник | PJ поле | FJ поле | Ожидаемое значение в строке | Режим |
|----------|---------|---------|----------------------------|-------|
| constant | `FieldDef(source=CONSTANT, value=...)` | `fields[name]` | `value` из PJ | — |
| table    | `FieldDef(source=TABLE, value="col")` | `fields[name]` | `row.get("col")` | — |
| counter  | `FieldDef(source=COUNTER, value="name")` | `fields[name]` | `counters[name].last + 1` | sequential/month |
| today    | `FieldDef(source=TODAY, value=None)` | `fields[name]` | `date.today()` | — |
| image    | **out of scope** | — | — | — |

### 2.3 Режимы обхода строк (FR-4)

| Режим | Поведение |
|-------|-----------|
| `sequential` | По порядку, от `start_row` до конца. После конца — стоп. |
| `circular` | По порядку, после конца — снова с начала (цикл), пока не сгенерировано N docs (лимит из PJ или CLI). |
| `constant` | Всегда первая строка данных (индекс `start_row`), повторяется N раз. |

### 2.4 Продолжение (Resume) — FR-5

- В `DataSourceDef` поле `start_row: int = 0`:
  - `0` — с начала (после заголовка).
  - `> 0` — продолжить с этой строки (0-based относительно первой строки данных).
- После генерации `start_row` обновляется в PJ (переписывается файл конфига).
- `resume` не хранится в FJ (см. спеку 002).

### 2.5 Циклы таблиц в шаблоне (FR-13)

Шаблон может содержать блок `{{#each rows}}...{{/each}}` (или синтаксис `xmlops`). `resolve` не занимается этим — он выдаёт **плоский список FJ** (по одному на документ). Циклы внутри шаблона обрабатываются `xmlops` на этапе рендера.

---

## 3. Контракты

### 3.1 Вход: `rows` (от ExcelReader)

```python
list[dict[str, Any]]  # каждая строка имеет все колонки заголовка, пустые = None
```

### 3.2 Вход: `ProjectJSON` (PJ)

Конфиг из спеки 002: `templates`, `data_sources`, `counters`, `filename_template`.

### 3.3 Выход: `list[FillingJSON]`

```python
class FillingJSON:
    version: str              # == PJ.version
    template: str             # ключ из pj.templates
    fields: dict[str, Any]    # разрешенные {поле: значение}
    dist: str                 # resolved filename_template + поля
```

---

## 4. Требования к реализации

| ID | Требование | Приоритет |
|----|------------|-----------|
| RES-1 | Построение `fields` по `FieldSource` (CONSTANT/TABLE/COUNTER/TODAY) | Must |
| RES-2 | Поддержка режимов строк: sequential/circular/constant | Must |
| RES-3 | Счётчики: инкремент `last` в PJ после каждого использования | Must |
| RES-4 | Режим month для счётчиков: формат `YYYY-MM-###` | Must |
| RES-5 | Resume: `start_row` обновляется в PJ после генерации | Must |
| RES-6 | `filename_template` → `dist` (resolve плейсхолдеров из `fields`) | Must |
| RES-7 | Пустые строки: FJ с пустыми полями (`None`), не пропуск | Must |
| RES-8 | Ошибки: `ResolveError(path, errors)` — невалидный PJ, нет колонки, переполнение счётчика | Must |
| RES-9 | Не зависит от Qt/gui/services (чистый engine) | Must |
| RES-10 | Покрытие тестами ≥ 90% | Must |

---

## 5. Тестирование

Файл: `tests/engine/test_resolve.py`. Фикстуры: `tests/json/003-resolve/`.

| Сценарий | Ожидаемое поведение |
|----------|---------------------|
| Constant + Table + Counter + Today | Все типы поля резолвятся правильно |
| Sequential mode | Идёт по порядку, стоп в конце |
| Circular mode | Циклится, стоп по лимиту docs |
| Constant mode | Повторяет первую строку N раз |
| Resume (`start_row > 0`) | Начинает с нужной строки, `start_row` обновляется |
| Counter month format | Формат `YYYY-MM-###` (например `2026-10-001`) |
| Counter overflow | Ошибка при переполнении (999 → ошибка) |
| Missing column in table | Ошибка с путём к полю |
| `filename_template` resolve | Плейсхолдеры заменяются на значения из `fields` |
| Пустая строка | FJ с `fields = {k: None}` |

---

## 6. Критерии приёмки

1. `pytest tests/engine/test_resolve.py -v` — зелёные, покрытие `resolve.py` ≥ 90%.
2. `from stanok.engine.resolve import resolve_rows` — работает.
3. Ошибки `ResolveError` с путём к полю.
31. `from stanok.engine import resolve` — нет импортов Qt/Gui/Services.
4. Pre-commit чистый, `pytest tests/ -q` — зелёные.

---

## 9. Риски

| Риск | Митигация |
|------|-----------|
| Счётчики: race condition при параллельных запусках | Однопользовательский офлайн — не актуально. Если понадобится — файловый лок. |
| Переполнение month-счётчика (999) | Ошибка с понятным сообщением, ручной сброс в PJ. |
| `filename_template` с несуществующим плейсхолдером | Ошибка resolve с путём к плейсхолдеру. |