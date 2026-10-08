# Спецификация: 005-core-storage — ProjectStore, атомарная запись, Home

**Статус:** Draft
**Версия:** 0.1.0
**Фаза:** 1 (Core Engine)
**Зависит от:** 002-core-schema (ProjectJSON), 004-core-render (Document)
**FR:** FR-8, FR-11
**NFR:** NFR-2, NFR-4

---

## 1. Назначение

Единственный модуль для работы с файловой системой проекта:
- чтение/запись ProjectJSON (`<имя>.stanok`) в `~/.stanok/`;
- атомарная запись через `tmp + rename` + `.bak`;
- управление миграцией конфигов из папки проекта в `~/.stanok/`;
- список недавних проектов (AJ), лимит 10;
- безопасность путей: запрет `..`, абсолютных путей, traversal.

Библиотека: `python-dotenv` для настроек, `pathlib` + `shutil` для FS.

---

## 2. Архитектурные решения

### 2.1 ProjectStore

```python
# src/stanok/services/storage.py
class ProjectStore:
    def __init__(self, home_dir: Path | None = None):
        ...

    def save(self, pj: ProjectJSON) -> Path:
        """Атомарно записать конфиг в ~/.stanok/<имя>.stanok, вернуть путь."""

    def load(self, name: str) -> ProjectJSON:
        """Прочитать конфиг из ~/.stanok/<имя>.stanok, валидировать."""

    def delete(self, name: str) -> None:
        """Удалить конфиг из Home (файл + .bak)."""

    def list(self) -> list[ProjectJSON]:
        """Список всех конфигов в Home (сортировка по mtime)."""

    def migrate_from_project(self, project_dir: Path) -> ProjectJSON:
        """Прочитать старый конфиг из папки проекта, мигрировать, сохранить в Home."""
```

### 2.2 Резолвер проекта (Resolver)

```python
def resolve_project(ref: str | Path, store: ProjectStore) -> tuple[ProjectJSON, Path]:
    """
    Разрешить ссылку на проект:
    - абсолютный/относительный путь к папке проекта
    - имя конфига в Home
    - отсутствие -> поиск по имени папки в Home
    Возвращает (ProjectJSON, путь к конфигу).
    """
```

### 2.3 ApplicationJSON (AJ) в `~/.stanok/settings.json`

```python
class ApplicationJSON:
    version: str
    recent: list[RecentItem]  # limit 10, LRU, дедуп по (folder, config)
    settings: dict[str, Any]  # UI-настройки, без шаблонов/счётчиков
```

`RecentItem`: `folder` (путь к проекту), `config` (имя конфига в Home), `opened_at`.

---

## 3. Контракты

### 3.1 Файл проекта `<имя>.stanok` в `~/.stanok/`

JSON по схеме `ProjectJSON` (спека 002). Поле `version` == версии приложения.
Ломающие изменения → миграция через `MIGRATIONS` (спека 002).

### 3.2 Файл настроек `~/.stanok/settings.json`

JSON по схеме `ApplicationJSON`. Версия = версии приложения.
`recent` — упорядочены по `opened_at` (свежие сверху), лимит 10.
Дубликаты `(folder, config)` схлопываются, свежий сверху.

### 3.3 Атомарность записи

- Запись во временный файл `*.tmp` в той же директории.
- `fsync()`, затем `rename()` (атомарно на POSIX, на Windows — replace).
- При успехе — старый файл → `.bak`, новый → целевой.
- При ошибке — `.tmp` удаляется, оригинал не тронут.

### 3.4 Безопасность путей

- Абсолютные пути запрещены (исключение: `home_dir` из конфига).
- `..` в путях — ошибка `StorageError`.
- Символические ссылки — `resolve()` с проверкой, что результат внутри `home_dir`.

---

## 4. Требования к реализации

| ID | Требование | Приоритет |
|----|------------|-----------|
| STR-1 | `save/load/delete/list` для конфигов | Must |
| STR-2 | Атомарная запись (`tmp + fsync + rename + .bak`) | Must |
| STR-3 | `resolve_project` с поддержкой путей/имён | Must |
| STR-4 | `ApplicationJSON` с лимитом 10, дедуп `(folder, config)` | Must |
| STR-5 | Миграция конфига из папки проекта в Home | Must |
| STR-6 | Валидация путей: запрет `..`, абсолютных, traversal | Must |
| STR-7 | Чтение/запись AJ с лимитом 10, дедуп по `(folder, config)` | Must |
| STR-8 | Ошибки: `StorageError(path, errors)` с путём к полю | Must |
| STR-9 | Покрытие тестами ≥ 90% | Must |

---

## 5. Тестирование

Файл: `tests/services/test_storage.py`. Фикстуры: `tests/json/005-storage/`.

| Сценарий | Ожидаемое поведение |
|----------|---------------------|
| Сохранение/чтение PJ | `save(pj)` → `load(name)` = исходный PJ |
| Атомарность при ошибке | Ошибка на этапе write → `.tmp` удалён, `.bak` и оригинал целы |
| Конкурентная запись | Два потока `save` → один побеждает, второй перезаписывает (файловый lock опционально) |
| Resolve: путь к папке → PJ | Поиск `.stanok` в папке → миграция в Home → возврат PJ |
| Resolve: имя в Home | Прямое чтение из Home |
| Resolve: имя папки → поиск в Home | Поиск по имени папки среди конфигов в Home |
| AJ: recent limit 10 | 11-й проект вытесняет первый |
| AJ: дедуп (folder, config) | Повторное открытие поднимает запись наверх |
| Путь с `..` / абсолютный | `StorageError("path", [...])` |
| Атомарность при ошибке записи | Имитация ошибки на `write` → `.tmp` удалён, оригинал не тронут |

---

## 6. Критерии приёмки

1. `pytest tests/services/test_storage.py -v` — зелёные, покрытие `storage.py` ≥ 90%.
2. `from stanok.services.storage import ProjectStore, resolve_project, StorageError` — работает.
3. Pre-commit чистый, `pytest tests/ -q` — зелёные.
4. Pre-commit: `python -m trufflehog3 --no-history . --exclude venv uv.lock` — чисто.

---

## 7. Риски

| Риск | Митигация |
|------|-----------|
| Windows: `rename` не атомарен при открытом файле | `try/except`, fallback на `replace` + `os.unlink` |
| Конкурентная запись без lock | Файловый lock (`fcntl`/`msvcrt`) опционально; документация |
| Путь Home на диске с иной кодировкой | `pathlib.Path` + `utf-8`; тесты на кириллице |
| Пользователь перенёс папку Home | `home_dir` настраивается через env/конфиг, дефолт `~/.stanok` |