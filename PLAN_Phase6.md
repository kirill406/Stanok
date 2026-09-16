# PLAN Phase 6 — B4 «Исключение копирования» (spec-002)

Branch: `feat/002-skip-copy` → merge `--no-ff` into `spec-002`.
Scope (Non-overlap contract): `batch_section.py`, `field_rows.py`,
флаги копирования в `generate.py` (только новые функции-флаги, создание
проектов правит B1). `form_dialog.py` ЗАПРЕЩЁН.

## Subitems

- [ ] P1 — STRINGS: ключ `batch_skip_copy` («Исключить копирование»),
  без хардкода русских строк (`src/docxforge/gui/strings.py`, аддитивно).
- [ ] P2 — UI: чекбокс «Исключить копирование» у каждой таблицы
  (`BatchSourceRow` в `batch_section.py` + ключ `chk_skip_copy`
  в `get_widgets_dict()`); всегда видим, т.к. переключение видимости
  по режиму потребовало бы `form_dialog.py` (запрещён).
- [ ] P3 — Engine: флаги копирования в `generate.py` — ТОЛЬКО новые функции:
  `get_skip_copy_tables()` (чтение флага через `getattr`, без изменения
  схемы) + `copy_data_tree()` (копирование `Данные/` с исключениями);
  существующие функции создания проектов НЕ трогать (зона B1).
- [ ] P4 — Тест: регрессионный `tests/test_generate_skip_copy.py`
  (исключённые таблицы не копируются, остальные — как раньше) + зелёный
  `pytest tests/ -q`.

## Handoff B1 (вне scope B4)

- Сохранение флага в конфиг (`config_collector.py` / `config_io.py` — файлы B1).
- Проброс `exclude` в `create_projects_from_template` /
  `create_nested_employee_projects` (создание проектов — зона B1).
- Добавление поля `skip_copy` в `BatchSourceConfig` (`schema.py`);
  `get_skip_copy_tables()` уже читает его через `getattr`, т.е. совместим.
