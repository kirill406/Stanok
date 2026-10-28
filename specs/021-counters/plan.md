# План: 021-counters

> Детализация `spec.md` → фазы A–E. Без миграции и бампа версии формата.

---

## Фаза A: Схема (`engine/schema.py`)

- `ProjectJSON.default_template: str`; валидатор `∈ templates` (пустой templates —
  не падать; конструктор ставит первый).
- `DataSourceDef`: убрать `start_row`.
- `TemplateDef.limit: int = 0`.
- `CounterDef`: одна позиция `pos: int = 0`, `resume: int = 1` (`table` уже есть);
  legacy `last`/`start_row` сводятся в `pos` при загрузке.
- `FieldDef`: убрать `table`, добавить `counter_name: str|None`.
- Model-валидация ProjectJSON: table-поле → `counter_name` есть/существует/
  `table` не `None`; `counter.table ∈ data_sources`; у каждого источника ≥1 счётчик.
- Тесты `tests/engine/test_schema.py` + фикстуры `tests/json/002-schema/*`.

## Фаза B: Движок (`engine/resolve.py`, `engine/xmlops.py` при необходимости)

- Переписать `resolve_rows` на композицию: вход — строки **всех** участвующих
  источников; вычисление `N` по §2.2; построчный выбор по `mode`; значение
  counter-поля = `pos + k` (для `constant` — `pos`).
- Убрать `_is_empty_row`-пропуск; пустая ячейка → пустое значение.
- Тесты `tests/engine/test_resolve.py`.

## Фаза C: Сервис (`services/generate.py`, `services/storage.py`)

- `generate_documents`: читать все участвующие источники шаблона; pre-flight
  колонок по источнику каждого table-поля; убрать `resume`/`resumed_from`/`skipped`;
  запись `pos` по каждому счётчику согласно `resume` (`constant` не меняется,
  circular хранит абсолютный счёт); оставить
  `default_template` при запуске без шаблона.
- `storage`: авто-создание счётчика в `init_project` и `add_source`
  (имя из stem, коллизия `_2`); удаление источника счётчики не трогает.
- `GenerateCommand`: убрать `resume`; `data_source` больше не влияет (убрать).
- CLI (`app.py`): убрать `--resume`; `--source` удалить.
- Тесты `tests/services/test_generate.py`, `test_storage.py`.

## Фаза D: Окно 2 + настройки (`gui/project_dialog.py`, `gui/create_dialog.py`, `gui/main_window.py`)

- Окно 2: убрать `PROJ_DATA` и комбобокс источников; перенести кнопки добавления
  вниз; добавить «Настройки проекта»; таблица источников `файл | тип (mode)`;
  радио `default_template`; лимит per-template из PJ; запрет удаления default
  (предупреждение «Смените шаблон по умолчанию»).
- Унифицировать создание и настройки в одном окне (режимы «создание»/«настройки»).
- Окно 1: запуск `default_template`; лимит в окне 1 **не** дублируется —
  правится в окне 2 (в строке шаблона).
- Тесты `tests/gui/test_project_dialog.py`, `test_main_window.py`, `test_create*`.

## Фаза E: Окно 3 + строки + доки

- Окно 3: «Имя файла» наверх; таблица счётчиков с колонками
  `имя | источник | формат | позиция | resume`; чекбокс `resume`
  per-counter; предупреждение при правке позиции; table-поле выбирает счётчик
  и колонку (источник из счётчика). Изменение позиции обновляет предпросмотр
  и counter-, и table-полей.
- `gui/strings.py`: новые ключи, удалить `PROJ_SOURCE*`/`PROJ_DATA`/
  `APP_RESUME_HELP`/`MAIN_RESUME`/`skipped`.
- Тесты `tests/gui/test_fields_dialog.py`, `test_strings.py`.
- Доки: `specs/spec.md` (§4.1, Правила, FR), `docs/architecture.md`,
  `CHANGELOG.md`, `specs/SUMMARY.md` → Done.

## Definition of Done

- [x] `pytest tests/ -q` — все зелёные (332), `src/` 99%
- [x] Pre-commit чистый (trufflehog3 + pytest)
- [x] Спеки (021/spec+plan), `specs/spec.md`, `docs/architecture.md`, CHANGELOG обновлены
- [x] 020 и старые спеки не переписываются
