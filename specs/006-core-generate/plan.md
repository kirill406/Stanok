# План: 006-core-generate

> Детализация `spec.md` → пошаговые задачи для реализации.

---

## День 1: Зависимости + скелет

### 1.1 Зависимости
```toml
# pyproject.toml
dependencies = [
    "openpyxl>=3.1.0",
    "pydantic>=2,<3",
    "python-docx>=1.2.0",
    "python-dotenv>=1.2.0",
]
```
- `uv sync` → обновить `uv.lock`

### 1.2 Файлы
```
src/stanok/services/
├── __init__.py
├── storage.py       # (готово)
└── generate.py      # NEW
```

---

## День 2: Core generate — оркестрация

### 2.1 `generate.py` — скелет
- `generate_documents(cmd: GenerateCommand) -> GenerateReport`
- Вызов `resolve_rows` → `render` → запись docx в `Результат/` (уникальные имена)
- Обновление PJ: `counters` (`last += created`), `start_row`
- `store.save(pj)` — только после прогона, отката файлов нет

### 2.2 Режимы + лимиты
- `sequential` / `circular` / `constant` через `resolve_rows`
- `max_docs` лимит (если задан) — обрезка списка FJ
- `resume` → `start_row` из PJ / переданный параметр

---

## День 3: Сохранение + ошибки

### 3.1 Сохранение
- Запись docx в `Результат/<dist>` через `doc.save` + `_unique_path` (`(1)`, `(2)`)
- `store.save(pj)` — атомарное сохранение PJ с обновлёнными счётчиками
- PJ не сохраняется при `created=0`; созданные файлы не откатываются

### 3.2 Обработка ошибок
- Одна ошибка → запись в `GenerateReport.errors`, продолжение
- Логирование каждого этапа (DEBUG/INFO)

---

## День 4: Тесты + CI

### 4.1 Фикстуры `tests/json/006-generate/`
- `pj_basic.stanok` — минимальный конфиг
- `pj_circular.stanok` — circular mode
- `pj_counter_month.stanok` — month counter
- Excel-файл + шаблоны

### 4.2 Тесты `tests/services/test_generate.py`
- Полный прогон sequential
- Resume с `start_row > 0`
- `max_docs` ограничение
- Ошибка в одной строке → остальные обрабатываются
- `max_docs=0` → пустой результат
- Пустой источник данных

---

## Definition of Done

- [ ] `pytest tests/services/test_generate.py -v` — зелёные, покрытие ≥ 90%
- [ ] `pytest tests/ -q` — все зелёные
- [ ] Pre-commit чистый
- [ ] `CHANGELOG.md [Unreleased]` — запись о фиче 006
- [ ] PR `feat/006-core-generate` → `develop`