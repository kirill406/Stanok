# -*- coding: utf-8 -*-
"""UI strings for localization and customization."""

STRINGS = {
    # Main window
    'main_window_title': 'Станок',
    'main_create_project': 'Создать проект',
    'main_open_project': 'Открыть проект',
    'main_recent_projects': 'Недавние проекты',
    'main_generate_all': '⚡ Сгенерировать все',
    'main_delete_recent': '✕',
    'main_settings': 'Настройки',

    # Project window
    'project_window_title': 'Проект: {name}',
    'project_templates': 'Шаблоны',
    'project_data': 'Данные',
    'project_output': 'Результаты',
    'project_fill_template': 'Заполнить шаблон',
    'project_delete': '🗑 Удалить проект',
    'project_delete_confirm': 'Удалить проект "{name}"?\nБудут удалены: Шаблоны/ и файл проекта.\nДанные/ и Результаты/ сохранятся.',
    'project_delete_template': '🗑 Удалить шаблон',
    'project_delete_template_confirm': 'Удалить шаблон "{name}"?\nФайл будет удалён безвозвратно.',

    # Fill form dialog
    'fill_window_title': 'Заполнение: {template}',
    'fill_template_label': 'Шаблон: {template}',
    'fill_fields_count': 'Полей в шаблоне: {total} ({simple} настраиваемых, {today} дат, {counter} номеров, {image} изображений)',
    'fill_add_field': '+ Добавить поле',
    'fill_field_description': 'Для каждого поля из шаблона укажите источник данных',
    'fill_advanced_group': 'Дополнительно: циклы и агрегации',
    'fill_add_cycle': '+ Добавить цикл',
    'fill_add_aggr': '+ Добавить агрегацию',
    'fill_filename_template': 'Шаблон имени файла:',
    'fill_filename_placeholder': '{{ doc_number }}_{{ client_name }} (пусто = авто)',
    'fill_filename_tooltip': 'Используйте {{ field_name }} для подстановки значений полей. Пусто = автоматическое именование.',
    'fill_insert_field_btn': 'Вставить поле',
    'fill_total_docs': 'Количество документов:',
    'fill_auto_checkbox': 'Авто',
    'fill_continue_checkbox': 'Продолжить с последней строки',
    'fill_validate_btn': 'Проверить',
    'fill_create_btn': 'Создать',
    'fill_cancel_btn': 'Отмена',
    'fill_create_projects': 'Создать проекты вместо документов',
    'fill_folder_name_template': 'Шаблон имени папки проекта',
    'fill_found_rows': 'Найдено строк: {count}. Сколько проектов создать?',
    'fill_projects_created': 'Создано {count} проектов в {path}',

    # Field types
    'field_type_constant': 'константа',
    'field_type_table': 'таблица',
    'field_type_counter': 'счётчик',
    'field_type_today': 'сегодня',
    'field_type_image': 'изображение',

    # Field dialog
    'field_dialog_title': 'Добавить поле',
    'field_dialog_select_type': 'Выберите тип поля',
    'field_dialog_desc': 'Каждый тип показывает, как поле будет выглядеть в шаблоне и в результате.',
    'field_dialog_params': 'Параметры поля',
    'field_dialog_add_btn': 'Добавить поле',
    'field_dialog_cancel_btn': 'Отмена',

    # Batch section
    'batch_generation_group': 'Генерация',
    'batch_mode_constant': 'Константа',
    'batch_mode_sequential': 'По строкам',
    'batch_mode_circular': 'По кругу',
    'batch_lookup_column': 'Столбец:',
    'batch_lookup_value': 'Значение:',
    'batch_continue_from_last': 'Продолжить с последней строки',
    'batch_auto_info_with_tables': 'Авто: минимальное число строк ({counts})',
    'batch_auto_info_no_tables': 'Авто: нет таблиц "По строкам" - задайте количество вручную',
    'batch_counter_column': 'Столбец счётчика:',
    'batch_counter_current_row': 'Текущая строка:',
    'batch_counter_value': 'Значение строки:',
    'batch_counter_summary': 'Счётчики источников: {counters}',
    'fill_directory_template': 'Шаблон папки:',
    'fill_directory_placeholder': '{{ region }}/{{ city }} (пусто = без подпапок)',
    'fill_directory_tooltip': 'Используйте {{ field_name }} для подстановки. Папки будут созданы внутри выходной директории. Пусто = файлы напрямую в папку результатов.',

    # Create projects mode
    'fill_create_projects_checkbox': 'Создать проекты',
    'fill_folder_name_template': 'Шаблон имени папки:',
    'fill_folder_name_placeholder': '{{ region }}_{{ city }} (обязательно для режима проектов)',
    'fill_folder_name_tooltip': 'Используйте {{ field_name }} для подстановки значений из таблицы. Каждая строка = одна папка проекта в Projects/. Обязательно в режиме "Создать проекты".',
    'fill_found_rows': 'Найдено строк в таблице: {count}.\nСоздать {count} проектов в папке Projects/?',
    'fill_projects_created': 'Создано проектов: {count}\nПапка: {path}',
    'fill_create_projects_btn': 'Создать проекты',
    'msg_folder_template_required': 'Для создания проектов укажите шаблон имени папки',
    'fill_nested_projects_created': 'Создано сотрудников: {employees}, проектов: {count} в {path}',
    'msg_no_batch_rows': 'Нет строк данных для создания проектов. Проверьте источник «По строкам» и файл данных.',

    # Messages
    'msg_error': 'Ошибка',
    'msg_warning': 'Предупреждение',
    'msg_info': 'Информация',
    'msg_success': 'Готово',
    'msg_field_exists': 'Поле {name} уже существует',
    'msg_validation_errors': 'Ошибки валидации:\n{errors}',
    'msg_validation_ok': 'Всё корректно. Конфигурация сохранена.',
    'msg_generation_done': 'Создано документов: {count}\n{files}',
    'msg_generation_failed': 'Не удалось создать документы',
    'msg_project_not_found': 'Файл проекта не найден',
    'msg_template_not_found': 'Файл шаблона не найден',
    'msg_template_not_configured': 'Шаблон не настроен',
    'msg_no_templates': 'Нет настроенных шаблонов',
    'msg_file_permission_error': 'Нет доступа к файлу "{file}".\nВозможно, файл открыт в Excel или это временный файл (~$...).\nЗакройте файл в Excel и попробуйте снова.',
    'msg_delete_recent_confirm': 'Убрать "{name}" из недавних проектов?',

    # Field labels
    'field_label_file': 'Файл:',
    'field_label_column': 'Столбец:',
    'field_label_start': 'Начало:',
    'field_label_counter_format': 'Формат:',
    'field_label_today_format': 'Формат:',
    'field_label_image': 'Изображение:',

    # Today format options
    'today_format_month': 'название месяца',
}
