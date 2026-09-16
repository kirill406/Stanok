# PLAN Phase 3 — B1 «Генерируемые проекты» + B0-gap `output/` (002-stabilization)

Branch: `feat/002-projects` (от `spec-002`). Интеграция — только в `spec-002`, НЕ в main.

Конвенции: `logging` вместо `print`, RU-строки через `STRINGS`, багфикс → регрессионный тест,
коммит на подпункт + push.
Non-overlap: B3 имеет ПРИОРИТЕТ на guard-ханках `config_io.py::_create`,
`form_dialog.py::__init__`, `project_window.py` — их не трогаю.
Моя секция в `form_dialog.py` — отдельный метод/место. Перед каждым коммитом:
`git pull --rebase origin spec-002`. Pre-commit hook гоняет `pytest tests/ -q` сам.

## Подпункты

- [x] P0. План и ветка: `PLAN_Phase3.md`, ветка `feat/002-projects`, push -u origin. (этот файл)
- [ ] P1(г). ДОП `output/` → `Результат`: `config_io.py:218` (однословная правка внутри
      `_create`, конфликт-риск с B3 зафиксировать в отчёте), убрать legacy-fallback
      `output/` в `generate.py:137-143` + `render_execute.py:41-48` (всегда `Результат/`),
      `generate.py:914` текст `<project>/output/` → `Результат` (stdout `print` сохраняю:
      покрыт тестом `test_generate_cli_returns_outputs` через capsys — перевод на logging
      его сломает; зафиксировано как осознанное отклонение).
      Обновить 2 ассёрта `tests/test_gui_fill_form.py:314,393` (`output` → `Результат`).
      `project_window.py` НЕ трогаю (приоритет B3). Коммит + push.
- [ ] P2(а). Снапшот `проект.docxforge` по имени проекта в Home: новые хелперы в `generate.py`
      (`get_home_dir`, `unique_home_project_file`, `save_project_snapshot_to_home`),
      коллизия имени → переименование создаваемого `(1)`, `(2)`, … (существующее не трогать),
      опциональный параметр `home_dir` для hermetic-тестов. Вызов из flat +
      nested создания. Регрессионные тесты в новом `tests/test_002_projects.py`
      (новый файл — без конфликта с B3). Коммит + push.
- [ ] P3(б). Предзаполнение генерируемых проектов: после сборки каждого проекта рендер
      ≥1 документа в его `Результат/` (`_render_prefilled_project_docs` в `generate.py`,
      best-effort с warning-логом), константы уже подставлены via `_build_project_config`.
      Регрессионные тесты (flat + nested: docx существует, константа в тексте) в
      `tests/test_002_projects.py`. Коммит + push.
- [ ] P4(в). Секция «Поля шаблона для генерируемых проектов» в `FillForm`: новый
      `QGroupBox` отдельным методом `_build_generated_project_section` (STRINGS, без хардкода RU),
      чекбоксы полей → новое опциональное поле `TemplateConfig.generated_project_fields`
      (`schema.py`, сериализация round-trip; `[]` = все поля, back-compat), сбор в
      `config_collector.py`, загрузка в `config_io._load_existing_config` (не guard-ханк),
      сигналы autosave — внутри своего билдера (не трогаю `_connect_autosave`),
      фильтр в `_build_project_config(include_fields=...)`, проброс из flat + nested.
      GUI-тест секции + unit-тест фильтра в `tests/test_002_projects.py`. Коммит + push.
- [ ] P5. Финал: `checkout spec-002`, `pull --ff-only`, `merge --no-ff feat/002-projects`,
      `push origin spec-002`. Конфликт/push-reject → НЕ форсить: `merge --abort`,
      ветку оставить запушенной, сообщить в отчёте. Прогон затронутых тестов.

## Риски/границы

- `config_io.py:218` лежит внутри заявленного B3 ханка `_create` — правка минимальная
  (одно слово), в отчёте явно указать для сведения при мерже B3.
- `tests/test_gui_fill_form.py` заявлен B3 (регрессионный тест) — мои 2 строчные правки
  минимальны, указать в отчёте.
- `renderer.py` НЕ трогаю (резерв B0), `project_window.py` НЕ трогаю (приоритет B3).
