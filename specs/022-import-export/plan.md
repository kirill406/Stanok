# План: 022-import-export

## Фаза A: Сервисы

- `ProjectStore.import_configs(folder)` + `ImportReport` в `services/storage.py`.
- Рекурсивный поиск, пропуск Home, валидация PJ до переноса, уникальные имена,
  восстановление `PJ.folder` по структуре папки, recent только для найденных.
- `services/import_export.py`: `detect_project_layout` + `ProjectLayout`.
- `_place_source`: не копировать файл, уже лежащий в целевой подпапке.

## Фаза B: GUI

- `OpenProjectDialog`: кнопка «Выбрать папку», импорт/сообщение/перечитывание
  списка, переход в `CreateDialog` с префиллом.
- `CreateDialog`: без изменений API; префилл задаёт вызывающий код.
- `MainWindow._on_browse`: `created_config` → открыть проект с
  `highlight_new=True`.
- `strings.py`: строки импорта и предупреждения.

## Фаза C: Тесты и документация

- `tests/services/test_import_export.py`: импорт, коллизии, восстановление пути,
  нечитаемые конфиги, layout.
- `tests/gui/test_open_project_dialog.py`: кнопка, импорт, префилл, ошибки.
- `tests/services/test_storage.py`: повторное использование файла из целевой папки.
- `tests/gui/test_main_window.py`: подсветка созданного проекта.
- `CHANGELOG.md`, `specs/SUMMARY.md`, `docs/architecture.md`.
