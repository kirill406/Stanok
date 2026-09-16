# B0 «Сверка готового» — отчёт-фиксация (002-stabilization)

Ветка: `feat/002-b0-verify` → merge в `spec-002`. Статус: сверка, код НЕ менялся
(исключение — нет; gaps зафиксированы как follow-up, молчаливого закрытия нет).

## A. Множественный выбор папок проектов — DONE

Доказательства:

- Тесты: `python -m pytest tests/test_dialogs.py -q` → **3 passed**.
  - `test_m_configure_sets_directory_multiselect` — диалог в режиме `Directory` +
    `DontUseNativeDialog`, `MultiSelection` на `listView`/`treeView`.
  - `test_m_rejected_dialog_returns_empty` — отмена → `[]`.
  - `test_m_add_many_projects` — валидная папка попадает в `recent_projects`
    (+1), невалидная (`not_a_project` без `проект.docxforge`) — в сводку
    `QMessageBox.information` с её именем.
- Ручная проверка по коду:
  - Кнопка в главном окне: `src/docxforge/gui/main_window.py:211`
    (`STRINGS['main_add_many_btn']`) → `_add_many_projects` (`main_window.py:402`).
  - Логика: `get_existing_directory_list` (`src/docxforge/gui/dialogs.py:31`,
    мультивыбор через `configure_multiselect`, `dialogs.py:16`); папка валидна
    iff есть `проект.docxforge` → `_add_recent`, иначе в `skipped` → сводка
    `STRINGS['main_added_many_skipped']` / `STRINGS['main_added_many']`
    (`main_window.py:409-425`, строки через `STRINGS` — `strings.py:125-128`).
- Полный сьют на момент сверки: `pytest tests/ -q` → **384 passed**
  (pre-commit hook при коммите P1).
