# REPORT — 001-review: глубокое ревью кода

Status: done

Date: 2026-09-13. Branch: `review/code-001-review` (от `review/directory-structure`,
т.к. ревьюится код после src/uv-миграции — от `main` было бы устаревшим; см. PLAN.md §Branching).
Baseline: `pytest tests/ -q` → 261 passed. После trivial-фиксов: 261 passed + smoke OK.

Метод: 4 субагента-исследователя (read-only): метрики/статика, engine, GUI/CLI, тесты.
Engine-агент дважды падал с provider-ошибкой (`reasoning encrypted_content...`), перезапущен,
с третьей попытки отработал. GUI/CLI-агент падал один раз, перезапущен успешно.

## Metrics
- `src/`: ~5800 LOC (крупнейшие: `generate.py` 888, `main_window.py` 463, `schema.py` 429,
  `form_dialog.py` 371, `render_loop.py` 362, `batch_section.py` 322, `config_io.py` 306)
- `tests/`: ~7000 LOC, 261 тест, 14× `pytest.skip()` с причинами, 0× `xfail`
- Слои чистые: engine зависит только от stdlib+lxml+openpyxl; обратных `engine→gui`,
  `engine→cli`, `gui→cli` нет. Одно исключение: `gui/fill_form/config_io.py:261`
  импортирует верхний `generate` (фасад, терпимо — зафиксировано)

## Применённые trivial-фиксы (этот коммит)
Импорты/мусор: удалены неиспользуемые импорты (`renderer`: zipfile/datetime/etree/W_NS;
`render_execute`: W_NS; `render_loop`: W + локальный дубль; `schema`: asdict, shutil→top;
`template_parser`: typing; `main_window`: QCoreApplication/QSettings/`self.settings`;
`config_io`/`config_collector`: QGroupBox; `field_rows`/`form_dialog`: FIELD_TYPES_ENUM;
`field_dialog`: QFileDialog→top; локальные `logging`→top; `main_window`: Project→top).
Удалены: `engine/render_loop.py.bak` (трекался!), закомментированный блок cycles/aggr,
stale-комментарий в `config_io`, дубль условия `sum_multiply or sum_multiply`,
неиспользуемая `qapp`-фикстура, 12 дублей `sys.path.insert` + висячие `import sys`,
`tests/__init__.py` — маркер-комментарий.
Логирование вместо молчания: `template_parser` header/footer `except→warning`;
`renderer`/`formatting` bare `except→logger.warning`; 7 голых `except: pass`
в `main_window` (settings IO) → `logger.debug`.
Корректность (проверено сьютом): убран двойной проход по таблицам в `template_parser`
(`.//p` уже покрывает); `FieldType` с понятной ошибкой (`schema.py`);
`KeyError` плохого листа → `[]` с логом (`data_reader`, оба ридера);
докстринг про пустые строки приведён к коду; фильтр header/footer частей
(`startswith word/header|word/footer + endswith .xml`); `row_contains_placeholder`
через regex с `re.escape`; `advanced_section` применяет `cval` при загрузке;
`run()` переиспользует `QApplication.instance()`; `_center()` гарды на `None`.
STRINGS: удалён затенённый старый трио-блок (`fill_folder_name_template/found_rows/
projects_created`); новые ключи `msg_check`, `msg_progress_*`, `msg_table_field_missing`;
`config_io` диалоги переведены на STRINGS.
Тесты: убрана тавтология (`coverage:139`), слабый assert (`template_deletion:137`),
`pytest.raises(match=)` вместо `assert False`, `nonexistent_template` реально
проверяет warning, `smoke_engine` возвращает exit 1 при провале.
`.gitignore`: убран `node_modules/`, добавлены `*.bak`/`*.tmp`.

## Находки: BLOCKER (требуют отдельных задач)
1. `gui/fill_form/config_io.py:63-66` vs `form_dialog.py:151-320` — `_load_existing_config`
   зовёт `_add_cycle_row/_add_aggr_row`, которых нет в диалоге (только в `advanced_section`)
   → `AttributeError` на проектах с циклами/агрегациями.
