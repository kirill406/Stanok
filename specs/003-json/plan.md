# PLAN — 003-json

## Phase 0 «Разведка» — done
- Примеры нормализованы, схемы зафиксированы разделом «Три типа JSON».

## Phase 1 «Filling JSON → docx» (ветка `feat/003-render-json`)
- [ ] `Renderer.render_from_json(filling: dict)` — рендер без Excel
- [ ] Тесты на JSON-фикстурах (включая разрыв строки, таблицы, картинки)
- [ ] Харнес `tests/json/` + `test_json_fixtures.py` (готов: текстовое
      сравнение с эталоном; новый тест = новая подпапка без кода)

## Phase 2 «Excel → JSON» (ветка `feat/003-data-formatting`)
- [ ] Граница чтения: типы ячеек, режимы строк, счётчики, resume → JSON
- [ ] Старый путь чтения работает как раньше (Strangler, без переключения)

## Phase 3 «Нормализация Project JSON» (ветка `feat/003-project-json`)
- [ ] Схема-словарь, относительные пути, миграция legacy
- [ ] Тесты round-trip + миграция

## Phase 4 «Переключение путей»
- [x] Flat + nested: префилл через `resolve_fields` + `render_from_json`
      (значения замороженного конфига → Filling JSON → docx)
- [x] Dead code удалён (`setup_nested_*`, `write_nested_*`, `copy_data_folder`,
      `copy_template_file`, `create_result_folder`, `NESTED_*`)
- [ ] Main loop (`render_loop`) и CLI — НЕ переключаем: резолвер цикла богаче
      (linked-таблицы, legacy-фолбэк, M7), чем модуль P2. Полное переключение —
      отдельная задача с M7-паритетом в `data_formatting` (follow-up).

## Phase 5 «Закрытие»
- [ ] Процедура done: Status, graduate в `docs/` + `AGENTS.md`, SUMMARY,
      CHANGELOG (ломающие — с путём миграции)
- [ ] Мерж `spec-003` в `main`, проверка сборки exe
