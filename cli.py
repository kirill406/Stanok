# -*- coding: utf-8 -*-
"""DocxForge CLI — command-line interface for all project operations.

Usage:
    python cli.py create PROJECT_DIR
    python cli.py scan PROJECT_DIR TEMPLATE
    python cli.py configure PROJECT_DIR TEMPLATE [options]
    python cli.py render PROJECT_DIR TEMPLATE [--batch TABLE] [--output DIR]
    python cli.py list PROJECT_DIR [--templates|--data|--config]
    python cli.py info PROJECT_DIR
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
    CycleMapping, AggregationMapping, AggregationFunction,
    create_project,
)
from docxforge.engine.template_parser import scan_template
from docxforge.engine.renderer import Renderer
from docxforge.engine.data_reader import DataReader


# ============================================================
# Helpers
# ============================================================

def _load_project(project_dir: str) -> Project:
    pf = os.path.join(project_dir, 'проект.docxforge')
    if not os.path.exists(pf):
        print('Ошибка: проект не найден в %s' % project_dir)
        print('Создайте проект: python cli.py create %s' % project_dir)
        sys.exit(1)
    return Project.from_file(pf)


def _save_project(project: Project, project_dir: str):
    project.to_file(os.path.join(project_dir, 'проект.docxforge'))


def _get_or_create_template(project: Project, template: str) -> TemplateConfig:
    return project.templates.setdefault(template, TemplateConfig())


# ============================================================
# Commands
# ============================================================

def cmd_create(args):
    """Create a new project."""
    path = os.path.abspath(args.project_dir)
    pf = create_project(path)
    print('Проект создан: %s' % path)
    print('  Данные/   — скопируйте сюда .xlsx файлы')
    print('  Шаблоны/  — скопируйте сюда .docx шаблоны')
    print('  проект.docxforge — файл настроек (автоматический)')


def cmd_scan(args):
    """Scan a template for placeholders."""
    project_dir = os.path.abspath(args.project_dir)
    tmpl_path = os.path.join(project_dir, 'Шаблоны', args.template)
    if not os.path.exists(tmpl_path):
        # Try as absolute path
        if os.path.exists(args.template):
            tmpl_path = args.template
        else:
            print('Ошибка: шаблон не найден: %s' % args.template)
            sys.exit(1)

    result = scan_template(tmpl_path)
    simple = result['simple']
    today = result['today']
    doc_number = result['doc_number']
    image = result['image']
    total = len(simple) + len(today) + len(doc_number) + len(image)

    print('Шаблон: %s' % args.template)
    print('Найдено полей: %d' % total)
    print()

    if simple:
        print('  Настраиваемые поля (%d):' % len(simple))
        for s in simple:
            print('    {{ %s }}' % s)
        print()

    if today:
        print('  Даты (%d):' % len(today))
        for t in today:
            print('    {{ %s }} — автоподстановка' % t)
        print()

    if doc_number:
        print('  Номера (%d):' % len(doc_number))
        for d in doc_number:
            print('    {{ %s }} — счётчик' % d)
        print()

    if image:
        print('  Изображения (%d):' % len(image))
        for i in image:
            print('    {{ image:%s }}' % i)
        print()


def cmd_configure(args):
    """Configure field mappings, cycles, aggregations."""
    project_dir = os.path.abspath(args.project_dir)
    project = _load_project(project_dir)
    tc = _get_or_create_template(project, args.template)

    if args.field:
        # --field имя тип [значение/файл] [--column СТОЛБЕЦ] [--linked-to ПОЛЕ]
        #        [--start N] [--format FMT]
        ftype = args.field_type.lower()
        fm = FieldMapping()

        if ftype == 'constant' or ftype == 'константа':
            fm.type = FieldType.CONSTANT
            fm.value = args.value
        elif ftype == 'table' or ftype == 'таблица':
            fm.type = FieldType.TABLE
            fm.file = args.value
            fm.column = args.column
            if args.linked_to:
                fm.linked_to = args.linked_to
        elif ftype == 'counter' or ftype == 'счётчик':
            fm.type = FieldType.COUNTER
            fm.start = int(args.start) if args.start else 1
            fm.format = args.format if args.format else '0001'
        elif ftype == 'today' or ftype == 'сегодня':
            fm.type = FieldType.TODAY
            fm.format = args.format if args.format else 'dd.MM.yyyy'
        elif ftype == 'image' or ftype == 'изображение':
            fm.type = FieldType.IMAGE
            fm.value = args.value
        else:
            print('Ошибка: неизвестный тип поля: %s' % ftype)
            print('Допустимые: constant, table, counter, today, image')
            sys.exit(1)

        tc.fields[args.field] = fm
        print('Поле {{ %s }} настроено: тип=%s' % (args.field, ftype))

    if args.cycle:
        # --cycle спецификация.xlsx наименование=наименование кол-во=количество
        table = args.cycle[0]
        cols = {}
        for pair in args.cycle[1:]:
            if '=' in pair:
                k, v = pair.split('=', 1)
                cols[k.strip()] = v.strip()
        if cols:
            tc.cycles.append(CycleMapping(table=table, columns=cols))
            print('Цикл добавлен: таблица=%s, поля=%s' % (table, list(cols.keys())))

    if args.aggregation:
        # --aggregation итого sum спецификация.xlsx цена [--multiplier N]
        name = args.aggregation[0]
        func = args.aggregation[1].lower()
        table = args.aggregation[2]
        column = args.aggregation[3]

        if func == 'sum_multiply' or func == 'sum_multiply':
            af = AggregationFunction.SUM_MULTIPLY
            mult = float(args.multiplier) if args.multiplier else 1.0
        else:
            af_map = {'sum': AggregationFunction.SUM,
                       'count': AggregationFunction.COUNT,
                       'max': AggregationFunction.MAX,
                       'min': AggregationFunction.MIN}
            af = af_map.get(func, AggregationFunction.SUM)
            mult = None

        tc.aggregations[name] = AggregationMapping(
            function=af, table=table, column=column, multiplier=mult)
        print('Агрегация {{ %s }} добавлена: %s(%s.%s)' % (name, func, table, column))

    _save_project(project, project_dir)


def cmd_render(args):
    """Render template into output documents."""
    project_dir = os.path.abspath(args.project_dir)
    _load_project(project_dir)  # Ensure project exists

    data_reader = DataReader()
    renderer = Renderer(project_dir, data_reader)
    renderer.load_project()

    output_dir = args.output if args.output else None
    outputs = renderer.render(
        args.template,
        {},
        batch_table=args.batch,
        output_dir=output_dir,
    )

    print('Создано документов: %d' % len(outputs))
    if outputs:
        out_dir = os.path.dirname(outputs[0])
        print('Папка: %s' % out_dir)
        for o in outputs:
            print('  %s' % os.path.basename(o))


def cmd_list(args):
    """List templates, data files, or config."""
    project_dir = os.path.abspath(args.project_dir)

    if args.data:
        data_dir = os.path.join(project_dir, 'Данные')
        if os.path.exists(data_dir):
            files = sorted(os.listdir(data_dir))
            if files:
                print('Файлы данных (%d):' % len(files))
                for f in files:
                    print('  📊 %s' % f)
            else:
                print('Нет файлов данных')
        else:
            print('Папка Данные/ не найдена')

    elif args.config:
        project = _load_project(project_dir)
        if project.templates:
            print('Настроенные шаблоны (%d):' % len(project.templates))
            for tname, tc in project.templates.items():
                fields = len(tc.fields)
                cycles = len(tc.cycles)
                aggr = len(tc.aggregations)
                print('  📄 %s — %d полей, %d циклов, %d агрегаций' % (
                    tname, fields, cycles, aggr))
        else:
            print('Нет настроенных шаблонов')

    else:
        # List templates (default)
        tmpl_dir = os.path.join(project_dir, 'Шаблоны')
        if os.path.exists(tmpl_dir):
            _print_templates_tree(tmpl_dir, tmpl_dir, 0)
        else:
            print('Папка Шаблоны/ не найдена')


def _print_templates_tree(base_dir, root_dir, depth):
    """Recursively print template tree."""
    items = sorted(os.listdir(base_dir))
    for name in items:
        full = os.path.join(base_dir, name)
        prefix = '  ' * depth
        if os.path.isdir(full):
            print(prefix + '📁 %s/' % name)
            _print_templates_tree(full, root_dir, depth + 1)
        elif name.endswith('.docx'):
            print(prefix + '📄 %s' % name)


def cmd_info(args):
    """Show project summary."""
    project_dir = os.path.abspath(args.project_dir)
    project = _load_project(project_dir)

    print('Проект: %s' % project_dir)
    print('Версия: %d' % project.version)
    print()

    # Data files
    data_dir = os.path.join(project_dir, 'Данные')
    data_count = 0
    if os.path.exists(data_dir):
        data_count = len([f for f in os.listdir(data_dir)
                          if f.endswith(('.xlsx', '.xls'))])
    print('Файлов данных: %d' % data_count)

    # Templates
    tmpl_dir = os.path.join(project_dir, 'Шаблоны')
    tmpl_count = 0
    if os.path.exists(tmpl_dir):
        for root, dirs, files in os.walk(tmpl_dir):
            tmpl_count += len([f for f in files if f.endswith('.docx')])
    print('Шаблонов: %d' % tmpl_count)

    # Configured
    configured = len(project.templates)
    total_fields = sum(len(tc.fields) for tc in project.templates.values())
    total_cycles = sum(len(tc.cycles) for tc in project.templates.values())
    total_aggr = sum(len(tc.aggregations) for tc in project.templates.values())

    print('Настроенных шаблонов: %d' % configured)
    print('  Полей: %d' % total_fields)
    print('  Циклов: %d' % total_cycles)
    print('  Агрегаций: %d' % total_aggr)

    if configured:
        print()
        for tname, tc in project.templates.items():
            print('  📄 %s:' % tname)
            for fn, fm in tc.fields.items():
                detail = fm.type.value
                if fm.file:
                    detail += ' → %s.%s' % (fm.file, fm.column)
                elif fm.value:
                    detail += ': "%s"' % fm.value
                if fm.linked_to:
                    detail += ' (связано с %s)' % fm.linked_to
                print('      {{ %s }} — %s' % (fn, detail))
            if tc.cycles:
                for c in tc.cycles:
                    print('      [цикл] %s ← %s' % (
                        list(c.columns.keys()), c.table))
            if tc.aggregations:
                for aname, a in tc.aggregations.items():
                    print('      {{ %s }} = %s(%s.%s)' % (
                        aname, a.function.value, a.table, a.column))


# ============================================================
# Main parser
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='DocxForge CLI — генератор документов из командной строки',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примеры:
  python cli.py create ./МоиДокументы
  python cli.py scan ./МоиДокументы договор.docx
  python cli.py configure ./МоиДокументы договор.docx --field клиент table клиенты.xlsx --column название
  python cli.py configure ./МоиДокументы договор.docx --field doc_number counter --start 1 --format 0001
  python cli.py configure ./МоиДокументы договор.docx --cycle спецификация.xlsx наименование=наименование количество=количество цена=цена
  python cli.py configure ./МоиДокументы договор.docx --aggregation итого sum спецификация.xlsx цена
  python cli.py render ./МоиДокументы договор.docx
  python cli.py render ./МоиДокументы договор.docx --batch клиенты.xlsx
  python cli.py list ./МоиДокументы
  python cli.py info ./МоиДокументы
        ''',
    )

    subparsers = parser.add_subparsers(dest='command', help='Команды')

    # === create ===
    sp_create = subparsers.add_parser('create', help='Создать новый проект')
    sp_create.add_argument('project_dir', help='Путь к папке проекта')

    # === scan ===
    sp_scan = subparsers.add_parser('scan', help='Просканировать шаблон на плейсхолдеры')
    sp_scan.add_argument('project_dir', help='Путь к проекту')
    sp_scan.add_argument('template', help='Имя файла шаблона (в Шаблоны/)')

    # === configure ===
    sp_cfg = subparsers.add_parser('configure', help='Настроить поля шаблона')
    sp_cfg.add_argument('project_dir', help='Путь к проекту')
    sp_cfg.add_argument('template', help='Имя файла шаблона')
    sp_cfg.add_argument('--field', help='Имя поля для настройки')
    sp_cfg.add_argument('--field-type', dest='field_type',
                         help='Тип поля: constant, table, counter, today, image')
    sp_cfg.add_argument('--value', help='Значение (для constant/image) или файл (для table)')
    sp_cfg.add_argument('--column', help='Имя столбца в Excel (для table)')
    sp_cfg.add_argument('--linked-to', dest='linked_to',
                         help='Связать с другим полем (для table)')
    sp_cfg.add_argument('--start', help='Начальное значение (для counter)')
    sp_cfg.add_argument('--format', help='Формат: 0001 (для counter) или dd.MM.yyyy (для today)')
    sp_cfg.add_argument('--cycle', nargs='+',
                         help='Добавить цикл: ТАБЛИЦА поле1=столбец1 поле2=столбец2 ...')
    sp_cfg.add_argument('--aggregation', nargs=4,
                         metavar=('NAME', 'FUNC', 'TABLE', 'COLUMN'),
                         help='Добавить агрегацию: ИМЯ ФУНКЦИЯ ТАБЛИЦА СТОЛБЕЦ')
    sp_cfg.add_argument('--multiplier', help='Множитель для sum_multiply')

    # === render ===
    sp_render = subparsers.add_parser('render', help='Сгенерировать документы')
    sp_render.add_argument('project_dir', help='Путь к проекту')
    sp_render.add_argument('template', help='Имя файла шаблона')
    sp_render.add_argument('--batch', help='Excel-файл для пакетной генерации')
    sp_render.add_argument('--output', help='Папка для выходных файлов')

    # === list ===
    sp_list = subparsers.add_parser('list', help='Показать содержимое проекта')
    sp_list.add_argument('project_dir', help='Путь к проекту')
    sp_list.add_argument('--data', action='store_true', help='Показать файлы данных')
    sp_list.add_argument('--config', action='store_true', help='Показать настройки')

    # === info ===
    sp_info = subparsers.add_parser('info', help='Сводка по проекту')
    sp_info.add_argument('project_dir', help='Путь к проекту')

    args = parser.parse_args()

    if args.command == 'create':
        cmd_create(args)
    elif args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'configure':
        cmd_configure(args)
    elif args.command == 'render':
        cmd_render(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'info':
        cmd_info(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
