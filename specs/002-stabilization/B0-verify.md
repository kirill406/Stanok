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

## B. Папка вывода `Результат` — GAP (не done, follow-up задача)

Проверка `grep output src/` показывает: `output` **есть в коде**, пункт нельзя закрыть как done.

Что уже переведено на `Результат` (engine-путь — DONE):

- `src/docxforge/generate.py:139` и `src/docxforge/engine/render_execute.py:44` —
  дефолт генерации `Результат/`; `tests/test_functional_generate.py:197`
  (`not (project/'output').exists()`) зелёный;
  `pytest tests/test_dialogs.py tests/test_functional_generate.py -q` → **12 passed**.
- `src/docxforge/engine/schema.py:420,515`, `generate.py:316,870` — создают `Результат/`.

Остатки `output` (каждый — follow-up, чужие файлы по Non-overlap contract — НЕ трогал):

1. `src/docxforge/gui/fill_form/config_io.py:218` —
   `output_dir=os.path.join(self.project_dir, 'output')`: генерация из окна
   заполнения пишет в `output/`, а не в `Результат/`. Подтверждено тестами
   `tests/test_gui_fill_form.py:314,393` (glob `output/*.docx`, assert ≥1 doc) и
   диском: `test_project/output/`, `test_project_cli/output/` существуют,
   каталога `Результат` на диске нет нигде. Файл за B1 → фикс туда.
2. Legacy-fallback `generate.py:137-143` / `render_execute.py:41-48`: если `output/`
   существует — используется он. Тормозит полный переход на `Результат`
   (допустимо удалить как обратную совместимость — версия не меняется).
3. Косметика: `generate.py:914` (`print(f'Output: ...<project>/output/')` —
   заодно `print` вместо `logging`), тултипы `gui/project_window.py:59,254`
   про «output» (там же хардкод RU мимо `STRINGS`), неиспользуемая
   `STRINGS['project_output']='Результаты'` (`gui/strings.py:18`, мн.ч. vs
   `Результат` в коде, ссылок на ключ нет).
