# Спецификация: 018-observability — Лог и настройки (NFR-5, §7.1)

**Статус:** done
**Версия:** 0.1.0
**Фаза:** 5 (Надёжность)
**Зависит от:** 005-core-storage (AJ/settings.json), 008-gui-main (кнопка настроек)
**FR:** — (NFR-работа)
**NFR:** NFR-3, NFR-5

## 1. Цель

Два висящих хвоста: spec.md §7.1 требует `~/.stanok/stanok.log` (ротация,
переживает перезапуск) — сейчас только консоль; кнопка «Настройки» — стаб.
018 закрывает оба: файловый лог с уровнем из настроек и настоящее окно настроек.

## 2. Контракт

### 2.1 Лог (`app._setup_logging`, идемпотентный)

- Файл `stanok.log` в Home: `RotatingFileHandler` (1 МБ × 3 бэкапа).
- Консольный хендлер остаётся (CLI-режим).
- Уровень корня — из `AJ.settings["log_level"]` (default `INFO`); чтение
  после создания Home.
- Home: `Path.home()/".stanok"`, переопределяется `STANOK_HOME` (тесты,
  portable-режим); новая переменная → строка в `.env.example` (пустая).
- Формат: `%(asctime)s %(levelname)s %(name)s: %(message)s`.

### 2.2 Настройки AJ (`ProjectStore`)

```python
def get_setting(self, key: str, default=None)
def set_setting(self, key: str, value) -> None  # dump AJ целиком, атомарно
```

### 2.3 Окно настроек (модальное из окна 1, вместо стаба)

- Комбобокс уровня лога (DEBUG/INFO/WARNING/ERROR) → `set_setting` + живое
  применение (`logging.getLogger().setLevel`); инфо-лейблы: Home-путь, версия
  (`stanok.__version__`), путь лога; кнопка «открыть папку логов».
- `MAIN_SETTINGS_STUB` удаляется. Строки `SET_*` в STRINGS (NFR-3).

## 3. Тесты (NFR-4)

- `_setup_logging` в tmp-Home через `STANOK_HOME`: файл создан, запись INFO
  в файле, повторный вызов хендлеры не дублирует.
- Уровень из AJ применяется ((nil → INFO; `"WARNING"` → WARNING).
- `get/set_setting` round-trip; окно настроек сохраняет уровень в AJ.

## 4. Вне скоупа

- Просмотр лога внутри приложения; ротация настроек по версиям.
- Другие настройки (каталог Результата и т.п.) — по мере FR.
