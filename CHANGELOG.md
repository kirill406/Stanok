# Журнал изменений

Все заметные изменения в этом проекте документируются в этом файле.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Добавлено
- `tables`: чтение Excel (`ExcelReader`, протокол `TableReader`, `TableReadError`); валидация заголовков, нормировка строк
- `engine.schema`: модели PJ/AJ/Filling на pydantic v2, `validate_*`, `normalize`, реестр `MIGRATIONS` + `migrate()`, `FormatTooNewError`
- `engine.resolve`: строки + PJ → Filling JSON; режимы sequential/circular/constant; счётчики plain/month; `dist` из filename_template (чистая функция, без мутации PJ)
- `engine.render` + `xmlops`: Filling → docx; run-merge с сохранением форматирования, `\n` → разрывы, таблицы (включая вложенные); строгий режим (неизвестное поле → `RenderError`)
- `services.storage`: `ProjectStore` (атомарная запись tmp+fsync+rename+`.bak`, миграция в Home, recent ≤ 10 с дедупом, защита путей)
- `services.generate`: `generate_documents(cmd)` — пайплайн tables → resolve → render → `Результат/`; `GenerateCommand`/`GenerateReport`; счётчики `last += created`, resume, `max_docs`, уникальные имена `(1)`, построчные ошибки в отчёт; CLI `python run.py <проект>`
- `gui.strings`: `STRINGS` — единый модуль пользовательских строк (NFR-3); AST-тест запрещает кириллические литералы в `src/` вне него
- `gui.main_window` + `worker`: окно 1 (recent-список, запуск по каждому/все последовательно со сводкой, настройки-заглушка, обзор); прогон в QThread, прогресс/отмена; `progress`-колбэк в `generate_documents`; `run.py` без аргументов открывает окно; PyQt5-зависимость
- `gui.project_dialog`: окно 2 (шапка проекта, таблица шаблонов с кол-вом, прогон по шаблону, хук окна 3); окно 1 открывает настоящий диалог (заглушка убрана)
- `gui.fields_dialog`: окно 3 (правка констант, превью table/counter/today, Save в PJ, dirty-чек Save/Discard/Cancel); окно 2 открывает настоящий диалог
- Тесты: `tests/tables/`, `tests/engine/test_schema.py`, `tests/engine/test_resolve.py` (покрытие движка ~99%)

### Исправлено

