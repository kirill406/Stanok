# Задачи: 002-core-schema

> Порядок выполнения — сверху вниз. Каждая группа → коммит.

---

## 1. Подготовка

- [ ] 1.1 Добавить `pydantic>=2,<3` в `pyproject.toml` → `dependencies`
- [ ] 1.2 `uv sync` — обновить окружение и `uv.lock`

---

## 2. Модели (`src/stanok/engine/schema.py`)

- [ ] 2.1 `FieldSource`, `FieldDef`, `CounterDef`, `TemplateDef`,
  `DataSourceDef`, `ProjectJSON`
- [ ] 2.2 `RecentItem`, `ApplicationJSON` (recent ≤ 10 через валидатор)
- [ ] 2.3 `FillingJSON` (version/template/fields/dist, без resume/images)
- [ ] 2.4 Валидатор путей: относительные, запрет `..`

---

## 3. Функции и ошибки

- [ ] 3.1 `validate_pj / validate_aj / validate_fj`
- [ ] 3.2 `normalize_*` (дефолты/trim) отдельно от validate
- [ ] 3.3 `MIGRATIONS` + `migrate()` + `current_version()`
- [ ] 3.4 `SchemaError`, `PJValidationError`, `FillingValidationError`,
  `FormatTooNewError` (с путём к полю)

---

## 4. Фикстуры `tests/json/002-schema/`

- [x] 4.1 Примеры: `pj_minimal`, `pj_full`, `aj_example`, `fj_example` (есть)
- [ ] 4.2 Негативные: `pj_broken_path.stanok` (`..` в пути)
- [ ] 4.3 `aj_many_recent.json` (11 записей)

---

## 5. Тесты `tests/engine/test_schema.py`

- [ ] 5.1 Валидный PJ/AJ/FJ парсится
- [ ] 5.2 Лишние ключи — варнинг, парсинг ок
- [ ] 5.3 Битый тип → ошибка с путём к полю
- [ ] 5.4 `..` в пути → ошибка
- [ ] 5.5 Будущая версия → `FormatTooNewError`
- [ ] 5.6 AJ: обрезка до 10 + схлопывание дублей recent
- [ ] 5.7 Граница: импорт engine не тянет Qt

---

## 6. Проверки и документация

- [ ] 6.1 `pytest tests/engine/ -v` — зелёные, покрытие ≥ 90%
- [ ] 6.2 `pytest tests/ -q` — без регрессий
- [ ] 6.3 Pre-commit hook — чисто
- [ ] 6.4 `CHANGELOG.md [Unreleased]` — запись о фиче 002
- [ ] 6.5 Push в `feat/002-core-schema`, MR в `develop`
