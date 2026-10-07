# План: 002-core-schema

> Детализация `spec.md` → пошаговые задачи для реализации.

---

## День 1: Зависимость + скелет моделей

### 1.1 Зависимость
```toml
# pyproject.toml
dependencies = [
    "openpyxl>=3.1.0",
    "pydantic>=2,<3",
]
```
- `uv sync` → обновить `uv.lock`

### 1.2 Файлы
```
src/stanok/engine/
├── __init__.py      # (есть) docstring-контракт
└── schema.py        # NEW: модели + validate/normalize/migrate + ошибки
```

### 1.3 Модели (по `spec.md` §2–§4)
- `FieldSource` (str, Enum): constant/table/counter/today
- `FieldDef`, `CounterDef`, `TemplateDef`, `DataSourceDef`, `ProjectJSON`
- `RecentItem`, `ApplicationJSON` (recent ≤ 10, без шаблонов/счётчиков)
- `FillingJSON` (без resume/images — только version/template/fields/dist)

---

## День 2: validate / normalize / migrate

### 2.1 validate_*
```python
def validate_pj(data: dict) -> ProjectJSON      # raises PJValidationError
def validate_aj(data: dict) -> ApplicationJSON
def validate_fj(data: dict) -> FillingJSON
```
- Неизвестные ключи — варнинг в лог, не падение (`extra="allow"` + лог).
- `..` в путях — ошибка валидации (проверка в валидаторе полей путей).

### 2.2 normalize
- Дефолты pydantic + `strip()` строковых полей.
- Отдельная функция, вызывается до `validate` в пайплайне чтения конфига.

### 2.3 migrate
```python
MIGRATIONS: dict[tuple[str, str], Callable[[dict], dict]]
def migrate(data: dict) -> dict  # цепочкой к current_version()
```
- Неизвестная/будущая версия → `FormatTooNewError`.
- `current_version()` == `stanok.__version__`.

### 2.4 Ошибки
- `SchemaError` (базовый) → `PJValidationError`, `FillingValidationError`,
  `FormatTooNewError` — все с путём к полю и контекстом для логов.

---

## День 3: Фикстуры + тесты

### 3.1 Фикстуры `tests/json/002-schema/` (есть: примеры)
Добавить:
- `pj_broken_*.stanok` — битый тип, `..` в пути, пустые заголовки-подобные кейсы
  (есть `pj_broken_type.stanok`; добавить `pj_broken_path.stanok`)
- `aj_many_recent.json` — 11 записей recent
- `migrate_0.0.0_to_0.1.0.json` — пример старой версии (когда появится 0.1.0;
  пока — пропустить, нет второй версии)

### 3.2 Тесты `tests/engine/test_schema.py`
По таблице §7 спеки: валидный парсинг, лишние ключи, битые типы,
`..`, старая/будущая версия, обрезка recent до 10, дубли recent,
граница Qt (импорт engine не тянет Qt).

### 3.3 Проверки
```bash
pytest tests/engine/test_schema.py -v   # зелёные, покрытие schema.py ≥ 90%
pytest tests/ -q                        # без регрессий
python -m truffleHog3 ...               # через pre-commit hook
grep -r "PyQt5\|stanok.gui\|HOME\|~/" src/stanok/engine/  # пусто (кроме тестовых tmp)
```

---

## Definition of Done (критерии §8 спеки)

- [ ] `pytest tests/engine/test_schema.py` — зелёные, покрытие ≥ 90%
- [ ] Импорт `ProjectJSON, validate_pj, migrate` работает
- [ ] Ошибка валидации содержит путь к полю
- [ ] Pre-commit чистый, запрещённых импортов нет
- [ ] `CHANGELOG.md [Unreleased]` — запись о фиче 002
