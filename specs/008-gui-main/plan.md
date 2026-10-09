# План: 008-gui-main

> Детализация `spec.md` → шаги реализации.

---

## Шаг 1: Зависимости

- `pyproject.toml` += `PyQt5>=5.15`, `uv sync` → `uv.lock`.
- Проверка: `QT_QPA_PLATFORM=offscreen python -c "import PyQt5.QtWidgets"`.

## Шаг 2: generate + progress-колбэк (MAIN-8)

- `GenerateCommand` без изменений; `generate_documents(..., progress=None)`.
- Вызов колбэка после каждого созданного документа; `True` → стоп, частичный отчёт.
- Тесты: отмена после 1-го документа, без колбэка — поведение 006.

## Шаг 3: worker + окно (MAIN-1…4)

- `gui/worker.py`: `GenerateWorker(QThread)`, сигналы `progress/finished/failed`.
- `gui/main_window.py`: макет §2.2, recent + обзор, dropdown, resume/limit,
  прогресс-диалог с отменой, итоги и ошибки — `QMessageBox`.
- `gui/strings.py`: ключи `MAIN_*`.

## Шаг 4: app.main + тесты

- Без аргументов → окно; с `project_ref` → CLI (регрессия 006).
- `tests/gui/test_main_window.py` (offscreen), AST-охранник, полный сьют.

## Definition of Done

- [ ] `QT_QPA_PLATFORM=offscreen pytest tests/gui/ -v` — зелёные
- [ ] `pytest tests/ -q` — все зелёные
- [ ] Ручной прогон окна на Windows
- [ ] Pre-commit чистый, CHANGELOG — запись о 008
