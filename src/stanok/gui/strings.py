# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Single source of user-facing strings (NFR-3).

Leaf module: no imports, no Qt — safe to import from any layer.
Usage: from stanok.gui.strings import STRINGS.
Placeholders are filled with `.format()` at the use site.
"""


class STRINGS:
    """All user-facing strings (Russian). Keys: SCREAMING_SNAKE + area prefix."""

    # CLI (app.py)
    APP_DESCR = "Генерация docx из проекта"
    APP_REF_HELP = "Папка проекта или имя конфига"
    APP_TEMPLATE_HELP = "Имя шаблона"
    APP_SOURCE_HELP = "Имя источника данных"
    APP_MAXDOCS_HELP = "Лимит документов"
    APP_RESUME_HELP = "Продолжить с start_row"
    APP_INTERRUPTED = "генерация прервана: {error}"
    APP_DONE = (
        "Готово: создано {created}, пропущено {skipped}, "
        "ошибок {errors} за {elapsed} с"
    )

    # Schema/validation (engine/schema.py)
    SCH_FORMAT_TOO_NEW = "Формат версии {version} новее программы — обновите программу"
    SCH_DIST_TRAVERSAL = "{field}: путь должен быть относительным без '..': {value}"

    # Generation (services/generate.py)
    GEN_RESULT_DIR = "Результат"

    # Tables (tables/excel.py)
    TBL_READ_FAILED = "Не удалось прочитать таблицу {path}: {cause}"
    TBL_NO_HEADERS = "первая строка пустая: нет заголовков"
    TBL_BLANK_HEADER = "пустой заголовок в колонке {column}"
    TBL_DUP_HEADERS = "повторяющиеся заголовки: {headers}"

    # Main window (gui/main_window.py)
    MAIN_TITLE = "Станок"
    MAIN_PROJECT_GROUP = "Проект"
    MAIN_BROWSE = "Обзор..."
    MAIN_TEMPLATE = "Шаблон:"
    MAIN_SOURCE = "Источник:"
    MAIN_RESUME = "Продолжить с места остановки"
    MAIN_LIMIT = "Лимит документов (0 — без лимита):"
    MAIN_GENERATE = "Сгенерировать"
    MAIN_GENERATE_ALL = "Сгенерировать все"
    MAIN_SETTINGS = "Настройки"
    MAIN_SETTINGS_STUB = "Настройки приложения появятся позже"
    MAIN_SUMMARY_TITLE = "Сгенерировать все: итог"
    MAIN_CREATE = "Создать проект"
    MAIN_CREATE_STUB = "Создание проекта появится в 014"

    # Project dialog (gui/project_dialog.py, window 2)
    PROJ_TITLE = "Проект: {name}"
    PROJ_DATA = "Данные: {path}"
    PROJ_SOURCE = "Источник: {file}"
    PROJ_TPL_COL = "Шаблон"
    PROJ_COUNT_COL = "Лимит"
    PROJ_COUNT_TIP = "Сколько документов создать (0 — без лимита, все строки)"
    PROJ_RUN = "Сгенерировать"
    # Fields dialog (gui/fields_dialog.py, window 3)
    FLD_TITLE = "Шаблон: {name}"
    FLD_COL_FIELD = "Поле"
    FLD_COL_SOURCE = "Источник"
    FLD_COL_VALUE = "Значение"
    FLD_SAVE = "Сохранить"
    FLD_HINT = "Правятся только константы; остальное — превью."
    FLD_DIRTY_ASK = "Есть несохранённые изменения. Сохранить?"
    FLD_SRC_CONSTANT = "константа"
    FLD_SRC_TABLE = "таблица"
    FLD_SRC_COUNTER = "счётчик"
    FLD_SRC_TODAY = "сегодня"
    FLD_PREVIEW_COUNTER = "счётчик: {name} (last={last})"
    FLD_PREVIEW_TODAY = "сегодня: {today}"
    MAIN_STATUS_READY = "Готов"
    MAIN_STATUS_RUNNING = "Генерация... {created} из {total}"
    MAIN_PROGRESS_TITLE = "Генерация документов"
    MAIN_CANCEL = "Отмена"
    MAIN_DONE_TITLE = "Генерация завершена"
    MAIN_ERRORS_TITLE = "Ошибки генерации"
    MAIN_ERROR_TITLE = "Ошибка"
    MAIN_CANCELLED = "Генерация отменена: создано {created}"
    MAIN_NO_PROJECT = "Выберите проект: папку или запись из недавних"
