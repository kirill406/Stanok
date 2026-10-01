# JSON-слой данных (003)

Graduated from `specs/003-json/` (Status: done). Примеры: `specs/003-json/*.json`.

## Три типа
- **Project JSON** (`<имя>.docxforge`): конфиг — шаблоны → поля (маппинг),
  пакетные источники, `resume`. Схема-словарь, пути относительные.
  Legacy-вход (массив `templates_new`, абсолютные пути, `number`,
  `project_name`) принимается и нормализуется: массив→словарь,
  абсолютные→basename, `number`→`counter`, `project_name` сохраняется.
- **Filling JSON**: разрешённые данные одного документа
  (`{"template", "dist", "fields": {name: value}}`, только значения).
- **Application JSON** (`~/.docxforge/docxforge_settings.json`): недавние
  проекты и настройки (без шаблонов/счётчиков — они в PJ).

## Границы (engine, без Qt)
- `Renderer.render_from_json(filling)` — рендер без Excel (валидация,
  `ValueError`; `generate` оборачивает в `GenerationError`).
- `engine/data_formatting.py` — Excel → JSON: `read_table_rows` /
  `read_project_table`, единый выбор строк (`_select_row` + адаптеры
  `resolve_source_row` / `resolve_legacy_source_row` /
  `resolve_source_row_for_config`), `resolve_document_fields`,
  `build_fillings`, `scan_project_template`. Упрощённые дубликаты
  (`resolve_fields`, `value_to_str`, `advance_resume`) удалены вместе
  с их тестами: семантика одна — полная (linked, legacy, M7).
- Единственный путь заполнения: `build_fillings` → `execute_render_fillings`
  → `render_effective` → `process_xml`. Старый цикл, `_read_table_data`,
  `_resolve_row_for_source`, wrapper `resolve_field_values` — удалены;
  `render()` — фасад с той же сигнатурой поверх fillings.
- `schema.validate_project_json` / `normalize_project_json` — схема PJ
  (`number`→`counter`, `templates_new`→словарь, абсолютные→basename). Коэрсия цикла — plain `str()` (legacy M6); strip/int-fix только
  в `value_to_str` для новых путей.

## Тесты
- `tests/json/<имя>/` (xlsx + docx + filling.json + expected.docx) +
  `tests/test_json_fixtures.py` (текстовое сравнение с эталоном).
- Поток PJ + Excel → FJ: кейсы с `project.json` + `data.xlsx` +
  `expected_filling.json` в том же харнесе.
- Потоки GUI ↔ AJ и GUI → PJ: `tests/test_json_gui_flows.py`
  (AJ изолирован в tmp).
- `test_003_render_json`, `test_003_data_formatting`, `test_003_project_json`.
