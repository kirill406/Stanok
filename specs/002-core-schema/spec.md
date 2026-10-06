# Спецификация: 002-core-schema — Схемы PJ/AJ/FJ

**Статус:** Draft
**Версия:** 0.1.0
**Фаза:** 1 (Core Engine)
**Зависит от:** 001-core-tables (типы строк), план `specs/plan.md`
**FR:** FR-6, FR-8, FR-10, FR-11
**NFR:** NFR-4

---

## 1. Назначение

Типизированные контракты всех JSON-форматов продукта в одном месте
(`src/stanok/engine/schema.py`): проект (PJ), приложение (AJ), заполнение (filling, FJ).
Здесь же — валидация, нормализация и реестр миграций между версиями формата.
Версия формата = версия приложения (единый счётчик, решение 4
в `docs/architecture.md`).

Библиотека: `pydantic` (v2) — валидация из коробки, понятные ошибки,
JSON Schema бесплатно.

---

## 2. Модель ProjectJSON (PJ) — `<имя>.stanok`

```python
class FieldSource(str, Enum):
    CONSTANT = "constant"    # значение вбито в конфиг / GUI
    TABLE = "table"          # строка таблицы
    COUNTER = "counter"      # счётчик проекта
    TODAY = "today"          # текущая дата
    IMAGE = "image"          # картинка (путь к файлу)

class FieldDef(BaseModel):
    source: FieldSource
    value: Any = None        # для CONSTANT — само значение; для TABLE — имя колонки

class CounterDef(BaseModel):
    last: int = 0
    format: str = "plain"    # plain | month (ГГГГ-ММ-###)

class TemplateDef(BaseModel):
    file: str                # относительный путь в Шаблоны/
    fields: dict[str, FieldDef]

class DataSourceDef(BaseModel):
    file: str                # относительный путь в Данные/
    mode: str = "sequential" # sequential | circular | constant
    start_row: int = 0       # resume: с какой строки продолжать

class ProjectJSON(BaseModel):
    version: str             # == версии приложения
    templates: dict[str, TemplateDef]
    data_sources: list[DataSourceDef] = []
    counters: dict[str, CounterDef] = {}
    filename_template: str = "{template} ({i})"  # FR-6
```

Правила:
- `version` обязателен; несовпадение с версией приложения → миграция
  (известная версия) или явная ошибка «обновите программу» (см. §5).
- Неизвестные ключи — варнинг в лог, не падение (форвард-совместимость).
- Пути — только относительные, `..` запрещён (path traversal → ошибка
  валидации, тест).

---

## 3. Модель ApplicationJSON (AJ) — `~/.stanok/settings.json`

```python
class RecentItem(BaseModel):
    folder: str              # путь к папке проекта
    config: str              # имя конфига в Home
    opened_at: datetime

class ApplicationJSON(BaseModel):
    version: str
    recent: list[RecentItem] = []   # лимит 10, свежие сверху (FR-16)
    settings: dict[str, Any] = {}  # настройки приложения, БЕЗ шаблонов/счётчиков
```

Правила:
- Шаблоны и счётчики живут только в PJ, никогда в AJ.
- Переименование `<имя>.stanok` в Home вручную — unsupported; рассинхрон
  recent-записи лечится резолвером по папке (см. проблему 10 в архитектуре).

---

## 4. Модель FillingJSON (FJ) — единственный вход рендера

```python
class FillingJSON(BaseModel):
    version: str
    template: str            # какой шаблон рендерить
    fields: dict[str, Any]   # разрешённые {поле: значение} — уже строки/числа/даты
    images: dict[str, str] = {}  # {поле: путь к файлу} (позже)
    resume: dict[str, Any] = {}  # мета продолжения: source, last_row
```

Правила (FR-10):
- Рендер принимает **только** валидный FJ; сырые dict'ы из Excel — никогда.
- Невалидный FJ → `FillingValidationError` с путём к полю
  (`fields.Возраст: expected int`), а не `KeyError` в глубине рендера.

---

## 5. Функции: validate / normalize / migrate

```python
def validate_pj(data: dict) -> ProjectJSON  # raises PJValidationError
def validate_aj(data: dict) -> ApplicationJSON
def validate_fj(data: dict) -> FillingJSON

def normalize_pj(raw: dict) -> dict   # дефолты, trim строк, сортировка ключей
def current_version() -> str          # == stanok.__version__

MIGRATIONS: dict[tuple[str, str], Callable[[dict], dict]]  # (from, to) -> data
def migrate(data: dict) -> dict       # цепочка миграций к current_version;
                                      # неизвестная версия -> FormatTooNewError
```

Ошибки (типизированные, с контекстом для логов):
- `SchemaError` — базовый класс слоя.
- `PJValidationError(SchemaError)` — поля `path`, `errors`.
- `FillingValidationError(SchemaError)` — то же для FJ.
- `FormatTooNewError(SchemaError)` — «обновите программу».

---

## 6. Требования к реализации

| ID | Требование | Приоритет |
|----|------------|-----------|
| SCH-1 | Pydantic v2 модели PJ/AJ/FJ в `engine/schema.py` | Must |
| SCH-2 | `validate_*` с типизированными ошибками (путь к полю в сообщении) | Must |
| SCH-3 | `normalize` (дефолты/trim) отделён от `validate` | Must |
| SCH-4 | Реестр `MIGRATIONS` + `migrate()` цепочкой; неизвестная версия → `FormatTooNewError` | Must |
| SCH-5 | Относительные пути, запрет `..` | Must |
| SCH-6 | AJ: лимит recent 10, без шаблонов/счётчиков | Must |
| SCH-7 | Никаких Qt/GUI/Home-путей в модуле (чистый engine) | Must |
| SCH-8 | Покрытие ≥ 90% | Must |

---

## 7. Тестирование

Файл: `tests/engine/test_schema.py`. Фикстуры: `tests/json/002-schema/`
(`pj_minimal.stanok`, `pj_full.stanok`, `pj_broken_*.stanok`, `aj_*.json`,
`fj_*.json`, по одному файлу на миграцию `migrate_<from>_to_<to>.json`).

| Сценарий | Ожидаемое поведение |
|----------|---------------------|
| Валидный PJ/AJ/FJ | Парсится, `version` совпадает |
| Лишние ключи | Варнинг в лог, парсинг ок |
| Битый тип поля | `*ValidationError` с путём к полю |
| `..` в пути | Ошибка валидации |
| Старая версия PJ | `migrate()` доводит до текущей, round-trip ок |
| Версия из будущего | `FormatTooNewError` |
| AJ с 11 recent | Обрезается до 10 |
| Импорт engine тянет Qt | Тест границы (действует и здесь) |

---

## 8. Критерии приёмки

1. `pytest tests/engine/test_schema.py` — зелёные, покрытие `schema.py` ≥ 90%.
2. `from stanok.engine.schema import ProjectJSON, validate_pj, migrate` — ок.
3. Невалидный конфиг даёт ошибку с путём к полю, а не traceback pydantic наружу.
4. `python -m trufflehog3` / pre-commit — чисто.
5. В модуле нет импортов Qt, gui, services, путей Home.

---

## 9. Риски

| Риск | Митигация |
|------|-----------|
| Pydantic v2 меняет API минорами | Пин `pydantic>=2,<3`, тесты на наши модели |
| Миграции плодятся с каждой версией | Реестр + тест на каждую пару (from, to), squash старых при 1.0 |
