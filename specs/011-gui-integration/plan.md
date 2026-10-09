# План: 011-gui-integration

> Детализация `spec.md` → шаги реализации. Новых виджетов нет.

---

## Шаг 1: Bootstrap

- `app.py`: `create_gui(store=None)` + `_run_gui` через неё, общий store.
- Юнит: `create_gui` возвращает окно без `exec_`.

## Шаг 2: Сквозной тест

- `tests/gui/test_integration.py`: окно 1 → окно 2 → окно 3 (Save) → прогон →
  docx + PJ. Настоящие диалоги, без `exec_`.

## Шаг 3: CLI-регрессия

- Тест `main([folder])`: мок `ProjectStore` в `services.generate`, код 0;
  битый проект → код 1.

## Definition of Done

- [ ] `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_integration.py -v` — зелёные
- [ ] `pytest tests/ -q` — все зелёные
- [ ] Pre-commit чистый, CHANGELOG — запись об 011
