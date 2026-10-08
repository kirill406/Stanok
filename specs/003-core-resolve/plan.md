# Задачи: 003-core-resolve

> Порядок выполнения — сверху вниз. Каждая группа → коммит.

---

## 1. Подготовка

- [ ] 1.1 Файл `src/stanok/engine/resolve.py` — скелет + импорты
- [ ] 1.2 Обновить `src/stanok/engine/__init__.py` — экспорт `resolve_rows`, `ResolveError`

---

## 2. Core resolve — построение FillingJSON

- [ ] 2.1 Функция `resolve_rows(rows, pj, today=None) -> tuple[list[FillingJSON], dict]` (PJ не мутируется)
- [ ] 2.2 Внутренняя функция: `build_fj(row, template, pj, counters_state) -> FillingJSON`
  - [ ] CONSTANT: взять `value` из PJ
  - [ ] TABLE: `row.get(column_name)` → если нет колонки → `ResolveError`
  - [ ] COUNTER: инкремент `pj.counters[name].last`, формат `plain` / `month`
  - [ ] TODAY: `datetime.date.today()`
- [ ] 2.3 Пустые строки: FJ с `fields = {name: None for name in template.fields}`

---

## 3. Режимы обхода строк + Resume

- [ ] 3.1 `sequential`: `rows[start_row:]` → стоп в конце
- [ ] 3.2 `circular`: цикл, `itertools.cycle`, лимит `max_docs` (из PJ или дефолт)
- [ ] 3.3 `constant`: повтор `rows[start_row]` N раз
- [ ] 3.4 Resume: после генерации `pj.data_sources[i].start_row += processed` (sequential/circular)
- [ ] 3.4 `constant`: `start_row` не меняется
- [ ] 3.5 Запись обновлённого PJ в файл (через `services.storage` или отдельная функция)

---

## 4. Счётчики

- [ ] 4.1 `plain`: `last += 1`, формат `str(last)`
- [ ] 4.2 `month`: формат `YYYY-MM-###` (например `2026-10-001`)
  - [ ] Сброс `###` при смене месяца (на основе `datetime.now().month`)
  - [ ] Переполнение при `> 999` → `ResolveError("counter overflow")`
- [ ] 4.3 Инкремент `pj.counters[name].last` после каждого использования

---

## 5. `filename_template` → `dist`

- [ ] 5.1 Плейсхолдеры: `{field}`, `{i}` (индекс doc 1-based), `{template}`
- [ ] 5.2 Неизвестный плейсхолдер → `ResolveError("dist", [...])`
- [ ] 5.3 Результат в `FillingJSON.dist`

---

## 6. Ошибки

- [ ] 6.1 Класс `ResolveError(SchemaError)` с `path`, `errors`
- [ ] 6.2 Отсутствующая колонка → `ResolveError("fields.ФИО", ["column 'ФИО' not found"])`
- [ ] 6.2 Переполнение счётчика (> 999 для month) → `ResolveError("counters.doc_num", ["counter overflow"])`
- [ ] 6.3 Неизвестный плейсхолдер в `filename_template` → `ResolveError("dist", ["unknown placeholder {unknown}"])`
- [ ] 6.4 Все ошибки логгируются `logger.error(f"resolve: {e}", exc_info=True)`

---

## 7. Тесты `tests/engine/test_resolve.py`

- [ ] 7.1 `test_constant_table_counter_today`
- [ ] 7.2 `test_mode_sequential`
- [ ] 7.3 `test_mode_circular`
- [ ] 7.4 `test_mode_constant`
- [ ] 7.5 `test_resume_sequential`
- [ ] 7.5 `test_counter_plain`
- [ ] 7.6 `test_counter_month_format`
- [ ] 7.6 `test_counter_month_overflow`
- [ ] 7.7 `test_missing_column`
- [ ] 7.8 `test_filename_template_unknown_placeholder`
- [ ] 7.8 `test_empty_row_included`

---

## 7. Фикстуры `tests/json/003-resolve/`

- [ ] `pj_basic.stanok` — 1 шаблон, 1 источник, 1 счётчик
- [ ] `pj_circular.stanok` — circular mode
- [ ] `pj_counter_month.stanok` — month counter
- [ ] 5 строк Excel + 1 пустая

---

## 7. Проверки и CI

- [ ] `pytest tests/engine/test_resolve.py -v` — зелёные, покрытие ≥ 90%
- [ ] `pytest tests/ -q` — без регрессий
- [ ] Pre-commit чистый
- [ ] `CHANGELOG.md [Unreleased]` — запись о фиче 003
- [ ] PR `feat/003-core-resolve` → `develop`

---

## Definition of Done (критерии §6)

1. `pytest tests/engine/test_resolve.py -v` — зелёные, покрытие `resolve.py` ≥ 90%
2. `from stanok.engine.resolve import resolve_rows` — работает
3. Ошибки `ResolveError` с путём к полю
4. `from stanok.engine import resolve` — нет импортов Qt/Gui/Services
5. Pre-commit чистый, `pytest tests/ -q` — зелёные