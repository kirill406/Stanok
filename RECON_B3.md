# RECON B3 — Падение из меню заполнения (только разведка, кода нет)

- Дата: 2026-09-16. Ветка: `fix/002-b3-recon` (от `spec-002`).
- Окружение: Windows, Python 3.8-32, PyQt5 5.15.11, headless `QT_QPA_PLATFORM=offscreen`,
  `QMessageBox.information/warning/critical` замоканы (немодально). Проект-сэмпл собран
  `tests/create_fixtures.py::create_all_fixtures` (фикстура `all_basic_fields`).
- Базовый сценарий (открыть `FillForm(proj, 'all_fields.docx')`, нажать «Создать») — работает,
  `pytest tests/ -q` зелёный (384 passed). Падение — только на краевых условиях ниже.

## Entry points

- Окно заполнения: `FillForm` (`src/docxforge/gui/fill_form/form_dialog.py:52`,
  реэкспорт `src/docxforge/gui/fill_form/__init__.py:3`).
- Открытие из проекта: `ProjectWindow._open_fill_form`
  (`src/docxforge/gui/project_window.py:182`), слоты кнопок «Заполнить» (`:161`)
  и двойного клика по дереву (`_on_tree_double_click`, `:178`).
- Кнопка создания: `btn_create.clicked → ConfigIOMixin._create`
  (`src/docxforge/gui/fill_form/config_io.py:191`, подключение `form_dialog.py:313`).
- Движок: `Renderer.render` (`src/docxforge/engine/renderer.py:163`)
  → `execute_render` (`src/docxforge/engine/render_execute.py:27`).

## Сценарий 1 (главный B3): _create без try/except — FileNotFoundError. ВОСПРОИЗВЕДЁН

Шаги:

1. `dlg = FillForm(proj, 'all_fields.docx')` — открывается нормально.
2. Удалить/переместить `Шаблоны/all_fields.docx` (вне диалога: проводник, другой процесс,
   битый путь после переименования).
3. Нажать «Создать» (`dlg._create()`).

Полный traceback (headless, модальные диалоги замоканы):

```text
Traceback (most recent call last):
  File "<stdin>", line 32, in <module>
  File "src\docxforge\gui\fill_form\config_io.py", line 215, in _create
    outputs = self.renderer.render(
  File "src\docxforge\engine\renderer.py", line 172, in render
    return execute_render(
  File "src\docxforge\engine\render_execute.py", line 76, in execute_render
    with zipfile.ZipFile(template_path, 'r') as zf:
  File "C:\Users\kirill\AppData\Local\Programs\Python\Python38-32\lib\zipfile.py", line 1251, in __init__
    self.fp = io.open(file, filemode)
FileNotFoundError: [Errno 2] No such file or directory: 'C:\...\projB\Шаблоны\all_fields.docx'
```

Причина: обычный (документный) режим `_create` (`config_io.py:212-220`) вызывает
`self.renderer.render(...)` без `try/except` — любое исключение движка вылетает из
Qt-слота наружу (в GUI — необработанное исключение/падение). Ветка «создать проекты»
(`_create_projects_mode`, `:287-302`) и `MainWindow.generate_for_project`
(`main_window.py:492-510`) обёрнуты, а этот путь — нет. Смежно: `_create` не сохраняет
собранный конфиг перед рендером (рендер читает старый конфиг с диска), но это не краш.

## Сценарий 2: битый проект.docxforge — JSONDecodeError при открытии. ВОСПРОИЗВЕДЁН

Шаги: записать мусор в `проект.docxforge`, затем `FillForm(proj, 'all_fields.docx')`
(то же через `ProjectWindow._open_fill_form`, там нет защиты).

```text
Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
  File "src\docxforge\gui\fill_form\form_dialog.py", line 60, in __init__
    self.renderer.load_project()
  File "src\docxforge\engine\renderer.py", line 31, in load_project
    self.project = Project.from_file(project_file) if os.path.exists(project_file) else Project()
  File "src\docxforge\engine\schema.py", line 150, in from_file
    data = json.load(f)
  ...
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

## Сценарий 3: битый шаблон (не zip) — BadZipFile при открытии. ВОСПРОИЗВЕДЁН

Шаги: записать мусор в `Шаблоны/all_fields.docx`, затем `FillForm(...)`
(путь существует, поэтому guard в `_open_fill_form` (`project_window.py:187`) не срабатывает).

```text
Traceback (most recent call last):
  File "<stdin>", line 36, in <module>
  File "src\docxforge\gui\fill_form\form_dialog.py", line 62, in __init__
    self.scan_result = scan_template(self.template_path)
  File "src\docxforge\engine\template_parser.py", line 30, in scan_template
    with zipfile.ZipFile(docx_path, 'r') as zf:
  ...
zipfile.BadZipFile: File is not a zip file
```

## Проверен, НЕ падает

- Удалены `Данные/*.xlsx` + поле типа «таблица» + «Создать»: движок возвращает `outputs=[]`,
  диалог показывает предупреждение (`msg_generation_failed`). Без исключений.

## Файлы-причины (точные)

1. `src/docxforge/gui/fill_form/config_io.py` — `ConfigIOMixin._create` (`:191-238`):
   нет `try/except` вокруг `self.renderer.render` (`:215-220`) — место главного падения.
2. `src/docxforge/gui/fill_form/form_dialog.py` — `FillForm.__init__` (`:53-86`):
   `load_project()` (`:60`) и `scan_template` (`:62`) без защиты.
3. `src/docxforge/gui/project_window.py` — `ProjectWindow._open_fill_form` (`:182-193`):
   конструирует `FillForm` (`:191`) без защиты от сценариев 2–3 (проверяет только `exists`).

## Заявленные за B3 файлы (Non-overlap contract, приоритет B3)

- ЗАЯВЛЕНЫ (изменять будет только ветка `fix/002-fill-menu-crash`):
  `src/docxforge/gui/fill_form/config_io.py`,
  `src/docxforge/gui/fill_form/form_dialog.py`,
  `src/docxforge/gui/project_window.py`,
  плюс регрессионный тест (`tests/test_gui_fill_form.py`, требует спека: багфикс → тест).
- Контекст traceback, только чтение (фикс — на слое GUI, движок не трогаем):
  `src/docxforge/engine/renderer.py`, `src/docxforge/engine/render_execute.py`,
  `src/docxforge/engine/schema.py`, `src/docxforge/engine/template_parser.py`.
- Явно НЕ заявляем: `src/docxforge/engine/renderer.py` зарезервирован за B0 (фикс разрыва
  строки); `form_dialog.py` до этого никому не коммитить (B1/B4 — см. порядок захвата в спеке).
- Конвенции для фикса: `logging` вместо `print`, RU-тексты через `STRINGS`
  (напр. новый текст предупреждения), один коммит на подпункт, `pytest tests/ -q` зелёный.
