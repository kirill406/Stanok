# PLAN Phase 4 — B2 «Логи» (ветка feat/002-user-logs)

Spec: `specs/002-stabilization/spec.md`, блок B2.
Разрешённые файлы: logging setup (`run.py`, модуль логов) + тест логов. Чужие зоны не трогать.

## Контекст
- Сейчас `run.py` пишет общий лог в `docxforge.log` рядом с exe/скриптом:
  `log_file = os.path.join(log_dir, 'docxforge.log')` — при переустановке/запуске
  из другой папки лог теряется, имя захардкожено в `run.py`.
- Прецедент Home в репо: настройки лежат в `~/.docxforge/docxforge_settings.json`
  (`get_settings_path()` в `main_window.py`). Логи кладём рядом: `~/.docxforge/docxforge.log`.

## Подпункты
- [x] P0. План и ветка: этот файл `PLAN_Phase4.md`, коммит + `push -u origin feat/002-user-logs`.
- [x] P1. (б) Новый модуль `src/docxforge/app_logging.py`: единая константа `APP_LOG_FILE`
  (полный путь в Home) + функция `setup_app_logging()` (создаёт каталог, RotatingFileHandler
  в режиме append, формат как в `run.py`). Никакого хардкода имени/пути вне модуля.
- [x] P2. (а) `run.py` переходит на модуль: импорт `APP_LOG_FILE`/`setup_app_logging`,
  удаление локального `log_dir`/`log_file` и `basicConfig` с захардкоженным путём.
  Поведение хендлеров сохраняется (stdout + ротация 5МБ x3, utf-8).
- [x] P3. (в) Тест `tests/test_app_logging.py` (путь в Home, append после «перезапуска»,
  `run.py` без хардкода) + ручная проверка дописывания файла.
- [ ] P4. Полный сьют `pytest tests/ -q` зелёный; финал: checkout spec-002,
  pull --ff-only, merge --no-ff, push origin spec-002.

## Acceptance B2
- Общий лог пишется в файл в Home, дописывается после перезапуска.
- Путь и имя — одна константа в одном месте.
- `pytest tests/ -q` зелёный. Конвенции: `logging` вместо `print`, без хардкода RU-строк.
