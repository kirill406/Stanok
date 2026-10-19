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
    APP_INTERRUPTED = "генерация прервана: {error}"
    APP_DONE = "Готово: создано {created}, ошибок {errors} за {elapsed} с"

    # Schema/validation (engine/schema.py)
    SCH_FORMAT_TOO_NEW = "Формат версии {version} новее программы — обновите программу"
    SCH_DIST_TRAVERSAL = "{field}: путь должен быть относительным без '..': {value}"

    # Generation (services/generate.py)
    GEN_RESULT_DIR = "Результат"

    # Storage (services/storage.py)
    STORAGE_DEFAULT_TPL = (
        "Нельзя убрать шаблон по умолчанию: сначала смените шаблон по умолчанию."
    )

    # Tables (tables/excel.py)
    TBL_READ_FAILED = "Не удалось прочитать таблицу {path}: {cause}"
    TBL_NO_HEADERS = "первая строка пустая: нет заголовков"
    TBL_BLANK_HEADER = "пустой заголовок в колонке {column}"
    TBL_DUP_HEADERS = "повторяющиеся заголовки: {headers}"

    # Main window (gui/main_window.py)
    MAIN_TITLE = "Станок"
    MAIN_PROJECT_GROUP = "Проект"
    MAIN_OPEN = "Открыть проект"
    MAIN_GENERATE = "Сгенерировать"
    MAIN_GENERATE_ALL = "Сгенерировать все"
    MAIN_REMOVE = "Убрать"
    MAIN_SETTINGS = "Настройки"
    MAIN_CREATE = "Создать проект"
    MAIN_FOLDER_MISSING = (
        "Папка проекта «{name}» не найдена. Указать новую папку?"
    )
    MAIN_FIND_FOLDER = "Папка проекта"
    MAIN_STATUS_READY = "Готов"
    MAIN_STATUS_RUNNING = "Генерация... {created} из {total}"
    MAIN_PROGRESS_TITLE = "Генерация документов"
    MAIN_CANCEL = "Отмена"
    MAIN_DONE_TITLE = "Генерация завершена"
    MAIN_ERRORS_TITLE = "Ошибки генерации"
    MAIN_ERROR_TITLE = "Ошибка"
    MAIN_CANCELLED = "Генерация отменена: создано {created}"
    MAIN_SUMMARY_TITLE = "Сгенерировать все: итог"

    # Open project dialog (gui/open_project_dialog.py, 020)
    OPEN_TITLE = "Открыть проект"
    OPEN_EMPTY = "Проекты не найдены: создайте новый проект."
    OPEN_NO_FOLDER = "папка неизвестна"

    # Settings dialog (gui/settings_dialog.py)
    SET_TITLE = "Настройки"
    SET_LOG_LEVEL = "Уровень лога:"
    SET_HOME = "Папка данных:"
    SET_VERSION = "Версия:"
    SET_LOG_FILE = "Файл лога:"
    SET_OPEN_FOLDER = "Открыть папку"
    SET_SAVE = "Сохранить"
    SET_CANCEL = "Отмена"

    # Create/settings-project dialog (gui/create_dialog.py, window 4)
    CRT_TITLE = "Новый проект"
    CRT_EDIT_TITLE = "Настройки проекта"
    CRT_NAME = "Имя проекта:"
    CRT_FOLDER = "Папка:"
    CRT_BROWSE = "Обзор..."
    CRT_XLSX = "Excel-файлы:"
    CRT_DOCX = "DOCX-шаблоны:"
    CRT_ADD = "Добавить..."
    CRT_REMOVE = "Убрать"
    CRT_COPY = "Скопировать файлы в проект"
    CRT_DEFAULT_TPL = "Шаблон по умолчанию:"
    CRT_CREATE = "Создать"
    CRT_SAVE = "Сохранить"
    CRT_CANCEL = "Отмена"
    CRT_ERR_TITLE = "Не удалось создать проект"
    CRT_SAVE_ERR_TITLE = "Не удалось сохранить настройки"
    CRT_PATH = "Файлы проекта: {path}"
    CRT_NAME_TAKEN = "Проект «{name}» уже существует — выберите другое имя"
    CRT_BAD_DIR = "Нельзя создавать проект внутри «{name}»"
    CRT_MKDIR_ASK = "Папки «{path}» нет. Создать её?"

    # Project folder layout (shared, NFR-3: no Cyrillic literals in code)
    DATA_DIR = "Данные"
    TPL_DIR = "Шаблоны"

    # Data-source modes (gui, 021)
    MODE_SEQUENTIAL = "По порядку"
    MODE_CIRCULAR = "По кругу"
    MODE_CONSTANT = "Одна строка"

    # Project dialog (gui/project_dialog.py, window 2)
    PROJ_TITLE = "Проект: {name}"
    PROJ_SOURCES_TITLE = "Источники:"
    PROJ_SRC_COL_FILE = "Файл"
    PROJ_SRC_COL_TYPE = "Тип"
    PROJ_SRC_ADD = "Добавить источник..."
    PROJ_TPL_COL = "Шаблон"
    PROJ_COUNT_COL = "Лимит"
    PROJ_COUNT_TIP = "Сколько документов создать (0 — без лимита, все строки)"
    PROJ_DEFAULT_COL = "По умолчанию"
    PROJ_DEFAULT_TIP = "Шаблон для запуска из главного окна"
    PROJ_RUN = "Сгенерировать"
    PROJ_SETTINGS = "Настройки проекта"
    TPL_ADD = "Добавить шаблон..."
    TPL_REMOVE = "Убрать"
    TPL_REMOVE_ASK = "Убрать шаблон «{name}»? Соответствия полей будут потеряны."
    TPL_LAST_KEPT = "Нельзя убрать последний шаблон: проект должен остаться генерируемым."
    TPL_DEFAULT_LOCKED = "Смените шаблон по умолчанию"
    PROJ_DELETE = "Удалить проект"
    PROJ_DELETE_ASK = "Удалить проект «{name}»? Действие необратимо."
    PROJ_DELETE_FOLDER = "Удалить папку с файлами"
    PROJ_DELETED = "Проект «{name}» удалён"

    # Fields dialog (gui/fields_dialog.py, window 3)
    FLD_TITLE = "Шаблон: {name}"
    FLD_FNAME_TITLE = "Имя файла:"
    FLD_FIELDS_TITLE = "Поля"
    FLD_COUNTERS_TITLE = "Счётчики"
    FLD_INSERT_FIELD = "Вставить поле"
    FLD_COL_FIELD = "Поле"
    FLD_COL_SOURCE = "Тип"
    FLD_COL_VALUE = "Значение"
    FLD_COL_DATA = "Данные"
    FLD_SAVE = "Сохранить"
    FLD_CLOSE = "Закрыть"
    FLD_HINT = "Источник меняется комбобоксом, значение — редактором по типу."
    FLD_DIRTY_ASK = "Есть несохранённые изменения. Сохранить?"
    FLD_SRC_CONSTANT = "Константа"
    FLD_SRC_TABLE = "Таблица"
    FLD_SRC_COUNTER = "Счётчик"
    FLD_SRC_TODAY = "Дата"
    FLD_CNT_NAME = "Название"
    FLD_CNT_SOURCE = "Источник данных"
    FLD_CNT_POS = "Начальная строка"
    FLD_CNT_RESUME = "Начинать заново"
    FLD_CNT_LAST = "Номер (значение)"
    FLD_CNT_FORMAT = "Формат"
    FLD_CNT_NAME_TIP = "Имя счётчика. На него ссылаются поля и поля-счётчики."
    FLD_CNT_SOURCE_TIP = (
        "Файл Excel, из которого берутся строки. "
        "«отсутствует» — числовой счётчик без источника."
    )
    FLD_CNT_FORMAT_TIP = (
        "Как печатать номер: 1 → 1, 2, 3; 01 → 01, 02, 03 (нули впереди); "
        "001, 0001 — больше разрядов."
    )
    FLD_POS_TIP = (
        "С какой строки файла брать данные. Генерация сдвигает её вперёд "
        "на число созданных документов (если не отмечено «Начинать заново»)."
    )
    FLD_CNT_LAST_TIP = (
        "Число, которое подставляется в поля-счётчики (например, № документа). "
        "Растёт на 1 за документ; вид задаёт «Формат»."
    )
    FLD_CNT_RESUME_TIP = (
        "Отмечено: после генерации строка и номер не сохраняются — следующий "
        "прогон начнётся заново. Снято: продолжать с сохранённого места."
    )
    FLD_CNT_HINT = (
        "«Начальная строка» — откуда брать данные; «Номер (значение)» — что "
        "печатать в полях-счётчиках. Оба сдвигаются после генерации, если "
        "не отмечено «Начинать заново»."
    )
    FLD_POS_CONST_TIP = (
        "Для режима «Одна строка» начальная строка фиксирована и не меняется."
    )
    FLD_PICK_DATA = "Выбрать данные"
    FLD_PICK_TITLE = "Выбор значения из таблицы"
    FLD_PICK_TIP = "Выбрать значение из привязанной таблицы"
    FLD_PICK_DISABLED_TIP = "Выбор данных недоступен в этой сборке"
    FLD_PICK_NO_SOURCE_TIP = "Счётчик не привязан к таблице — выбирать нечего"
    FLD_PICK_NOT_NUMBER = "Выберите целое неотрицательное число"
    PICK_TABLE_HINT = "Выберите ячейку с числом — оно станет «Номером»."
    PICK_WILL_WRITE = "Будет записано: {value}"
    PICK_NO_VALUE = "—"
    PICK_ROW = "Строка"
    PICK_ROW_TIP = (
        "Номер строки данных (с нуля), он же «Начальная строка» счётчика."
    )
    PICK_EMPTY = "В таблице нет данных"
    PICK_CHOOSE = "Выбрать"
    FLD_NONE = "отсутствует"
    FLD_COUNTER_CREATE = "Создать счётчик"
    FLD_COUNTER_NAME = "Имя счётчика:"
    FLD_DUP_COUNTER = "Счётчик «{name}» уже существует"
    FLD_DATE_KEEP = "как в проекте"
    FLD_DATE_DMY = "16.10.2026"
    FLD_DATE_DAY = "16"
    FLD_DATE_MONTH = "октября"
    FLD_DATE_MONTHNUM = "10"
    FLD_DATE_YEAR = "2026"
    FLD_DATE_RU = "16 октября 2026"
    FLD_EMPTY_VALUE = "Поле «{name}»: пустое значение — запись заблокирована"
    FLD_CNT_BAD = "Счётчик «{name}»: номер — целое число ≥ 0"
    FLD_CNT_POS_BAD = "Счётчик «{name}»: начальная строка — целое число ≥ 0"
    FLD_NO_COUNTER = "Поле «{name}»: выберите счётчик из списка или создайте новый"
    FLD_SRC_PICK = "Выбрать папку с источником..."
    FLD_SRC_CREATE = "Создать папку"
    FLD_SRC_MISSING = "Источник «{name}» не найден"
    FLD_SRC_MISSING_HINT = (
        "Выберите папку, где находится файл, или создайте папку «Данные»."
    )
    FLD_SRC_FIND_TITLE = "Папка с источником"
    FLD_SRC_DIR_MADE = (
        "Папки проекта созданы в «{folder}». "
        "Положите файл источника и откройте окно заново."
    )

    # Month names, genitive case for dates (engine splits on "|")
    RU_MONTHS_GENITIVE = (
        "января|февраля|марта|апреля|мая|июня|"
        "июля|августа|сентября|октября|ноября|декабря"
    )
