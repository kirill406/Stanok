# PLAN — 001-review: глубокое ревью кода

## Goal
Провести глубокое ревью всего репозитория (`src/docxforge`, `tests/`, точки входа `run.py`/`cli.py`,
`tests/smoke_engine.py`) после переезда на `src/`-layout и uv. Результат: отчёт с находками
по приоритетам + trivial-фиксы сразу, остальное — отдельными задачами.

## Scope
- `src/docxforge/engine/` (schema, parser, renderer, data_reader), `src/docxforge/generate.py`,
  `src/docxforge/cli/`, `src/docxforge/gui/` (включая `fill_form/`)
- `tests/` (качество тестов, а не только покрытие), `run.py`, `cli.py`, `tests/smoke_engine.py`
- Конфиги: `pyproject.toml`, `pytest.ini`, `conftest.py`, `.gitignore`, хуки

## Non-goals
- Не менять поведение (кроме trivial-фиксов: форматирование, опечатки, мёртвый код с доказательством)
- Не трогать `specs/000-pre-alpha/` (замороженная история)
- Не рефакторить архитектуру в рамках ревью — только зафиксировать находки

## Phases
### 1. Инвентаризация и метрики
- Дерево модулей, LOC, зависимости между слоями (`GUI → engine`, запрет обратных)
- Покрытие: `pytest --cov=src/docxforge --cov-report=term-missing tests/`, точки <85%

### 2. Статика: стиль, дубли, мёртвый код
- `print()` вместо `logging` (запрещено AGENTS.md), русские строки в коде (только через GUI-strings),
  неиспользуемые импорты/функции (доказательство через `git grep`), дубли логики

### 3. Engine глубоко
- `schema.py`: контракт `.docxforge`-конфига, валидация, сериализация
- `template_parser.py` / `renderer.py`: корректность склейки XML-run'ов, краевые случаи
  (разбитые плейсхолдеры, таблицы, header/footer), обработка ошибок
- `data_reader.py`: Excel-парсинг, типы, большие файлы
- `generate.py`: режимы flat/composite, `max_projects`, rollback при ошибках, `_sanitize/_unique`

### 4. GUI / CLI глубоко
- Qt-паттерны: event loop, сигналы/слоты, модальные диалоги, утечки виджетов, headless-поведение
- `fill_form/`: валидация composite-шаблона, cancel-пути, row-count диалог
- `cli.py`/`run.py`/`main()`: коды выхода, сообщения об ошибках на русском

### 5. Качество тестов
- Слабые ассёрты, тесты-пустышки, дубли фикстур (`tests/documents/*` vs `tests/test_project/`),
  медленные тесты, GUI-тесты без `qapp`-изоляции, проверка негативных сценариев

### 6. Trivial-фиксы
- Применять сразу, отдельным коммитом; после каждого — `pytest tests/ -q`
- Критерий trivial: не меняет поведение, очевидно безопасен, покрыт существующими тестами

### 7. Отчёт
- `specs/001-review/REPORT.md`: таблица находок (Severity: blocker/major/minor, файл:строка,
  описание, предлагаемое действие), метрики до/после, список follow-up задач

## Verification
- До старта: `pytest tests/ -q` зелёный (261 passed baseline)
- После trivial-фиксов: `pytest tests/ -q` + `python tests/smoke_engine.py` + `cli.py --version`
- Отчёт содержит все находки major+ с привязкой к коду

## Branching
- Ревью выполнено в `review/code-001-review` (от `review/directory-structure`, т.к. ревьюится
  код после src/uv-миграции; `REPORT.md` + ~40 trivial-фиксов, 261 passed)
- Разбор находок: ветка `fix/001-review-findings`, задачи в `tasks.md`

## Execution (разбор находок — ведётся здесь)
- [x] Фаза 1-5: 4 субагента (engine-агент падал 2×, перезапущен)
- [x] Фаза 6: trivial-фиксы применены и проверены (261 passed + smoke)
- [x] Фаза 7: `REPORT.md` готов
- [x] Разбор blockers B1–B10 (статус — в `tasks.md`)
  - done: B1 (`ac189a8`), B2,B3,B4,B6,B7 (`de26475`), B8 (фикс `de26475`, тесты `c762877`),
    B5,B9,B10 (`c762877`); `pytest` → 317 passed
- [ ] Разбор majors M1–M17 (статус — в `tasks.md`)
  - done: M13 (`ac189a8`); остальное (M1–M12, M14–M17) — todo
- Правило: багфикс → регрессионный тест; коммит на задачу; отмечать `[x]` в `tasks.md`
