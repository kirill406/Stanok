# PLAN_Phase7 — Integration Tests & Polish (Nested Employee/Project Generation)

**Spec:** SPEC.md (Nested Employee/Project Generation v1.0) | **Status:** In progress
**Branch:** `feat/phase7-integration-polish`
**Scope:** `tests/test_gui_fill_form.py` (только ДОБАВЛЕНИЕ UI-тестов; существующие не ломать)
+ end-to-end проверка (сгенерированные проекты умеют генерировать документы)
+ polish мелких багов ТОЛЬКО в своём скоупе.
`generate.py` / GUI-логику НЕ переписывать (только минимальные polish-правки с пометкой в отчёте).

## Codebase state (verified 2026-09-12, commit dc85302)

- SPEC.md/PLAN.md обновлены под nested/composite-режим, но код фаз 1–6 nested
  НЕ приземлён: `create_nested_employee_projects()` / `parse_composite_template()`
  отсутствуют, composite-UI в Fill Form нет, `tests/test_nested_projects.py` нет.
- Реально работает flat-режим: `chk_create_projects` + `edit_folder_name_template`
  (`form_dialog.py:237-253`, `_on_create_projects_toggled`, `_set_folder_name_visible`),
  `create_projects_from_template()` + `_resolve_folder_name_template()` /
  `_build_project_config()` в `generate.py`, тесты `test_create_projects.py`,
  `test_folder_name_resolution.py`.
- Вывод: UI-тесты Phase 7 покрывают СУЩЕСТВУЮЩИЕ виджеты create-projects режима
  (включая composite-вид шаблона `{{employee}}/{{project_name}}` как строковое
  значение поля — без требования несуществующих виджетов); e2e — flat-режим.
  Nested-AC, требующие нереализованного кода, честно помечаются в отчёте.

## Subtasks (чек-лист)

### 1. Hygiene-polish `tests/test_gui_fill_form.py` [phase7]
- [ ] Удалить дубль `test_autosave_on_field_change` (определён дважды, побеждает второй)
- [ ] Удалить мёртвый код после `if __name__ == '__main__':` (вложенный docstring + `def test_full_configuration_flow`, никогда не выполняется; дубль `if __name__`)
- [ ] `python -m pytest tests/test_gui_fill_form.py -q` → всё ещё green

### 2. UI-тесты create-projects / composite-поля [phase7]
- [ ] `test_create_projects_checkbox_toggles_folder_template`: чекбокс показывает/прячет `edit_folder_name_template`, прячет filename/dir rows
- [ ] `test_create_projects_checkbox_changes_button_text`: «Создать» ↔ «Создать проекты»
- [ ] `test_folder_name_template_accepts_composite_value`: composite-строка `{{employee}}/{{project_name}}` вводится, курсор/вставка поля ок
- [ ] `test_create_projects_empty_template_shows_warning`: пустой шаблон + `_create()` → `QMessageBox.warning`, документов/папок нет
- [ ] `test_folder_name_template_persists_on_save`: значение сохраняется в `проект.docxforge` (autosave)

### 3. E2E: сгенерированные проекты генерируют документы [phase7]
- [ ] Новый класс `TestCreateProjectsE2E` в `tests/test_gui_fill_form.py` (строго в скоупе файла)
- [ ] `create_projects_from_template()` → N проектов с `проект.docxforge` + `Шаблоны/*.docx`
- [ ] `generate_project()` на каждом сгенерированном проекте → ≥1 `.docx` в `Результат/` (или `output/`)
- [ ] Проверка конфига: TABLE→CONSTANT со значениями строки, COUNTER сброшен, константы целы

### 4. Full suite + smoke + merge [phase7]
- [ ] `python -m pytest tests/ -q` → exit 0
- [ ] `python test_engine.py` → exit 0
- [ ] Ручная сверка acceptance criteria (таблица ниже)
- [ ] `git pull origin main` → merge ветки в main → push (без --force)

## Acceptance criteria (из SPEC.md) — статусы по факту (2026-09-12)

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Composite template `{{employee}}/{{project_name}}` works | ⚠️ PARTIAL — composite-строка вводится/хранится в поле шаблона (UI-тест), но nested-кода нет |
| 2 | Employee folders with `docxforge_settings.json` created | ❌ NOT IMPLEMENTED — `create_nested_employee_projects()` отсутствует в коде |
| 3 | Project folders with `данные/` + `шаблоны/` + `результат/` + `проект.docxforge` | ⚠️ PARTIAL — flat создаёт `Шаблоны/` + `проект.docxforge`; `Данные/` не копируются |
| 4 | `данные/` is full copy of source project's data | ❌ NOT IMPLEMENTED (см. #2) |
| 5 | `проект.docxforge`: TABLE→CONSTANT, COUNTER reset, batch→CONSTANT | ✅ VERIFIED — e2e-тесты (после polish-фикса `fm.column in row_data`) |
| 6 | `docxforge_settings.json` lists all employee's projects | ❌ NOT IMPLEMENTED (см. #2) |
| 7 | Row count dialog works for total projects | ❌ NOT IMPLEMENTED — `fill_found_rows` объявлены, но нигде не используются |
| 8 | Success message shows employee and project counts | ⚠️ PARTIAL — есть «Создано проектов: N» (flat, хардкод в `config_io.py`) |
| 9 | Backward compatible with flat structure | ✅ VERIFIED — flat — основной e2e-путь, все старые тесты green |
| 10 | All existing tests pass | ✅ VERIFIED — `pytest tests/ -q`: 239 passed; `test_engine.py`: ALL CHECKS PASSED |

## Polish-правки вне tests/ (минимальные, за скоупом тестового файла)

- `docxforge/engine/schema.py`: сериализация `create_projects` / `folder_name_template`
  в `_to_dict` / `_from_dict` (раньше чекбокс и шаблон не переживали перезапуск диалога).
- `docxforge/generate.py`: `fm.file in row_data` → `fm.column in row_data` в
  `_resolve_folder_name_template()` и `_build_project_config()` (иначе TABLE-поля
  никогда не превращались в CONSTANT — SPEC-требование не выполнялось). |

## Commits

- `docs: add PLAN_Phase7 breakdown` (этот файл)
- `feat/test: <что> [phase7]` после каждого подпункта 1–3 (+ full suite прогон)
- merge в main, push
