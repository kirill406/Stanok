# PLAN_003_Phase2.md — Phase 2 «Excel → JSON» (P2)

Branch: `feat/003-data-formatting` (от `spec-003`).
Spec: `specs/003-json/spec.md` + `plan.md` (Phase 2).
Зона P2: граница Excel → JSON. Запрещены: `renderer.py` (P1), изменения
`schema.py` (только чтение/импорт), `generate.py`, `gui/`, `cli/`.
Strangler: только новый модуль рядом, старый путь чтения НЕ трогать
и НЕ переключать.

## Подпункты

- [ ] 1. Каркас `src/docxforge/engine/data_formatting.py`: `value_to_str`
  (нативные типы ячеек `int`/`float`/`bool`/`None` → `str`, битые ячейки → `''`)
  + `read_table_rows` поверх `DataReader` (missing/corrupt файл → `[]`, warning).
- [ ] 2. `resolve_source_row` (+ обёртка под `BatchSourceConfig`/`ResumeState`):
  режимы `constant` (первая строка / lookup), `sequential` (исчерпание → `None`),
  `circular` (по кругу), `start_offset` из resume.
- [ ] 3. `resolve_fields(field_mappings, row, ...)` → `{name: value}` для
  Filling JSON: типы `constant`/`table`/`counter`/`today`/`image`, без плейсхолдеров.
- [ ] 4. `advance_resume(resume, created)`: математика B6
  (`last = last + created`, `continue_from_last=False` → база 0, `created <= 0` — no-op).
- [ ] 5. Тесты `tests/test_003_data_formatting.py`: типы, режимы строк,
  счётчики, resume, битые ячейки. Полный `pytest tests/ -q` зелёный.

## Acceptance Phase 2

- Граница Excel → JSON покрыта тестами; старый путь работает как раньше.
- `pytest tests/ -q` зелёный после каждого коммита (pre-commit hook).
- GUI/CLI без изменений поведения.
