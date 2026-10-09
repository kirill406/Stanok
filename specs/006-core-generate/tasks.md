# Задачи: 006-core-generate

> Порядок выполнения — сверху вниз. Каждая группа → коммит.

---

## 1. Подготовка

- [ ] 1.1 Файл `src/stanok/services/generate.py` — скелет + импорты
- [ ] 1.2 Обновить `src/stanok/services/__init__.py` — экспорт `generate_documents`, `GenerateReport`

---

## 2. Core generate — оркестрация

- [ ] 2.1 Функция `generate_documents(cmd)` → `GenerateReport`, `GenerateCommand`
- [ ] 2.2 Внутренняя функция: обработка одного FJ → render → save
- [ ] 2.3 Вызов `resolve_rows` → `render` → запись docx в `Результат/`
- [ ] 2.4 Обновление PJ: `counters` (`last += created`), `start_row`
- [ ] 2.5 `store.save(pj)` только после прогона; `_unique_path` для коллизий

---

## 3. Режимы обхода + лимиты

- [ ] 3.1 `sequential` — через `resolve_rows` mode=sequential
- [ ] 3.2 `circular` — один круг (до FR-17)
- [ ] 3.3 `constant` — повтор первой строки
- [ ] 3.4 `max_docs` лимит (обрезка списка FJ)
- [ ] 3.5 `resume` через `start_row` из PJ / параметра

---

## 4. Сохранение + ошибки

- [ ] 4.1 Запись docx + `store.save(pj)` после прогона
- [ ] 4.2 При `created=0` PJ не сохраняется; файлы не откатываются
- [ ] 4.3 Обработка ошибок: одна ошибка → запись в `GenerateReport.errors`, продолжение
- [ ] 4.4 Логирование каждого этапа (DEBUG/INFO)

---

## 4. Тесты `tests/services/test_generate.py`

- [ ] 7.1 `test_full_sequential_run`
- [ ] 7.2 `test_resume_start_row`
- [ ] 7.3 `test_max_docs_limit`
- [ ] 7.4 `test_error_continues`
- [ ] 7.5 `test_max_docs_zero`
- [ ] 7.6 `test_empty_data_source`
- [ ] 7.7 `test_resume_updates_pj`

---

## 5. Проверки и CI

- [ ] `pytest tests/services/test_generate.py -v` — зелёные, покрытие ≥ 90%
- [ ] `pytest tests/ -q` — без регрессий
- [ ] Pre-commit чистый
- [ ] `CHANGELOG.md [Unreleased]` — запись о фиче 006
- [ ] PR `feat/006-core-generate` → `develop`

---

## Definition of Done

- [ ] `pytest tests/services/test_generate.py -v` — зелёные, покрытие `generate.py` ≥ 90%
- [ ] `pytest tests/ -q` — все зелёные
- [ ] Pre-commit чистый
- [ ] `CHANGELOG.md [Unreleased]` — запись о фиче 006
- [ ] PR `feat/006-core-generate` → `develop`