# PLAN Phase 5 — B3 «Падение из меню заполнения» (ветка `fix/002-fill-menu-crash`)

Источник: `specs/002-stabilization/spec.md` (блок B3), разбор — `RECON_B3.md`.
Конвенции: `logging` вместо `print`, RU-строки только через `STRINGS`, багфикс → регрессионный тест.
Зарезервировано за мной (Non-overlap, другие агенты не трогают):
`src/docxforge/gui/fill_form/config_io.py`, `src/docxforge/gui/fill_form/form_dialog.py`,
`src/docxforge/gui/project_window.py`, `tests/test_gui_fill_form.py`.
`engine/*` — только чтение. Плюс аддитивные ключи в `src/docxforge/gui/strings.py`
(новые RU-тексты диалогов; существующих ключей не хватает).

## Было / станет
| # | Было (crash) | Станет (корректное поведение) |
|---|--------------|-------------------------------|
| 1 | `_create` без `try/except` → `FileNotFoundError`, если шаблон удалили после открытия диалога | `try/except` вокруг `renderer.render`: `logging.error` + `QMessageBox.warning`, диалог жив |
| 2 | `FillForm.__init__` → `JSONDecodeError` на битом `проект.docxforge` | guard: `logging` + `QMessageBox.critical` + контролируемое `FillFormOpenError` (без сырого traceback наружу) |
| 3 | `FillForm.__init__` → `BadZipFile` на битом шаблоне; `_open_fill_form` проверяет только `exists` | guard в `__init__` + `_open_fill_form`: `zipfile.is_zipfile`-проверка и `try/except` вокруг `FillForm(...)` с `QMessageBox.warning`, без `exec_` |

## Подпункты (каждый = коммит + push)
- [x] 0. Этот план (`PLAN_Phase5.md`): коммит + `push -u origin fix/002-fill-menu-crash`
- [x] 1. Сценарий 1: `try/except` в `ConfigIOMixin._create` + новые ключи `STRINGS`
      (`msg_render_error`, `msg_project_load_error`, `msg_template_load_error`) + регрессионный тест
- [x] 2. Сценарии 2–3: guards в `FillForm.__init__` (`FillFormOpenError`, реэкспорт) + 2 регрессионных теста
- [x] 3. `_open_fill_form`: `is_zipfile`-валидация + `try/except` + регрессионные тесты (битый шаблон, битый проект, отсутствующий шаблон)
- [x] 4. Полный `pytest tests/ -q` (offscreen) зелёный → `checkout spec-002`, `pull --ff-only`,
      `merge --no-ff fix/002-fill-menu-crash`, `push origin spec-002`; при конфликте — `merge --abort`, отчёт

## Тесты
Headless: `QT_QPA_PLATFORM=offscreen`, `QMessageBox.*` замоканы (примеры — `tests/test_gui_*.py`).
Имена: `test_<module>_<scenario>_<expectation>`. База: `tests/test_gui_fill_form.py` — 37 passed.
