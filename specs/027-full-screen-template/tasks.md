# Задачи: 027-full-screen-template

Каждая задача — отдельный коммит с тестами. Порядок важен: раскладка → виджеты → редактор → окно.

1. [ ] `services/template_layout.py`: модели и разбор абзаца (текст, стиль, поля, `w:br`, `w:br type=page`).
2. [ ] Раскладка: абзацы (выравнивание, отступы, интервалы, наследование стиля, `docDefaults`), таблицы, колонтитулы, `pageBreakBefore`.
3. [ ] Тесты раскладки на docx, созданных в тесте (`python-docx`).
4. [ ] `gui/template_sheet.py`: `FlowLayout`, абзац, строка, кнопка поля, сигнал `fieldClicked`.
5. [ ] `gui/template_sheet.py`: таблица, колонтитулы, разрыв страницы, размеры страницы.
6. [ ] `gui/source_data.py`: вынос чтения строк и заголовков, восстановление источника (из `fields_dialog.py`).
7. [ ] `gui/field_editor.py`: тип и значение поля (константа, таблица, счётчик, дата).
8. [ ] `gui/field_editor.py`: блок счётчика — источник, формат, позиция, «Заново», создание, удаление, сквозной — только чтение.
9. [ ] `gui/fields_dialog.py`: новое окно на весь экран, `TemplateSheet`, кнопки полей, поля вне документа, сохранение.
10. [ ] Удалить старые таблицы полей и счётчиков; обновить `test_global_counters.py`, `test_integration.py`, `test_project_dialog.py`.
11. [ ] Строки интерфейса в `STRINGS`; тест `test_strings.py`.
12. [ ] `CHANGELOG.md [Unreleased]`, `docs/architecture.md`, `README.md` (если описано окно 3), спека → Done.
13. [ ] Проверка на экране (скриншот `grabWindow`), пересборка exe в `dist/`.
