# TASKS — 001-review: разбор находок REPORT.md

Конвенции: багфикс → регрессионный тест; коммит на задачу; `pytest` зелёный после каждой.
Легенда: `[ ]` todo, `[x]` done + хэш коммита.

## Blockers (по REPORT.md §BLOCKER)
- [x] B1 `config_io:63` — `_load_existing_config` падает `AttributeError` на проектах
  с циклами/агрегациями (нет `cycles_layout` в диалоге). Файлы: `gui/fill_form/*`
  → done в `ac189a8` (регрессия: `tests/test_review_gui_fixes.py::TestReviewB1CyclesLoad`)
- [x] B2 `merge.py:139` — раны с `w:br/w:drawing` теряются/съезжают в конец параграфа
  → done в `de26475` (регрессия: `tests/test_review_render_fixes.py::TestReviewB2BrRunsKeptInPlace`)
- [x] B3 `xml_utils.py:46,55` — поиск плейсхолдера внутри одного рана, склейку не видит
  → done в `de26475` (регрессия: `TestReviewB3SplitPlaceholderInRow`)
- [x] B4 `merge.py:198` — пустые `table_data`: шаблонная строка удаляется при 0 клонов
  → done в `de26475` (регрессия: `TestReviewB4EmptyTableDataKeepsRow`)
- [x] B5 `schema.py:335` — `directory_template` без sanitize/unique, затирает проекты
  → done в `c762877` (регрессия: `tests/test_review_gen_fixes.py::TestReviewB5SchemaDirectoryTemplate`)
- [x] B6 `render_loop.py:244` — `break` после первой картинки; `image_index` затирает media
  → done в `de26475` (регрессия: `TestReviewB6MultipleImagesUnique`)
- [x] B7 `image_utils.py:75` — нет `Override` в `[Content_Types].xml` для картинок
  → done в `de26475` (регрессия: `TestReviewB7ContentTypeOverride`)
- [x] B8 `render_execute.py:117` — warnings теряются; пустая таблица рендерит мусор
  → done в `de26475`+`c762877` (фикс в `de26475`, регрессия `TestReviewB8EmptySequentialRendersNothing` в `c762877`)
- [x] B9 `generate.py:242` — flat-ветка: копировать `Данные/`, проверка диска, полный откат
  → done в `c762877` (регрессия: `TestReviewB9FlatBranch`)
- [x] B10 `generate.py:235,750` — мёртвые `'all'`/`raw_placeholders` (3 вызова + сигнатура)
  → done в `c762877` (регрессия: `TestReviewB10DeadCodeRemoved` + правки `tests/test_nested_projects.py`)

## Majors
- [x] M1 Дубль резолва имён: `render_loop:130` vs `generate:291` → одна функция в engine
  → done в `fix/001-m1-folder-resolve` (`602a598`, ядро `schema.substitute_placeholders`,
  регрессия `tests/test_m1_folder_resolve.py::TestM1SingleCore`)
- [x] M2 Дубль entrypoint «строка→проект»: `schema.create_projects` vs `generate.*`
  → done: точки входа оставлены (разные layout/семантика: engine-API vs полный пайплайн),
  контракт унифицирован (общее ядро B5/M1/M8) + кросс-ссылки в докстрингах +
  контракт-тест `tests/test_m2_contract.py`
- [x] M3 Тройной подсчёт строк → переиспользовать engine-метод в GUI
  → done в `fix/001-m-gui-batch` (`9a9fa3e`, `Renderer.count_source_rows`,
  регрессия `tests/test_m_gui_batch.py::TestM3SingleRowCount`)
- [x] M4 `to_file` → атомарная запись как `_atomic_write_project`
  → done в `fix/001-m4-atomic-errors` (`f0681af`, регрессия `tests/test_m4_atomic_errors.py`)
- [x] M5 Engine RU-исключения (`render_execute:134,150`) → коды/маппинг
  → done в `fix/001-m4-atomic-errors` (`f0681af`, `engine/errors.py`)
- [x] M6 `data_reader:69` типы ячеек; `:29` различать отсутствие/битость файла
  → done в `fix/001-m6-data-reader` (`8c8fccf`, `_coerce_cell` + `FileNotFoundError`,
  регрессия `tests/test_m6_data_types.py`; тест `numeric_values_become_strings`
  обновлён под новый контракт)
- [x] M7 Fallback на `rows[0]` (`render_loop:83,112`, `renderer:87`, `:124`) → `''` + warning
  → done в `fix/001-m6-data-reader` (`8c8fccf`); batch-путь даёт `''`+warning,
  дефолт без batch-конфигов (rows[0]) и плейсхолдер при полном отсутствии данных
  сохранены как запиненное поведение
