# TASKS — 001-review: разбор находок REPORT.md

Конвенции: багфикс → регрессионный тест; коммит на задачу; `pytest` зелёный после каждой.
Легенда: `[ ]` todo, `[x]` done + хэш коммита.

## Blockers (по REPORT.md §BLOCKER)
- [ ] B1 `config_io:63` — `_load_existing_config` падает `AttributeError` на проектах
  с циклами/агрегациями (нет `cycles_layout` в диалоге). Файлы: `gui/fill_form/*`
- [ ] B2 `merge.py:139` — раны с `w:br/w:drawing` теряются/съезжают в конец параграфа
- [ ] B3 `xml_utils.py:46,55` — поиск плейсхолдера внутри одного рана, склейку не видит
- [ ] B4 `merge.py:198` — пустые `table_data`: шаблонная строка удаляется при 0 клонов
- [ ] B5 `schema.py:335` — `directory_template` без sanitize/unique, затирает проекты
- [ ] B6 `render_loop.py:244` — `break` после первой картинки; `image_index` затирает media
- [ ] B7 `image_utils.py:75` — нет `Override` в `[Content_Types].xml` для картинок
- [ ] B8 `render_execute.py:117` — warnings теряются; пустая таблица рендерит мусор
- [ ] B9 `generate.py:242` — flat-ветка: копировать `Данные/`, проверка диска, полный откат
- [ ] B10 `generate.py:235,750` — мёртвые `'all'`/`raw_placeholders` (3 вызова + сигнатура)

## Majors
- [ ] M1 Дубль резолва имён: `render_loop:130` vs `generate:291` → одна функция в engine
- [ ] M2 Дубль entrypoint «строка→проект»: `schema.create_projects` vs `generate.*`
- [ ] M3 Тройной подсчёт строк → переиспользовать engine-метод в GUI
- [ ] M4 `to_file` → атомарная запись как `_atomic_write_project`
- [ ] M5 Engine RU-исключения (`render_execute:134,150`) → коды/маппинг
- [ ] M6 `data_reader:69` типы ячеек; `:29` различать отсутствие/битость файла
- [ ] M7 Fallback на `rows[0]` (`render_loop:83,112`, `renderer:87`, `:124`) → `''` + warning
- [ ] M8 `max_projects<=0`: `generate:223` vs `schema:324` — единая валидация
- [ ] M9 `generate:744` пустой `employee` сливает строки
- [ ] M10 GUI в главном потоке + `QProgressDialog` без отмены
- [ ] M11 `docxforge_settings.json` в дереве пакета → QSettings/дом. каталог
- [ ] M12 Сохранение конфига до диалога + частичный откат `Projects/`
- [ ] M13 `validate_composite_template`: traversal (`../`, `<>:"/\|?*`), `a/b/c`
- [ ] M14 CLI: валидация `--field` без `--field-type`, `int(start)`, exit-коды
- [ ] M15 CLI↔GUI паритет флагов — задокументировать/добавить
- [ ] M16 Тесты: `assert True` (`fill_form:556`), `pass`-тест (`single_row:154`),
  дубли фикстур/сетапа, `scope=session`, `qWait`→`waitUntil`, `@mark.gui`, негативы
  (битые docx/xlsx, rollback, composite-детект), `field_rows:211` сравнение типов
- [ ] M17 Minors из REPORT.md §MINOR (CLI stdout/stderr, RU мимо STRINGS, `showMaximized`,
  `get_template_path` walk, `read_all` ключи, `create_fixtures` global, переименования)

## Done
_(пусто — отмечать здесь с хэшем коммита)_
