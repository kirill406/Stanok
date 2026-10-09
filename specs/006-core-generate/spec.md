# Спецификация: 006-core-generate — Оркестрация генерации (end-to-end)

**Статус:** Active
**Версия:** 0.2.0
**Фаза:** 1 (Core Engine)
**Зависит от:** 003-core-resolve (FillingJSON), 004-core-render (Document), 005-core-storage (ProjectStore)
**FR:** FR-1, FR-3, FR-4, FR-10
**NFR:** NFR-4, NFR-5

---

## 1. Назначение

Единственный модуль, объединяющий движки в пайплайн генерации:
принимает команду с ссылкой на проект и параметрами запуска → возвращает
отчёт со списком созданных документов. Единственная точка входа для CLI и GUI.

```
Excel + PJ → resolve → FillingJSON → render → docx → Результат/
```

---

## 2. Архитектурные решения

### 2.1 Продукт функции

```python
# src/stanok/services/generate.py
@dataclass(frozen=True)
class GenerateCommand:
    project_ref: str | Path   # путь к папке проекта или имя конфига в Home
    template: str | None = None      # имя шаблона (None — первый из PJ)
    data_source: str | None = None   # имя источника (None — первый)
    max_docs: int | None = None      # лимит документов на прогон
    resume: bool = False             # продолжить с сохранённого start_row


@dataclass
class GenerateReport:
    created: int                     # успешно создано
    skipped: int                     # пропущено (пустые строки)
    errors: list[tuple[int, str]]    # (row_index, error_msg)
    output_paths: list[Path]         # пути к созданным файлам
    elapsed: float                   # секунды


def generate_documents(cmd: GenerateCommand) -> GenerateReport:
    """Запустить генерацию документов, вернуть отчёт."""
```

### 2.2 Пайплайн

```
cmd.project_ref
    → resolve_project() → (PJ, config_path)
    → read_excel(источник) → rows
    → resolve_rows(rows, pj, today) → (fillings, counters)
    → truncate fillings[:max_docs]
    → for each FJ: render(fj, template_path) → Document
    → doc.save(Результат/<dist> с уникальным именем)
    → update PJ: counters (last += created), start_row
    → store.save(pj)  # только после прогона
```

Выходной каталог — `<папка проекта>/Результат/` (создаётся при отсутствии).
Коллизия имени — суффиксы `(1)`, `(2)` по правилу FR-11 (`spec.md` §5.3):
существующий файл не трогаем. Хелпер `_unique_path()` — приватный,
покрыт тестами (вынос в `storage` — при рефакторинге, не в этой фиче).

### 2.3 Ошибки: fail-fast против построчных

Fail-fast (весь прогон прерывается, исключение наружу):

| Ошибка | Тип |
|--------|-----|
| Проект не найден | `StorageError` из `resolve_project` |
| Шаблон не найден / битый | `TemplateError` (новый, `services/generate.py`) |
| Пустой список шаблонов / источников в PJ | `TemplateError` / `ValueError` |

Построчные (попадают в `report.errors`, прогон продолжается):

| Этап | Причина |
|------|---------|
| `render(fj, ...)` | `RenderError` движка и др. |
| `doc.save(...)` | `OSError` записи |

Пустой источник данных (0 строк) — не ошибка: отчёт с `created=0`,
PJ не сохраняется. `max_docs=0` — то же самое.

### 2.4 Счётчики и resume (правило 2 из `spec.md` §5.2)

- `last += created` — только за фактически созданные документы.
- `start_row` — индекс первой необработанной строки после прогона.
- `resume=True` → старт с сохранённого `PJ.start_row`;
  `resume=False` → старт с `data_source.start_row` (обычно 0).
- PJ сохраняется только после завершения прогона, даже при частичных
  ошибках (созданные файлы остаются, ошибки — в отчёте, отката файлов нет).

### 2.5 Логирование (NFR-5)

Каждый этап — `logger.info` (старт/итог), детали — `DEBUG`;
каждый `except` — уровень по смыслу + `exc_info=True` в f-строке.
Строки пользователю — русские; централизация через `gui.strings` — в 007
(здесь — прямые строки с пометкой `# TODO(007)`).

---

## 3. Контракты

### 3.1 Вход: `GenerateCommand`

| Поле | Тип | Описание |
|------|-----|----------|
| `project_ref` | `str \| Path` | путь к папке проекта или имя конфига в Home |
| `template` | `str \| None` | имя шаблона (None — первый из PJ) |
| `data_source` | `str \| None` | имя источника (None — первый) |
| `max_docs` | `int \| None` | лимит документов (авто-лимиты FR-17 — в 017) |
| `resume` | `bool` | продолжить с сохранённого `start_row` |

### 3.2 Выход: `GenerateReport` (§2.1)

---

## 4. Требования к реализации

| ID | Требование | Приоритет |
|----|------------|-----------|
| GEN-1 | Вызов `resolve_rows` → `render` → запись docx в `Результат/` | Must |
| GEN-2 | Обновление `counters` (`last += created`) и `start_row` в PJ | Must |
| GEN-3 | `store.save(pj)` только после прогона; созданные файлы не откатываются | Must |
| GEN-4 | `max_docs`: обрезка списка Filling до лимита | Must |
| GEN-5 | `resume`: старт с сохранённого `start_row` | Must |
| GEN-6 | Построчная ошибка → запись в `report.errors`, прогон продолжается | Must |
| GEN-7 | `GenerateReport` с полной статистикой и `elapsed` | Must |
| GEN-8 | Уникальные имена `(1)`, `(2)`; чужой файл не трогаем | Must |
| GEN-9 | Логирование каждого этапа (DEBUG/INFO, `exc_info=True`) | Must |

---

## 5. Тестирование

Юнит: `tests/services/test_generate.py`. Фикстуры: `tests/json/006-generate/`.
Сквозной: `tests/integration/test_generate_e2e.py` (Excel → docx в `Результат/`).

| Сценарий | Ожидаемое поведение |
|----------|---------------------|
| Полный прогон sequential | Все документы созданы, PJ обновлён (counters, start_row) |
| Resume с `start_row > 0` | Генерация продолжается с нужной строки |
| `max_docs` ограничение | Создано ровно `max_docs`, `start_row` сдвинут |
| Ошибка в одной строке | Остальные созданы, ошибка в `report.errors` |
| `max_docs=0` | `created=0`, PJ не сохраняется |
| Пустой источник данных | `created=0`, без исключений |
| Коллизия имени в `Результат/` | Новый файл с суффиксом `(1)`, старый цел |
| E2E: Excel → docx | docx открывается, плейсхолдеры подставлены |

---

## 6. Критерии приёмки

1. `pytest tests/services/test_generate.py tests/integration/test_generate_e2e.py -v` — зелёные, покрытие `generate.py` ≥ 90%.
2. `from stanok.services.generate import generate_documents, GenerateCommand` — работает.
3. MVP: `python run.py <папка тестового проекта>` → docx в `Результат/`, код возврата 0.
4. Pre-commit чистый, `pytest tests/ -q` — зелёные.

---

## 7. Риски

| Риск | Митигация |
|------|-----------|
| Падение записи PJ теряет counters | PJ пишется последним, только после документов (§2.4) |
| Большие Excel/docx в памяти | `read_only=True` в `openpyxl`; Document сохраняется сразу, не копится |
| Конкурентный доступ к PJ | `ProjectStore` сериализует через `threading.Lock` (005) |
| Batch-режимы сверх одного круга | В этой фиче — один проход; циклы/повторы — 012 |
