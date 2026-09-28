# JSON-слой данных (003)

Graduated from `specs/003-json/` (Status: done). Примеры: `specs/003-json/*.json`.

## Три типа
- **Project JSON** (`<имя>.docxforge`): конфиг — шаблоны → поля (маппинг),
  пакетные источники, `resume`. Схема-словарь, пути относительные.
- **Filling JSON**: разрешённые данные одного документа
  (`{"template", "dist", "fields": {name: value}}`, только значения).
- **Application JSON** (`~/.docxforge/docxforge_settings.json`): недавние
  проекты и настройки (без шаблонов/счётчиков — они в PJ).

## Границы (engine, без Qt)
- `Renderer.render_from_json(filling)` — рендер без Excel (валидация,
  `ValueError`; `generate` оборачивает в `GenerationError`).
- `engine/data_formatting.py` — Excel → JSON: `value_to_str`,
  `read_table_rows`, `resolve_source_row*`, `resolve_fields`, `advance_resume`.
- `schema.validate_project_json` / `normalize_project_json` — схема PJ
  (`number`→`counter`, `templates_new`→словарь, абсолютные→basename).
- Префилл создания (flat/nested) идёт через `resolve_fields` +
  `render_from_json`. Резолвер основного цикла — `resolve_document_fields()`
  здесь же (перенесён из `render_loop` бит-в-бит: linked-таблицы, legacy,
  M7, агрегации, image-пути); `render_loop.resolve_field_values` — тонкая
  обёртка. Коэрсия цикла — plain `str()` (legacy M6); strip/int-fix только
  в `value_to_str` для новых путей.

## Тесты
- `tests/json/<имя>/` (xlsx + docx + filling.json + expected.docx) +
  `tests/test_json_fixtures.py` (текстовое сравнение с эталоном).
- `test_003_render_json`, `test_003_data_formatting`, `test_003_project_json`.
