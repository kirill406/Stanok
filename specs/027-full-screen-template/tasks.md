# Задачи: 027-full-screen-template

Каждая задача — отдельный коммит с тестами. Порядок важен: раскладка → виджеты → редактор → окно.

1. [x] `services/template_layout.py`: модели и разбор абзаца (текст, стиль, поля, `w:br`, `w:br type=page`).
2. [x] Раскладка: абзацы (выравнивание, отступы, интервалы, наследование стиля, `docDefaults`), таблицы, колонтитулы, `pageBreakBefore`.
3. [x] Тесты раскладки на docx, созданных в тесте (`python-docx`).
4. [x] `gui/template_sheet.py`: `FlowLayout`, абзац, строка, кнопка поля, сигнал `fieldClicked`.
5. [x] `gui/template_sheet.py`: таблица, колонтитулы, разрыв страницы, размеры страницы.
6. [x] `gui/source_data.py`: вынос чтения строк и заголовков, восстановление источника (из `fields_dialog.py`).
7. [x] `gui/field_editor.py`: тип и значение поля (константа, таблица, счётчик, дата).
8. [x] `gui/field_editor.py`: блок счётчика — источник, формат, позиция, «Заново», создание, удаление, сквозной — только чтение.
9. [x] `gui/fields_dialog.py`: новое окно на весь экран, `TemplateSheet`, кнопки полей, поля вне документа, сохранение.
10. [x] Удалить старые таблицы полей и счётчиков; обновить `test_global_counters.py`, `test_integration.py`, `test_project_dialog.py`.
11. [x] Строки интерфейса в `STRINGS`; тест `test_strings.py`.
12. [x] `CHANGELOG.md [Unreleased]`, `docs/architecture.md`, `README.md` (если описано окно 3), спека → Done.
13. [x] Проверка на экране (скриншот `grabWindow`), пересборка exe в `dist/`.

## Дополнение: правка текста

14. [ ] `services/template_edit.py`: чтение текста абзаца, `set_paragraph_text` с диффом и сохранением оформления соседнего фрагмента, `TemplateEditError` для абзацев с гиперссылкой и правками.
15. [ ] `services/template_edit.py`: `TemplateDocument` — открыть, раскладка, правка, сохранение с `.bak` и атомарной записью.
16. [ ] `services/template_layout.py`: абзац хранит ссылку на XML (`element`), публичные `iter_run_elements` и `run_chars`.
17. [ ] `gui/template_sheet.py`: двойной щелчок → редактор абзаца (`QPlainTextEdit`), Esc отменяет, уход фокуса применяет; `set_layout` перестраивает страницу с сохранением прокрутки.
18. [ ] `gui/fields_dialog.py`: держит `TemplateDocument`, применяет правку, помечает окно изменённым, Save пишет `.docx` и проект.
19. [ ] Тесты: services (оформление, дифф, сохранение, `.bak`), gui (двойной щелчок, Esc, применение), окно (Save пишет docx).
20. [ ] Строки (`TPL_*`), подсказка окна, `CHANGELOG`, `docs/architecture.md`, пересборка exe.