- [x] M8 `max_projects<=0`: `generate:223` vs `schema:324` — единая валидация
  → done в `fix/001-m1-folder-resolve` (`602a598`, `schema.limit_rows`: None/<=0 = все;
  тест `test_max_projects_zero` обновлён)
- [x] M9 `generate:744` пустой `employee` сливает строки
  → done в `fix/001-m1-folder-resolve` (`602a598`, `unassigned_<row>` + warning)
- [x] M10 GUI в главном потоке + `QProgressDialog` без отмены
  → done в `fix/001-m-gui-batch` (`9a9fa3e`, `gui/worker.py::GenerateWorker` для
  пакетной генерации, честная отмена между проектами; одиночные вызовы оставлены
  синхронными сознательно — у движка нет чекпоинтов, отмена была бы фейковой)
- [x] M11 `docxforge_settings.json` в дереве пакета → QSettings/дом. каталог
  → done в `fix/001-m-gui-batch` (`9a9fa3e`, `~/.docxforge/` + разовая миграция)
- [x] M12 Сохранение конфига до диалога + частичный откат `Projects/`
  → done в `fix/001-m-gui-batch` (`9a9fa3e`, save после диалога + снапшот/восстановление)
- [x] M13 `validate_composite_template`: traversal (`../`, `<>:"/\|?*`), `a/b/c`
  → done в `ac189a8` (регрессия: `tests/test_review_gui_fixes.py::TestReviewM13CompositeValidation`)
- [x] M14 CLI: валидация `--field` без `--field-type`, `int(start)`, exit-коды
  → done в `fix/001-m14-cli` (`e0d33b0`, exit 2/1 + stderr, `--multiplier`,
  регрессия `tests/test_m14_cli.py`; по пути починены двойные юникод-эскейпы)
- [x] M15 CLI↔GUI паритет флагов — задокументировать/добавить
  → done в `fix/001-m14-cli` (`e0d33b0`, `docs/cli-gui-parity.md`)
- [x] M16 Тесты: `assert True` (`fill_form:556`), `pass`-тест (`single_row:154`),
  дубли фикстур/сетапа, `scope=session`, `qWait`→`waitUntil`, `@mark.gui`, негативы
  (битые docx/xlsx, rollback, composite-детект), `field_rows:211` сравнение типов
  → done в `fix/001-m16-tests` (`7d177a5`: ассёрты, pass-тест, `@mark.gui`,
  `tests/test_m16_negatives.py`, фикс типов, `base_dir` без global; массовые
  переименования/session-скоп/migration qWait — сознательно вне скоупа)
- [x] M17 Minors из REPORT.md §MINOR (CLI stdout/stderr, RU мимо STRINGS, `showMaximized`,
  `get_template_path` walk, `read_all` ключи, `create_fixtures` global, переименования)
  → done в `fix/001-m16-tests` (`7d177a5`: stderr, STRINGS-синглы, warnings,
  `show()`, кэш пути, фикстуры; RU-балк main/project/advanced ~70 литералов,
  `read_all` ключи, массовые переименования — follow-up)

## Done
- B1 — `ac189a8`
- B2,B3,B4,B6,B7 — `de26475`
- B8 — фикс `de26475`, тесты `c762877`
- B5,B9,B10 — `c762877`
- M13 — `ac189a8`
- M4,M5 — `f0681af` (ветка `fix/001-m4-atomic-errors`, F4)
- M14,M15 — `e0d33b0` (ветка `fix/001-m14-cli`, F6)
- M1,M8,M9 — `602a598` (ветка `fix/001-m1-folder-resolve`, F2)
- M6,M7 — `8c8fccf` (ветка `fix/001-m6-data-reader`, F3)
- M3,M10,M11,M12 — `9a9fa3e` (ветка `fix/001-m-gui-batch`, F5)
- M16,M17 — `7d177a5`+`6fa7ac0` (ветка `fix/001-m16-tests`, F7; влита M6-ветка как зависимость)
- M2 — контракт-тест `tests/test_m2_contract.py` (FirstAgent, поверх мержей)
- Статус: `pytest tests/ -q` → 377 passed (261 baseline + 116 новых)
- Follow-up (сознательно вне скоупа): RU-балк main/project/advanced (~70 литералов),
  `read_all` ключи, массовые переименования тестов, session-скоп фикстур, qWait-миграция
