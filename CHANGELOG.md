# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0-alpha] — 2026-09-12

First versioned pre-release: nested employee/project generation on top of
the document generator.

### Added
- Product version `0.1.0-alpha` (`docxforge.__version__`, `python cli.py --version`).
- Nested project creation: `Employee/Project` folders from one batch source
  via composite path template `{{поле_сотрудника}}/{{поле_проекта}}`
  (e.g. `{{фио_сотрудника}}/{{проект}}`).
- `parse_composite_template()` and routing in `create_projects_from_template()`
  (`docxforge/generate.py`); per-employee `docxforge_settings.json`.
- Composite template field with validation in Fill Form; row-count dialog and
  `Создано сотрудников: N, проектов: M` summary.
- Unit, integration and E2E tests (`tests/test_nested_projects.py`,
  `tests/test_gui_fill_form.py`, `tests/test_version.py`).

### Fixed
- Composite placeholders resolve via field mapping (field name → table column),
  so `{{фио_клиента}}` (Таблица `клиенты`, столбец `фио`) groups by `фио`.
- Any whitespace inside `{{ ... }}` resolves; folders are never created with
  literal `{{ ... }}` names (batch-value fallback with warning).
