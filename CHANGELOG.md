# Журнал изменений

Все заметные изменения в этом проекте документируются в этом файле.
Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Добавлено
- `tables`: чтение Excel (`ExcelReader`, протокол `TableReader`, `TableReadError`); валидация заголовков, нормировка строк
- `engine.schema`: модели PJ/AJ/Filling на pydantic v2, `validate_*`, `normalize`, реестр `MIGRATIONS` + `migrate()`, `FormatTooNewError`
- Тесты: `tests/tables/`, `tests/engine/test_schema.py` (покрытие движка ~99%)

### Исправлено

