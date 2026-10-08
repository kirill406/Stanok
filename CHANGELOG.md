# Журнал изменений

Все заметные изменения в этом проекте документируются в этом файле.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Добавлено
- `tables`: чтение Excel (`ExcelReader`, протокол `TableReader`, `TableReadError`); валидация заголовков, нормировка строк
- `engine.schema`: модели PJ/AJ/Filling на pydantic v2, `validate_*`, `normalize`, реестр `MIGRATIONS` + `migrate()`, `FormatTooNewError`
- `engine.resolve`: резолв строк Excel + PJ → Filling JSON; режимы sequential/circular/constant; счётчики plain/month; resume; `filename_template` → `dist`
- Тесты: `tests/tables/`, `tests/engine/test_schema.py`, `tests/engine/test_resolve.py` (покрытие движка ~99%)

### Исправлено

