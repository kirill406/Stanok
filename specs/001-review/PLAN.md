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
- Новая ветка `review/code-001-review` от `main` (не смешивать с `review/directory-structure`)
- Trivial-фиксы — отдельные коммиты; отчёт — финальный коммит; push, без мержа до аппрува
