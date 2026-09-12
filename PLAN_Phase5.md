# PLAN_Phase5 — Integration with Fill Form (Nested Employee/Project Generation)

**Parent:** PLAN.md Phase 5 | **Spec:** SPEC.md | **Status:** In progress
**Branch:** `feat/phase5-fillform-integration`
**Scope:** `docxforge/gui/fill_form/config_io.py` (метод `_create` + диалоги),
`docxforge/gui/strings.py` (только reuse + минимум новых).
`docxforge/generate.py` НЕ переписывать — только вызывать engine-функции.

> Qt event loop (AGENTS.md): только модальные диалоги в GUI-потоке
> (`QInputDialog`/`QMessageBox` в слоте `_create`), без потоков и таймеров.

---

## Подпункты

### 5.1 Диалог количества строк + отмена
- [ ] В `_create()` (режим `create_projects`): посчитать всего строк первичного
      SEQUENTIAL batch-источника через `DataReader.read_all_batch_sources()`.
- [ ] Если строк > 1 (или всегда, когда есть данные): `QInputDialog.getInt`
      с текстом из `STRINGS['fill_found_rows']`, default = всего строк,
      min 1, max = всего строк.
- [ ] Cancel/Close диалога → немедленный `return`, ничего не создано
      (до этого момента никаких записей на диск из `_create`).

### 5.2 Вызов engine с composite-шаблоном
- [ ] Перед вызовом engine: сохранить собранный config
      (`renderer.project.templates[...] = config; renderer.save_project()`),
      т.к. engine читает `проект.docxforge` с диска.
- [ ] Вызвать `create_projects_from_template(project_dir, template_rel_path,
      folder_name_template, max_projects=выбор_пользователя)`.
- [ ] Composite-диспетч (совместимость с параллельными Ф2–Ф4):
      если шаблон содержит `/` и в `generate` есть
      `create_nested_employee_projects` — вызывать её; иначе flat-вызов выше.
- [ ] Удалить устаревшие `_create_projects()` / `_get_effective_values_for_doc()`
      (рендерили документы в `output/` вместо создания проектов через engine).

### 5.3 Success / error сообщения
- [ ] Nested-результат `(path, n_employees, n_projects)` → новая минимальная
      строка `fill_nested_projects_created`:
      `Создано сотрудников: {employees}, проектов: {count} в {path}`.
- [ ] Flat-результат `(path, count)` → reuse `STRINGS['fill_found_rows']`/
      `STRINGS['fill_projects_created']`.
- [ ] `GenerationError`/любое исключение engine → `QMessageBox.warning`
      с понятным текстом ошибки (без traceback в UI).
- [ ] Ошибка подсчёта строк (нет источников/данных) → warning, без создания.

### 5.4 Проверка
- [ ] `python -m pytest tests/ -q` → без новых падений
      (GUI-тесты могут требовать Qt — тогда фиксируется причина +
      минимум импорт/синтаксис `config_io.py` и engine-тесты).
- [ ] Ручной сценарий: composite-шаблон → диалог → OK → success
      `Создано N сотрудников, M проектов в [path]`; Cancel → пусто.

---

## Критерии приёмки

1. `_create()` вызывает engine с composite-шаблоном и лимитом из диалога.
2. Диалог кол-ва строк показывает итог по всем проектам (все строки источника).
3. Success: `Создано N сотрудников, M проектов в [path]` (nested) /
   `Создано проектов: {count} / {path}` (flat, reuse строки).
4. Отмена диалога → ничего не создано.
5. Ошибка engine → понятное сообщение в `QMessageBox`, без падения.
6. `generate.py` не переписан (только вызовы).
7. Новых `print()` нет; русские строки только через `strings.py`.
