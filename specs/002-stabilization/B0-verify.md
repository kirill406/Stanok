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

## C. Баг разрыва строки — ПОДТВЕРЖДЁН, НЕ ЧИНЮ (фикс — `fix/002-linebreak-merge`)

Симптом из спеки воспроизведён на `merge_and_replace_paragraph`
(`src/docxforge/engine/merge.py:12`, вызывается из `process_xml`,
`src/docxforge/engine/render_loop.py:287,320`; `renderer.py` — только фасад):

- Смешанный run как его хранит Word (Shift+Enter):
  `<w:r><w:t>текст</w:t><w:br/><w:t>текст{{поле}}</w:t></w:r>` →
  после мержа: `'тексттекстЗНАЧ' | <BR/>` — разрыв съехал ЗА поле
  (ожидалось `текст | <BR/> | текстЗНАЧ`).
- Плейсхолдер, разорванный между runs, + `w:br` в первом run →
  `'тексттекст' | 'ЗНАЧ' | <BR/>` — тот же съезд.
- `w:br` отдельным run'ом — корректно (контрпример, баг именно про
  не-текстовый контент внутри текстового run'а).

Первопричина (два места в `merge.py`, оба оставляют не-текст `w:br/w:drawing`
на исходной позиции, а текст переизлучают до неё):

- 1-й проход, строки 40-60: in-place замена склеивает весь `t`-текст run'а
  в `t_els[0]`, `w:br` остаётся после склеенного текста;
- 2-й проход, строки 119-150: клоны текста вставляются `addprevious` до
  исходного run'а, исходный run хранит только не-текст на месте.

Фикс и регрессионный тест (`текст<w:br/>текст{{поле}}` в одном run'е) —
за веткой `fix/002-linebreak-merge` другого агента, `renderer.py`/`merge.py`
зарезервированы за ней. Здесь код не менялся сознательно.
