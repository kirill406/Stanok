# План: 009-gui-project

> Детализация `spec.md` → шаги реализации.

---

## Шаг 1: Диалог

- `src/stanok/gui/project_dialog.py` — `ProjectDialog(project_ref, store, parent)`,
  шапка readonly + таблица шаблонов (имя, spin, кнопка).
- `STRINGS`: ключи `PROJ_*`.

## Шаг 2: Прогон и окно 3

- Кнопка шаблона → `GenerateWorker` + прогресс/отмена + итог (как в окне 1).
- Клик по строке → хук `_open_fields_dialog` (модуля `fields_dialog` нет до 010 —
  та же заглушечная схема, что была для окна 2: `PROJ_FIELDS_TBD` + тест).

## Шаг 3: Стык с окном 1

- Удалить ветку `ImportError` и ключ `MAIN_PROJECT_TBD` из окна 1.
- `test_row_click_stub_without_009` → мок `ProjectDialog.exec_`.

## Definition of Done

- [ ] `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_project_dialog.py -v` — зелёные
- [ ] `pytest tests/ -q` — все зелёные
- [ ] Pre-commit чистый, CHANGELOG — запись о 009
