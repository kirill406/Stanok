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
    APP_ERROR_LINE = "  ошибка {index}: {error}"
    APP_CRASH = (
        "Непредвиденная ошибка: {error}\n\n"
        "Подробности записаны в файл лога. В нём могут быть персональные "
        "данные — проверьте файл перед отправкой. Пожалуйста, свяжитесь с "
        "разработчиком и приложите файл лога."
    )
    APP_DONE = "Готово: создано {created}, ошибок {errors} за {elapsed} с"
    APP_DONE_NO_LIMIT = (
        "Готово: документы не созданы, лимит шаблона 0. "
        "Укажите лимит больше 0, ошибок {errors} за {elapsed} с"
    )
    APP_DONE_SHORT = (
        "Готово: создано {created} из {limit} (строки закончились), "
        "ошибок {errors} за {elapsed} с"
    )

    # Schema/validation (engine/schema.py)
    SCH_FORMAT_TOO_NEW = "Формат версии {version} новее программы — обновите программу"
    SCH_RESULT_DIR_RELATIVE = "Папка копий результата должна быть абсолютной: {value}"
    SCH_NO_MIGRATION = "Нет пути миграции формата {source} → {target}"
    SCH_MIGRATION_STALLED = "Миграция {source} не обновила версию (шаг → {target})"
    SCH_DIST_TRAVERSAL = "{field}: путь должен быть относительным без '..': {value}"

    # Generation (services/generate.py)
    GEN_RESULT_DIR = "Результат"
    GEN_SKIPPED_COLUMNS = "Пропущены столбцы без заголовков:\n{items}"
    GEN_COPY_FAILED = "Не удалось скопировать результат в {dest}: {cause}"

    # Storage (services/storage.py)
    STORAGE_DEFAULT_TPL = (
        "Нельзя убрать шаблон по умолчанию: сначала смените шаблон по умолчанию."
    )

    STORAGE_SOURCE_LAST = "Нельзя убрать последний источник проекта"
    STORAGE_SOURCE_IN_USE = (
        "Источник «{file}» нужен полям: {fields}. Сначала измените эти поля"
    )

    # Tables (tables/excel.py)
    TBL_READ_FAILED = "Не удалось прочитать таблицу {path}: {cause}"
    TBL_NO_HEADERS = "первая строка пустая: нет заголовков"
    TBL_SKIPPED_COLUMNS = (
        "пропущены столбцы без заголовков: {columns}; их данные недоступны"
    )
    TBL_DUP_HEADERS = "повторяющиеся заголовки: {headers}"

    # Main window (gui/main_window.py)
    MAIN_TITLE = "Станок"
    MAIN_SUBTITLE = "Генерация документов по шаблонам Word"
    MAIN_PROJECT_GROUP = "Проекты"
    MAIN_EMPTY = (
        "Проектов пока нет. Создайте новый проект или откройте существующий."
    )
    MAIN_OPEN = "Открыть проект"
    MAIN_GENERATE = "Сгенерировать"
    MAIN_EDIT = "Редактировать"
    MAIN_GENERATE_ALL = "Сгенерировать все"
    MAIN_TPL = "Шаблон: «{name}»"
    MAIN_TPL_UNAVAILABLE = "Шаблон: —"
    MAIN_TPL_LIMIT_TIP = "Сколько документов создать по шаблону (0 — не создавать)"
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

    # Common dialog buttons (gui/dialogs.py)
    BTN_YES = "Да"
    BTN_NO = "Нет"
    BTN_OK = "ОК"
    BTN_SAVE = "Сохранить"
    BTN_DISCARD = "Не сохранять"
    MAIN_ERRORS_TITLE = "Ошибки генерации"
    MAIN_ERROR_TITLE = "Ошибка"
    MAIN_CANCELLED = "Генерация отменена: создано {created}"
    MAIN_SUMMARY_TITLE = "Сгенерировать все: итог"

    # Open project dialog (gui/open_project_dialog.py, 020)
    OPEN_TITLE = "Открыть проект"
    OPEN_SUBTITLE = "Выберите сохранённый проект или импортируйте папку"
    OPEN_EMPTY = "Проекты не найдены: создайте новый проект."
    OPEN_NO_FOLDER = "папка неизвестна"
    OPEN_PICK = "Выбрать папку"
    OPEN_IMPORTED = "Добавлено проектов: {count}"
    OPEN_IMPORT_ERRORS = "Не удалось прочитать: {count}"
    OPEN_IMPORT_MISSING = "Папка не найдена у проектов: {names}"
    OPEN_FAILED = (
        "Не удалось открыть: в папке нет проектов .stanok "
        "или структуры проекта (Данные, Шаблоны, Результат)."
    )

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
    CRT_EDIT_TITLE = "Настройки проекта"
    CRT_NAME = "Имя проекта:"
    CRT_FOLDER = "Папка:"
    CRT_BROWSE = "Обзор..."
    CRT_DEFAULT_TPL = "Шаблон по умолчанию:"
    CRT_SAVE = "Сохранить"
    CRT_CANCEL = "Отмена"
    CRT_SAVE_ERR_TITLE = "Не удалось сохранить настройки"
    CRT_SECTION_DATA = "Данные"
    CRT_SECTION_TPL = "Шаблоны"
    CRT_SECTION_RESULTS = "Результаты"
    CRT_RESULT_COPY_TIP = "Дублировать результат в другую папку"
    CRT_RESULT_COPY_PICK = "Папка для копий результата"
    CRT_RESULT_COPY_OWN = "Это папка результатов самого проекта"
    CRT_RESULT_COPY_DUP = "Эта папка уже в списке"
    CRT_RESULT_REMOVE_TIP = "Убрать папку из списка"
    CRT_COPIES_NONE = "Копии результата не настроены"
    CRT_MKDIR_ASK = "Папки «{path}» нет. Создать её?"
    # 024: окно старта создания проекта
    START_TITLE = "Создание проекта"
    START_DESCR = (
        "Папка проекта содержит три подпапки: «Данные» (таблицы .xlsx), "
        "«Шаблоны» (документы .docx) и «Результат» (готовые документы). "
        "Выберите способ создания."
    )
    START_MINIMAL = "Создать минимальный шаблон"
    START_PICK = "Выбрать готовую папку"
    START_CLONE = "Создать из существующего проекта"
    START_CLOSE = "Закрыть"
    START_BASE = "Где создать:"
    START_SOURCE = "Проект-источник:"
    START_NO_SOURCES = "Нет проектов, из которых можно скопировать"
    START_PICK_TITLE = "Папка проекта"
    START_FORM_NAME = "Имя проекта:"
    START_FORM_TITLE_MINIMAL = "Минимальный шаблон"
    START_FORM_TITLE_CLONE = "Копия проекта"
    START_FORM_CREATE = "Создать папку"
    START_BROWSE = "Обзор..."
    START_NAME_EMPTY = "Введите имя проекта"
    START_MISSING_ASK = "В папке нет «{dirs}». Создать недостающие подпапки?"
    START_ERR_TITLE = "Не удалось создать папку проекта"
    # 024: окно подсказок и проверки структуры
    PCHK_TITLE = "Подготовка проекта"
    PCHK_HINT = (
        "Положите в папку «Шаблоны» документы .docx. В тексте документа "
        "пишите поля в двойных фигурных скобках, например {{Фамилия}}.\n\n"
        "Положите в папку «Данные» таблицы .xlsx. В первой строке — "
        "заголовки колонок. Имена колонок совпадают с именами полей.\n\n"
        "Когда файлы готовы, нажмите «Проверить»."
    )
    PCHK_CHECK = "Проверить"
    PCHK_CREATE = "Создать проект"
    PCHK_CLOSE = "Закрыть"
    PCHK_CREATE_DIRS = "Создать папки"
    PCHK_FOLDER_LABEL = "Папка проекта:\n{path}"
    PCHK_ERRORS_COUNT = "Ошибок: {count}. Исправьте файлы и нажмите «Проверить»."
    PCHK_WARNINGS_HINT = (
        "Предупреждения не мешают созданию. Нажмите «Создать проект», "
        "чтобы продолжить, или исправьте файлы и проверьте снова."
    )
    PCHK_WARN_PREFIX = "Предупреждение: {message}"
    PCHK_NAME_LABEL = "Имя проекта:"
    PCHK_COL_FILE = "Файл"
    PCHK_COL_COLUMN = "Колонка"
    PCHK_COL_MESSAGE = "Сообщение"
    PCHK_NO_FOLDER = "Папка «{path}» не найдена"
    PCHK_MISSING_DIRS = "Нет папки «{dirs}»"
    PCHK_NO_DOCX = "В папке «Шаблоны» нет .docx"
    PCHK_NO_XLSX = "В папке «Данные» нет .xlsx"
    PCHK_NO_FIELDS = "В шаблоне нет полей вида {{поле}}"
    PCHK_TEMPLATE_READ = "Шаблон не читается: {cause}"
    PCHK_EMPTY_FIELD = "Пустое поле {{ }}"
    PCHK_TABLE_READ = "Таблица не читается: {cause}"
    PCHK_NO_HEADERS = "Нет заголовков в первой строке"
    PCHK_NO_ROWS = "Нет строк данных"
    PCHK_NAME_EMPTY = "Введите имя проекта"
    PCHK_NAME_BAD = "Имя содержит недопустимые символы: / \\ . .."
    PCHK_NAME_TAKEN = "Проект «{name}» уже существует"
    PCHK_FOLDER_BUSY = "Папка «{path}» уже не пустая"
    PCHK_CREATE_FAILED = "Не удалось создать проект: {cause}"

    # 026: shared (сквозные) counters (services/storage.py, gui/global_counters_dialog.py)
    GCNT_BUTTON = "Счётчики..."
    GCNT_TITLE = "Сквозные счётчики"
    GCNT_HINT = (
        "Общие для всех проектов. В шаблоне поле «Счётчик» может ссылаться на них. "
        "Двойной клик по имени — переименовать."
    )
    GCNT_NAME = "Имя:"
    GCNT_FORMAT = "Формат:"
    GCNT_START = "Начальное значение:"
    GCNT_ADD = "Добавить"
    GCNT_ADD_TITLE = "Новый сквозной счётчик"
    GCNT_COL_NAME = "Имя"
    GCNT_COL_FORMAT = "Формат"
    GCNT_COL_VALUE = "Текущее значение"
    GCNT_COL_USERS = "Используют"
    GCNT_NO_USERS = "—"
    GCNT_REMOVE = "Убрать"
    GCNT_REMOVE_ASK = "Убрать сквозной счётчик «{name}»?"
    GCNT_IN_USE = "Счётчик «{name}» используют проекты: {projects}. Сначала уберите его из полей."
    GCNT_NAME_EMPTY = "Введите имя счётчика"
    GCNT_NAME_BAD = "Имя не должно содержать «/» или «\»"
    GCNT_NAME_TAKEN = "Счётчик «{name}» уже есть: сквозной или в проекте"
    GCNT_FORMAT_BAD = "Неизвестный формат: {fmt}"
    GCNT_UNKNOWN = "Сквозной счётчик не найден: {name}"
    GCNT_SHARED_TAG = "сквозной"
    GCNT_CLASH_TAG = "имя занято счётчиком проекта"
    GCNT_RENAME = "Переименовать сквозной счётчик"
    GEN_SHARED_COLLISION = (
        "Счётчик «{name}» есть и в проекте, и среди сквозных. "
        "Переименуйте сквозной счётчик в окне «Счётчики»"
    )
    GEN_SHARED_UNKNOWN = "Счётчик «{name}» не найден ни в проекте, ни среди сквозных"
    MAIN_COUNTERS = "Счётчики..."

    # Project folder layout (shared, NFR-3: no Cyrillic literals in code)
    DATA_DIR = "Данные"
    TPL_DIR = "Шаблоны"

    # Data-source modes (gui, 021)
    MODE_SEQUENTIAL = "По порядку"
    MODE_CIRCULAR = "По кругу"
    MODE_CONSTANT = "Одна строка"

    # Project dialog (gui/project_dialog.py, window 2)
    PROJ_TITLE = "Проект: {name}"
    PROJ_FOLDER = "Папка: {path}"
    PROJ_SOURCES_TITLE = "Источники:"
    PROJ_TEMPLATES_TITLE = "Шаблоны:"
    PROJ_SRC_COL_FILE = "Файл"
    PROJ_SRC_COL_TYPE = "Тип"
    PROJ_SRC_TYPES_HINT = (
        "Типы источников: «По порядку» — строки по одной до конца таблицы; "
        "«По кругу» — после последней строки снова первая; "
        "«Одна строка» — всегда одна и та же строка, счётчик не меняется."
    )
    PROJ_SRC_ADD = "Добавить источник..."
    PROJ_SRC_REMOVE = "Убрать"
    PROJ_SRC_REMOVE_ASK = (
        "Убрать источник «{name}»? Файл останется в папке «Данные»."
    )
    PROJ_TPL_COL = "Шаблон"
    PROJ_COUNT_COL = "Лимит"
    PROJ_COUNT_TIP = "Сколько документов создать за прогон (0 — не создавать)"
    PROJ_DEFAULT_COL = "По умолчанию"
    PROJ_DEFAULT_TIP = "Шаблон для запуска из главного окна"
    PROJ_RUN = "Сгенерировать"
    PROJ_EDIT = "Редактировать"
    PROJ_EDIT_TIP = "Открыть поля и источники шаблона"
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

    # Template page (gui/template_sheet.py, 027)
    TPL_PART_HEADER = "Верхний колонтитул"
    TPL_PART_FOOTER = "Нижний колонтитул"
    TPL_PAGE_BREAK = "Разрыв страницы"
    TPL_LOAD_FAILED = "Не удалось открыть шаблон: {error}"

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
    FLD_CNT_POS = "Позиция"
    FLD_CNT_RESUME = "Заново"
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
        "Строка файла (с нуля) и одновременно число, которое печатается "
        "в полях-счётчиках. Генерация сдвигает её на число документов, "
        "если не отмечено «Заново»."
    )
    FLD_CNT_RESUME_TIP = (
        "Снято: после генерации позиция сохраняется — следующий прогон "
        "продолжит с неё. Отмечено: позиция не сохраняется, прогон начнётся "
        "заново."
    )
    FLD_CNT_RESUME_NA_TIP = (
        "Для этого счётчика позиция после генерации не меняется."
    )
    FLD_CNT_DEFINITION = (
        "Счётчик — это число в памяти компьютера. Для каждой таблицы "
        "создаётся свой счётчик по умолчанию. Можно создать новый счётчик "
        "и использовать его в полях документов (например, для регистрационного "
        "номера). При генерации счётчики сдвигаются вперёд согласно типу данных "
        "(«Одна строка», «По порядку», «По кругу») или на 1 за каждый документ, "
        "если привязка к таблице отсутствует."
    )
    FLD_CNT_HINT = (
        "«Позиция» — это и строка источника, и печатаемое число. В режиме "
        "«Одна строка» она не меняется."
    )
    FLD_CNT_CHANGE_FAILED = (
        "Не удалось изменить счётчик: {error}\n\n"
        "Изменение не сохранено. Проверьте данные и попробуйте снова."
    )
    FLD_POS_CONST_TIP = (
        "Для режима «Одна строка» позиция фиксирована и не меняется."
    )
    FLD_PICK_DATA = "Выбрать данные"
    FLD_PICK_TITLE = "Выбор значения из таблицы"
    FLD_PICK_TIP = "Выбрать значение из привязанной таблицы"
    FLD_PICK_DISABLED_TIP = "Выбор данных недоступен в этой сборке"
    FLD_PICK_NO_SOURCE_TIP = "Счётчик не привязан к таблице — выбирать нечего"
    FLD_PICK_NOT_NUMBER = "Выберите целое неотрицательное число"
    PICK_TABLE_HINT = "Выберите строку — её номер станет «Позицией»."
    PICK_WILL_WRITE = "Будет записано: {value}"
    PICK_NO_VALUE = "—"
    PICK_ROW = "Строка"
    PICK_ROW_TIP = "Номер строки данных (с нуля); он записывается в «Позицию»."
    PICK_EMPTY = "В таблице нет данных"
    PICK_CHOOSE = "Выбрать"
    FLD_NONE = "отсутствует"
    FLD_COUNTER_CREATE = "Создать счётчик"
    FLD_CNT_REMOVE = "Убрать"
    FLD_CNT_REMOVE_TIP = "Удалить счётчик проекта. Доступно, если ни одно поле его не читает"
    FLD_CNT_REMOVE_BOUND = (
        "Счётчик привязан к источнику. Уберите источник в окне проекта, счётчик уйдёт с ним"
    )
    FLD_CNT_REMOVE_USED = "Счётчик «{name}» читают поля: {fields}. Сначала измените эти поля"
    FLD_CNT_REMOVE_ASK = "Удалить счётчик «{name}»?"
    FLD_COUNTER_NAME = "Имя счётчика:"
    FLD_DUP_COUNTER = "Счётчик «{name}» уже существует"
    FLD_DATE_KEEP = "как в проекте"
    FLD_EMPTY_VALUE = "Поле «{name}»: пустое значение — запись заблокирована"
    FLD_CNT_POS_BAD = "Счётчик «{name}»: позиция — целое число ≥ 0"
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
