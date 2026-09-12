# Plan: Phase 6 — Unit Tests for Nested Employee/Project Generation
**Spec:** SPEC.md | **Status:** In progress (branch `feat/phase6-unit-tests`)

---

## Goals

- Create `tests/test_nested_projects.py` covering nested generation
  (Employee → Projects) per SPEC.md
- Scope: ONLY `tests/test_nested_projects.py` (+ fixtures рядом).
  Исходники `generate.py` / GUI НЕ менять
- Если API других фаз (Phase 2–4) ещё нет — тесты с
  `monkeypatch` / `importorskip` / `pytest.skip`, в отчёте зафиксировать
  какие тесты pending и почему
- Покрыть то что уже есть: flat-режим + parse-заглушки

---

## Constraints

- Follow existing code style: 4 spaces, UTF-8, snake_case, PascalCase
- Test naming: `test_<module>_<scenario>_<expectation>`
- No `print()` — `logging` в хелперах
- Never commit `.env`
- No new dependencies beyond requirements.txt

---

## References

| File | Purpose |
|------|---------|
| `docxforge/generate.py` | `create_projects_from_template()`, `_build_project_config()`, `_resolve_folder_name_template()` (flat, уже есть); `parse_composite_template()` / `create_nested_employee_projects()` (Phase 2–3, пока нет) |
| `docxforge/engine/schema.py:265` | `create_projects()` (flat helper, уже есть) |
| `tests/test_create_projects.py` | Flat-тесты как образец фикстур |

---

## Subtasks (чек-лист тестов + что проверяет каждый)

- [ ] 6.1 `test_nested_basic_generation_creates_employee_and_project_folders` — basic nested generation (2 employees × 3 projects): структура Employee/Project создана, счётчики сотрудников/проектов верны. Pending если нет `create_nested_employee_projects`
- [ ] 6.2 `test_nested_data_folder_copied_fully` — `Данные/` скопирована целиком (все xlsx, без нарезки строк). Pending если нет nested API; частично покрывается flat-проверкой копирования
- [ ] 6.3 `test_nested_settings_json_structure_and_content` — `docxforge_settings.json`: ключи employee/employee_folder/created_at/projects, записи name/folder/template/row_index/created_at. Pending если нет nested API
- [ ] 6.4 `test_nested_config_transformation_applies` — TABLE→CONSTANT со значениями строки, COUNTER reset (start/step/format), batch→CONSTANT. Покрывается существующим `_build_project_config()` (pass), плюс nested-вариант pending
- [ ] 6.5 `test_nested_composite_template_parsing` — `parse_composite_template("{{employee}}/{{project_name}}")` → (employee_part, project_part), детект composite vs flat, валидация обоих плейсхолдеров. Pending если нет `parse_composite_template`; fallback — проверка `_resolve_folder_name_template()` (pass)
- [ ] 6.6 `test_nested_max_projects_limit_respected` — max_projects ограничивает общее число проектов. Покрывается flat (`create_projects_from_template(max_projects=...)`, pass), nested-вариант pending
- [ ] 6.7 `test_nested_missing_column_raises_clear_error` — отсутствие `employee`/`project_name` колонки → понятная ошибка. Pending если нет nested API
- [ ] 6.8 `test_nested_flat_mode_backward_compatible` — flat-шаблон без `/` работает как раньше через `create_projects_from_template()` (pass, регрессия)

---

## Definition of Done

- [ ] `python -m pytest tests/test_nested_projects.py -v` → pass/skip, 0 failed
- [ ] `python -m pytest tests/ -q` → no regressions
- [ ] Коммиты `test: <что> [phase6]` запушены в `feat/phase6-unit-tests`
- [ ] Merge в main без --force, конфликты в tests/ — сохранять оба набора
- [ ] Отчёт: подпункты, коммиты/пуши, полный вывод pytest (passed/failed/skipped, pending и почему), ошибки, main/ветка

---

## Risks / Open Questions

| Risk | Mitigation |
|------|------------|
| `parse_composite_template` / `create_nested_employee_projects` ещё не реализованы (Phase 2–3) | Тесты skip через hasattr-check с причиной; покрыть существующие flat-хелперы |
| Фикстуры nested Excel (employee + project_name) | Локальный хелпер `_make_nested_source_project()` в файле теста |
| Дубль папок / пустые имена | Ожидаемое поведение: суффиксы `_1`, `_2`; fallback `employee_N`/`project_N` (тест pending до реализации) |
