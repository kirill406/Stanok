# План реализации продукта (Feature-based)

> Источник: `specs/spec.md` (FR/NFR), `docs/architecture.md` (модули, контракты).
> Каждая фича = отдельная папка `specs/NNN-name/` со своим `spec.md` + `plan.md` + `tasks.md`.

---

## Общая структура фич

| ID | Папка | Название | Фаза | Зависит от | FR/NFR |
|------|-------|----------|------|------------|--------|
| 001 | `001-core-tables` | Чтение Excel | 1 | — | FR-1, FR-2, FR-7 |
| 002 | `002-core-schema` | Схемы PJ/AJ/FJ + валидация/миграции | 1 | 001 | FR-8, FR-10, FR-11, FR-12 |
| 003 | `003-core-resolve` | Resolve: строки + PJ → Filling JSON | 1 | 001, 002 | FR-1, FR-3, FR-4, FR-5, FR-12 |
| 004 | `004-core-render` | Render: Filling JSON → docx (run-merge) | 1 | 002, 003 | FR-1, FR-12 |
| 005 | `005-core-storage` | ProjectStore, атомарная запись, Home | 1 | 002 | FR-8, FR-11 |
| 006 | `006-core-generate` | Оркестрация генерации (end-to-end) | 1 | 003, 004, 005 | FR-1, FR-3, FR-4, FR-10, FR-12 |
| 007 | `007-gui-strings` | Единый модуль строк (NFR-3) | 2 | — | NFR-3 |
| 008 | `008-gui-main` | Main Window: выбор проекта/шаблонов, запуск | 2 | 006, 007 | FR-1, FR-2, FR-14 |
| 009 | `009-gui-project` | Project Dialog: create/open/delete | 2 | 005, 007 | FR-13, FR-14, FR-15 |
| 010 | `010-gui-fields` | Field Form: константы, выбор строки таблицы | 2 | 001, 006, 007 | FR-2 |
| 011 | `011-gui-integration` | App bootstrap + интеграция GUI | 2 | 008, 009, 010 | FR-1, FR-2, FR-14 |
| 012 | `012-batch-resume` | Batch modes + Resume + Filename templates | 3 | 003, 006 | FR-4, FR-5, FR-6 |
| 013 | `013-multi-excel` | Несколько Excel файлов на проект | 4 | 001, 003 | FR-7 |
| 014 | `014-project-ops` | Project ops: copy Data/Templates, exclude checkbox | 4 | 005, 009 | FR-13, FR-14, FR-15 |
| 015 | `015-recent-projects` | Recent projects (AJ) | 5 | 002, 011 | FR-16 |
| 016 | `016-background-gen` | Фоновая генерация + прогресс + отмена | 5 | 006, 011 | FR-17 |
| 017 | `017-gen-limits` | Лимиты генерации (max_docs, auto_docs) | 5 | 006 | FR-18 |
| 018 | `018-nfr-diagnostics` | Логирование, exc_info, диагностика | 5 | все | NFR-5 |
| 019 | `019-nfr-exe` | PyInstaller build + иконка + add-data | 5 | 011 | NFR-2 |

---

## Детальный план по фазам

### Фаза 0: Фундамент (готово)
- [x] Каркас пакетов `src/stanok/{engine,services,gui,tables}` с контрактами
- [x] Входные точки: `run.py`, `app.py`, `__main__.py`
- [x] Версия из `pyproject.toml` через `importlib.metadata`
- [x] Pre-commit: `python -m trufflehog3` + pytest
- [x] Документация: `docs/architecture.md`, `specs/spec.md`, `README.md`, `AGENTS.md`

---

### Фаза 1: Core Engine — «Excel → docx» (MVP)

#### 001-core-tables
**Спека:** `specs/001-core-tables/spec.md`
- Интерфейс `TableReader` (protocol) — `read(path) -> list[dict]`
- Реализация `ExcelReader` (openpyxl): типы, даты, пустые строки, заголовки
- Тесты: `tests/tables/test_excel.py` + фикстуры `tests/json/001-basic/`

#### 002-core-schema
**Спека:** `specs/002-core-schema/spec.md`
- Pydantic модели: `ProjectJSON`, `ApplicationJSON`, `FillingJSON`
- `validate(data) -> Model`, `normalize(data) -> Model`, `migrate(v_from, v_to, data) -> Model`
- Реестр миграций `migrations/`
- Тесты round-trip + версионирование

#### 003-core-resolve
**Спека:** `specs/003-core-resolve/spec.md`
- `resolve(rows: list[dict], pj: ProjectJSON) -> list[FillingJSON]`
- Поддержка: constant / table / counter / today / image
- Режимы строк: sequential / circular / constant
- Resume: `last_row` в PJ → продолжение с места остановки
- Тесты: `tests/json/002-counters/`, `003-loops/`, `004-resume/`

#### 004-core-render
**Спека:** `specs/004-core-render/spec.md`
- `render(fj: FillingJSON, template_path: Path) -> DocxDocument`
- Run-merge: сохранение форматирования run'ов
- Циклы таблиц (FR-12): размножение строк таблицы по данным
- Изображения (заглушка для P0, реализация в P1)
- Тесты: побайтовое сравнение с эталоном `expected.docx`

#### 005-core-storage
**Спека:** `specs/005-core-storage/spec.md`
- `ProjectStore`: `save(pj)`, `load(name)`, `delete(name)`, `list()`
- Атомарная запись: `tmp` + `.bak` + rename
- Home: `~/.stanok/<folder_name>.stanok` + миграция при открытии
- Уникальные имена: коллизии → `(1)`, `(2)` (FR-11)
- Путь Home инжектируется (тесты на tmp)

