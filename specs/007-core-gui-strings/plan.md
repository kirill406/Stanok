# План: 007-core-gui-strings

> Детализация `spec.md` → шаги реализации. Маленькая фича, один коммит.

---

## Шаг 1: Модуль

- `src/stanok/gui/__init__.py` — пустой (+ лицензионный заголовок).
- `src/stanok/gui/strings.py` — класс `STRINGS`, 19 ключей из §2.2 спеки, тексты дословные.

## Шаг 2: Миграция потребителей

- `app.py` → `S.APP_*`, снять `# TODO(007)`.
- `schema.py` → `S.SCH_*` (2 сообщения).
- `generate.py` → `S.GEN_RESULT_DIR`.
- `tables/excel.py` → `S.TBL_*` (4 сообщения).

## Шаг 3: Тесты

- `tests/gui/test_strings.py` — импорт, непустота, плейсхолдеры, AST-скан.
- Обновить `match=` на русские тексты → `S.КЛЮЧ` (найти grep'ом по кириллице в `tests/`).

## Definition of Done

- [ ] `pytest tests/gui/test_strings.py -v` — зелёные
- [ ] `pytest tests/ -q` — все зелёные
- [ ] `grep -rn "TODO(007)" src/` — пусто
- [ ] Pre-commit чистый
- [ ] `CHANGELOG.md [Unreleased]` — запись о фиче 007
