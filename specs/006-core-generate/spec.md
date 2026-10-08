# Спецификация: 006-core-generate — Оркестрация генерации (end-to-end)

**Статус:** Draft
**Версия:** 0.1.0
**Фаза:** 1 (Core Engine)
**Зависит от:** 003-core-resolve (FillingJSON), 004-core-render (Document), 005-core-storage (ProjectStore)
**FR:** FR-1, FR-3, FR-4, FR-10
**NFR:** NFR-1, NFR-2, NFR-4

---

## 1. Назначение

Единственный модуль, объединяющий все движки в единый пайплайн генерации:
принимает на вход ссылку на проект и параметры запуска → возвращает
список путей к сгенерированным документам. Это единственная точка входа
для CLI и GUI.

---

## 2. Архитектурные решения

### 2.1 Продукт функции

```python
# src/stanok/services/generate.py
def generate_documents(
    project_ref: str | Path,
    *,
    template: str | None = None,
    data_source: str | None = None,
    max_docs: int | None = None,
    resume: bool = False,
) -> GenerateReport:
    """Запустить генерацию документов, вернуть отчёт."""
```

### 2.2 Пайплайн генерации

```
project_ref
    → resolve_project() → (PJ, config_path)
    → load Excel rows (tables.read_excel)
    → resolve_rows(rows, pj, today) → (list[FillingJSON], counters)
    → for each FJ: render(fj, template_path) → Document
    → storage.save_document(doc, fj.dist) → path
    → update PJ: counters, start_row
    → storage.save(pj)  # persist counters/start_row
```

### 2.3 GenerateReport

```python
@dataclass
class GenerateReport:
    created: int              # успешно создано
    skipped: int              # пропущено (пустые строки / ошибки)
    errors: list[tuple[int, str]]  # (row_index, error_msg)
    output_paths: list[Path]  # пути к созданным файлам
    elapsed: float            # секунды
```

---

## 3. Контракты

### 3.1 Входные параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `project_ref` | `str \| Path` | путь к папке проекта или имя конфига в Home |
| `template` | `str \| None` | имя шаблона (если None — первый из PJ) |
| `data_source` | `str \| None` | имя источника данных (если None — первый) |
| `max_docs` | `int \| None` | лимит документов (перекрывает FR-17) |
| `resume` | `bool` | продолжить с `start_row` |

### 3.2 Выходные данные

`GenerateReport` — структура с результатами генерации.

---

## 4. Требования к реализации

| ID | Требование | Приоритет |
|----|------------|-----------|
| GEN-1 | Вызов `resolve_rows` → `render` → `storage.save_document` | Must |
| GEN-2 | Обновление `counters` и `start_row` в PJ после генерации | Must |
| GEN-3 | Атомарное сохранение PJ и документа (или rollback) | Must |
| GEN-4 | Поддержка `max_docs` (лимит на количество документов) | Must |
| GEN-5 | Поддержка `resume` (продолжение с `start_row`) | Must |
| GEN-6 | Обработка ошибок: одна ошибка не ломает весь прогон | Must |
| GEN-7 | `GenerateReport` с полной статистикой | Must |
| GEN-8 | Логирование каждого этапа (DEBUG/INFO) | Must |

---

## 5. Тестирование

Файл: `tests/services/test_generate.py`. Фикстуры: `tests/json/006-generate/`.

| Сценарий | Ожидаемое поведение |
|----------|---------------------|
| Полный прогон sequential | Все документы созданы, PJ обновлён |
| Resume с `start_row > 0` | Генерация продолжается с нужной строки |
| `max_docs` ограничение | Генерация останавливается на лимите |
| Ошибка в одной строке | Остальные обрабатываются, ошибка в отчёте |
| `max_docs=0` | Ничего не генерируется, отчёт пустой |
| Пустой источник данных | Отчёт с `created=0` |

---

## 6. Критерии приёмки

1. `pytest tests/services/test_generate.py -v` — зелёные, покрытие `generate.py` ≥ 90%.
2. `from stanok.services.generate import generate_documents` — работает.
3. End-to-end тест: проект от Excel до `.docx` в `Результат/`.
4. Pre-commit чистый, `pytest tests/ -q` — зелёные.

---

## 7. Риски

| Риск | Митигация |
|------|-----------|
| Ошибка записи документа не откатывает PJ | Транзакция: сохранять PJ только после успешного сохранения всех документов |
| Большие файлы (память) | Потоковая запись, не держать все docx в памяти |
| Конкурентный доступ к PJ | Файловый lock при сохранении PJ |
| Большие Excel файлы | `read_only=True` в `openpyxl` |