#### 006-core-generate
**Спека:** `specs/006-core-generate/spec.md`
- `generate_documents(cmd: GenerateCommand) -> GenerateReport`
- Оркестрация: tables → resolve → render → storage → docx
- Batch modes: sequential / circular / constant
- Resume: сохранение `last_row` в PJ
- Ошибки: typed exceptions (`ProjectNotFound`, `NoData`, `TemplateError`, `RenderError`)
- Интеграционные тесты: `tests/integration/test_generate_e2e.py`

**MVP Done:** `python run.py` → генерирует docx из тестового проекта.

---

### Фаза 2: GUI — Первый рабочий продукт

#### 007-gui-strings
**Спека:** `specs/007-gui-strings/spec.md`
- Единый модуль `gui/strings.py` — все русские строки
- Использование везде: `from stanok.gui.strings import S`

#### 008-gui-main
**Спека:** `specs/008-gui-main/spec.md`
- `MainWindow`: список проектов (AJ recent), выбор `.stanok`, список шаблонов
- Кнопка «Сгенерировать» → вызов `services.generate`
- Прогресс-бар + отмена (worker thread)

#### 009-gui-project
**Спека:** `specs/009-gui-project/spec.md`
- Dialog: создать проект (имя, папка, копирование Data/Templates, чекбокс «исключить копирование»)
- Открыть: выбор `.stanok` или папки → резолвер (folder → named → Home)
- Удалить проект: с подтверждением

#### 010-gui-fields
**Спека:** `specs/010-gui-fields/spec.md`
- Форма полей: константы (ручной ввод), table (выбор строки из combo), counter/today (read-only)
- Валидация на лету

#### 011-gui-integration
**Спека:** `specs/011-gui-integration/spec.md`
- `app.py`: `QApplication` → `MainWindow.show()` → `app.exec()`
- DI: проброс `ProjectStore`, `TableReader` в сервисы
- End-to-end: открыть проект → заполнить поля → «Сгенерировать» → docx в `Результат/`

**GUI Done:** Полный цикл в интерфейсе.

---

### Фаза 3: Batch & Resume

#### 012-batch-resume
**Спека:** `specs/012-batch-resume/spec.md`
- Batch modes в PJ: `sequential` / `circular` / `constant` (на уровне источника строк)
- Resume: `last_row` в PJ + `GenerateReport` с `resumed_from`
- Filename templates: маска имени из полей PJ (FR-6)

---

### Фаза 4: Multi-Excel & Project Ops

#### 013-multi-excel
**Спека:** `specs/013-multi-excel/spec.md`
- PJ: `data_sources: list[DataSourceConfig]` (путь, режим, resume)
- `ExcelReader` читает все источники → merged rows с тегами источника

#### 014-project-ops
**Спека:** `specs/014-project-ops/spec.md`
- Копирование `Data/` / `Шаблоны/` при создании проекта (FR-13)
- Чекбокс «Исключить копирование» (FR-13)
- Папка без `*.stanok` → понятная ошибка (FR-15)

---

### Фаза 5: Polish & Should

#### 015-recent-projects
**Спека:** `specs/015-recent-projects/spec.md`
- AJ: `recent: list[RecentItem]` (folder, config_name, timestamp)
- Лимит 10, автообновление при открытии/создании

#### 016-background-gen
**Спека:** `specs/016-background-gen/spec.md`
- `QRunnable` / `QThreadPool` для генерации
- Прогресс-сигналы → прогресс-бар в GUI
- Флаг отмены → корректное прерывание + сохранение resume

#### 017-gen-limits
**Спека:** `specs/017-gen-limits/spec.md`
- PJ: `max_docs`, `auto_docs` (bool)
- Остановка при достижении лимита

#### 018-nfr-diagnostics
**Спека:** `specs/018-nfr-diagnostics/spec.md`
- Логирование во всех слоях: `logging.getLogger(__name__)`
- `except Exception as e: logger.error(f'ctx: {e}', exc_info=True)`
- Лог файл: `~/.stanok/stanok.log` (RotatingFileHandler)

#### 019-nfr-exe
**Спека:** `specs/019-nfr-exe/spec.md`
- `scripts/build-exe.py` (или `.bat`) с флагами PyInstaller
- `--add-data` для шаблонов/иконки, `--icon`, `--name Станок`
- Проверка на чистой Windows

---

## Правила работы с фичами

1. **Одна фича = одна ветка** `feat/NNN-name`
2. **Сначала `spec.md`** в `specs/NNN-name/` — согласовать перед кодом
3. **Потом `plan.md`** — разбивка на задачи
4. **Потом код + тесты** в одной ветке
4. **PR → develop** через squash merge после CI (pytest + trufflehog3)
5. **После мержа** — перенести знания в `docs/` + `AGENTS.md`, обновить `CHANGELOG.md`

---

## Порядок запуска (критический путь)

```
001 → 002 → 003 → 004 → 005 → 006  (Core Engine MVP)
                          ↘
                           007 → 008 → 009 → 010 → 011  (GUI)
                                             ↘
                                              012 → 013 → 014  (Batch, Multi-Excel, Ops)
                                                                     ↘
                                                                      015 → 016 → 017 → 018 → 019  (Polish)
```

---

## Следующий шаг

Создать `specs/001-core-tables/spec.md` — детальная спецификация чтения Excel.
После согласования — `plan.md` + `tasks.md` в той же папке, затем реализация.

---

*План живое: при изменении скоупа — править здесь и в `CHANGELOG.md [Unreleased]`.*