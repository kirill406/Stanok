# PLAN Phase 7 — B5 «Защита от перезаписи» (spec 002-stabilization)

Branch: `feat/002-no-overwrite` (from `spec-002`).
Scope (Non-overlap contract): главное меню + recent storage (только чтение формата!) + переименование в engine.
Out of scope: формат недавних проектов НЕ меняется; CLI-паритет; `renderer.py` (зарезервирован за B0); `generate.py` (B1/B4).

Проблема: генерация из главного меню (`MainWindow.generate_for_project` → `generate_project` →
`Renderer.render` → `execute_render` → `write_output_doc` в `src/docxforge/engine/render_loop.py`)
открывает выходной файл через `zipfile.ZipFile(out_path, 'w')` — существующий файл молча перезаписывается.

- [x] P1: ветка + этот план (коммит + push)
- [x] P2: engine: `resolve_unique_output_path()` в `render_loop.py` + использование в `write_output_doc`
      (существует → `файл (1).docx`, `файл (2).docx`, …; существующий не трогаем)
- [x] P3: регрессионный тест `tests/test_b5_no_overwrite.py`
      (предсоздать файл → сгенерировать → оба на месте + юнит-тест цепочки `(1)`→`(2)`)
- [x] P4: `pytest tests/ -q` зелёный; merge --no-ff в `spec-002`, push

Конвенции: `logging` вместо `print`, RU-строки через `STRINGS` (новых строк не добавляем —
переименование бесшумное, без UI-текста), багфикс → регрессионный тест.

Recent storage: `_load_recent()` в `main_window.py` уже читает оба формата (list — старый,
dict с `recent_projects` — новый); формат не меняем, только читаем. Изменений в
`main_window.py` не требуется: путь генерации из меню идёт через engine-фикс.