2. `merge.py:139` — раны с `w:br/w:drawing` теряются/съезжают в конец параграфа.
3. `xml_utils.py:46,55` — поиск плейсхолдера внутри одного рана, склейку не видит.
4. `merge.py:198` — пустые `table_data`: 0 клонов, но шаблонная строка всё равно удаляется.
5. `schema.py:335` — `directory_template` без sanitize/unique, `exist_ok` затирает проекты.
6. `render_loop.py:244` — `break` после первой картинки; `image_index` затирает media.
7. `image_utils.py:75` — нет `Override` в `[Content_Types].xml` для вставленных картинок.
8. `render_execute.py:117` — warnings теряются; пустая SEQUENTIAL-таблица рендерит мусор.
9. `generate.py:242` — flat-ветка не копирует `Данные/`, дедуп без проверки диска, откат частичный.
10. `generate.py:235,750` — мёртвый ключ `'all'` у `scan_template` + неиспользуемый параметр
    `raw_placeholders` в `_resolve_folder_name_template` (3 вызова).

## Находки: MAJOR (follow-up)
- Дубль резолва имён папок: `render_loop.py:130` vs `generate.py:291` (разный whitespace-толеранс
  и поведение при missing). Дубль entrypoint «строка→проект»: `schema.create_projects`
  vs `generate.create_projects_from_template` (разный layout). Тройной подсчёт строк:
  `renderer._compute_total_docs` vs `config_io._count_primary_rows` vs `batch_section._update_auto_info`.
- `to_file` (голый `json.dump`) vs `_atomic_write_project` (fsync) — унифицировать на атомарную.
- Engine RU-исключения (`render_execute.py:134,150`) — нужны коды/маппинг.
- `data_reader.py:69` `str(val).strip()` калечит даты/числа/bool; `:29` не различает отсутствие и битость.
- `render_loop.py:56` только первый COUNTER; `:83,112` fallback на `rows[0]` маскирует отсутствие данных.
- `generate.py:223` vs `schema.py:324`: `max_projects<=0` — все строки vs `[]`.
- `generate.py:744`: пустой `employee` сливает строки в `''`-ключ.
- GUI в главном потоке (блокировка), `QProgressDialog` без отмены, `docxforge_settings.json`
  в дереве пакета, сохранение конфига до диалога кол-ва, слабый `validate_composite_template`
  ( `/`-split, нет защиты от traversal), CLI `--field` без `--field-type` → traceback,
  CLI↔GUI паритет флагов.
- Тесты: `assert True` (`fill_form:556`), `pass`-тест (`single_row:154-202`), 93× `Document()/Workbook()`
  копипасты сетапа, дубли фикстур (`create_fixtures` vs `documents/` vs `test_project/`),
  `sample_project` function-scope + `create_all_fixtures` на каждый GUI-тест, 106 `qWait`,
  GUI-тесты без `@mark.gui`, 0 негативных на битые docx/xlsx и rollback, ~70% имён не по конвенции,
  10 скипов `nested` маскируют отсутствие парсера (`HAS_*=False`).
- `field_rows.py:211` сравнение `'counter' in type` не срабатывает на русских именах типов.

## Находки: MINOR (follow-up, вынесено из trivial)
- CLI `print()` (~50 мест: `commands/helpers/info_cmd/generate_cli`) — разделить stdout/stderr,
  решить: `logging` vs `click.echo` vs исключение в AGENTS (тест `functional:236` ассёртит stdout).
- RU-литералы мимо STRINGS: `main_window` (~10), `project_window` (~10), `advanced_section` (~15),
  `form_dialog:201`, `field_dialog:198` + опечатка-плейсхолдер «к изображение».
- `field_dialog` молчаливые `return` (пустое/дублирующее имя) — нужен warning, но сначала замокать
  в `test_gui_field_dialog:273` (иначе модалка повесит тест).
- `showMaximized()` в `__init__`, `set_run_text` в реэкспорте без внешних вызовов,
  `renderer.get_template_path` walk без кэша, `read_all_batch_sources` ключ `bsc.file`,
  `create_fixtures` global-мутация, переименование ~70% тестов, `generate_cli` оставить как есть.

## Сознательно НЕ тронуто (мотивы)
- `generate_cli` print: тест ассёртит stdout — нужно UX-решение.
- `read_all_batch_sources` ключи: 3 коллсайта используют file-ключи.
- `merge:198`, `renderer:87,124`, `generate:223,242`, `render_loop:break`, image/ContentType,
  `data_reader` типы, single COUNTER, `now/page` классификация, `showMaximized`,
  `sys.path` в `smoke_engine` (другая цель), `set_run_text` реэкспорт: меняют поведение —
  только через отдельные SPEC.
- `pytest.ini` без `pythonpath`: ini-опция в этом окружении молча не применяется (проверено),
  работает корневой `conftest.py` — не ломать.
- Замороженные `specs/000-pre-alpha/`: не тронуты.
