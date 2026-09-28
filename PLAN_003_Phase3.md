# PLAN_003_Phase3 — Нормализация Project JSON (P3)

Scope: только `src/docxforge/engine/schema.py` + `tests/test_003_project_json.py`.
Запрещены: `renderer.py`, `generate.py`, `gui/`, `cli.py`.
Конвенции: `logging` вместо `print`, без хардкода RU-строк, багфикс → регрессионный тест.

Нормативный пример: `specs/003-json/project_generation.json`
(схема-словарь `templates`, относительные пути, типы `constant/table/counter`,
batch sources словарём, `resume`).

- [ ] 1. `validate_project_json(data: dict) -> list[str]` — проверка схемы
      Project JSON: обязательные `templates`/`fields`, известные типы полей
      (`constant/table/counter/today/image`), batch mode из
      (`constant/sequential/circular`), относительные пути (абсолютный путь — ошибка).
- [ ] 2. `normalize_project_json(data)` — legacy-миграция в коде:
      `type: number` → `counter`, массив `templates_new` → словарь (если встретится),
      legacy batch mode (`single`→`constant`, `all_rows`/`n_rows`→`sequential`),
      абсолютные пути → basename, заполнение дефолтов `resume`/`continue_from_last`.
- [ ] 3. `tests/test_003_project_json.py`: валидный пример из
      `specs/003-json/project_generation.json` проходит; каждый класс ошибок ловится;
      `number`→`counter`; round-trip `normalize → validate` чисто.
- [ ] 4. Мерж в `spec-003` (`--no-ff`) + push (без форса при конфликте).
