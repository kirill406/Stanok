# -*- coding: utf-8 -*-
"""CLI command implementations: create, scan, configure, render, list, info."""

import os
import sys

from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
    CycleMapping, AggregationMapping, AggregationFunction,
    create_project,
)
from docxforge.engine.template_parser import scan_template
from docxforge.engine.renderer import Renderer
from docxforge.engine.data_reader import DataReader
from .helpers import _load_project, _save_project, _get_or_create_template


def cmd_create(args):
    """Create a new project."""
    path = os.path.abspath(args.project_dir)
    pf = create_project(path)
    print('\u041f\u0440\u043e\u0435\u043a\u0442 \u0441\u043e\u0437\u0434\u0430\u043d: %s' % path)
    print('  \u0414\u0430\u043d\u043d\u044b\u0435/   \u2014 \u0441\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u044e\u0434\u0430 .xlsx \u0444\u0430\u0439\u043b\u044b')
    print('  \u0428\u0430\u0431\u043b\u043e\u043d\u044b/  \u2014 \u0441\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u0441\u044e\u0434\u0430 .docx \u0448\u0430\u0431\u043b\u043e\u043d\u044b')
    print('  \u043f\u0440\u043e\u0435\u043a\u0442.docxforge \u2014 \u0444\u0430\u0439\u043b \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043a (\u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439)')


def cmd_scan(args):
    """Scan a template for placeholders."""
    project_dir = os.path.abspath(args.project_dir)
    tmpl_path = os.path.join(project_dir, '\u0428\u0430\u0431\u043b\u043e\u043d\u044b', args.template)
    if not os.path.exists(tmpl_path):
        # Try as absolute path
        if os.path.exists(args.template):
            tmpl_path = args.template
        else:
            print('\u041e\u0448\u0438\u0431\u043a\u0430: \u0448\u0430\u0431\u043b\u043e\u043d \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d: %s' % args.template)
            sys.exit(1)

    result = scan_template(tmpl_path)
    simple = result['simple']
    today = result['today']
    doc_number = result['doc_number']
    image = result['image']
    total = len(simple) + len(today) + len(doc_number) + len(image)

    print('\u0428\u0430\u0431\u043b\u043e\u043d: %s' % args.template)
    print('\u041d\u0430\u0439\u0434\u0435\u043d\u043e \u043f\u043e\u043b\u0435\u0439: %d' % total)
    print()

    if simple:
        print('  \u041d\u0430\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0435\u043c\u044b\u0435 \u043f\u043e\u043b\u044f (%d):' % len(simple))
        for s in simple:
            print('    {{ %s }}' % s)
        print()

    if today:
        print('  \u0414\u0430\u0442\u044b (%d):' % len(today))
        for t in today:
            print('    {{ %s }} \u2014 \u0430\u0432\u0442\u043e\u043f\u043e\u0434\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430' % t)
        print()

    if doc_number:
        print('  \u041d\u043e\u043c\u0435\u0440\u0430 (%d):' % len(doc_number))
        for d in doc_number:
            print('    {{ %s }} \u2014 \u0441\u0447\u0451\u0442\u0447\u0438\u043a' % d)
        print()

    if image:
        print('  \u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f (%d):' % len(image))
        for i in image:
            print('    {{ image:%s }}' % i)
        print()


def cmd_configure(args):
    """Configure field mappings, cycles, aggregations."""
    project_dir = os.path.abspath(args.project_dir)
    project = _load_project(project_dir)
    tc = _get_or_create_template(project, args.template)

    if args.field:
        ftype = args.field_type.lower()
        fm = FieldMapping()

        if ftype == 'constant' or ftype == '\u043a\u043e\u043d\u0441\u0442\u0430\u043d\u0442\u0430':
            fm.type = FieldType.CONSTANT
            fm.value = args.value
        elif ftype == 'table' or ftype == '\u0442\u0430\u0431\u043b\u0438\u0446\u0430':
            fm.type = FieldType.TABLE
            fm.file = args.value
            fm.column = args.column
            if args.linked_to:
                fm.linked_to = args.linked_to
        elif ftype == 'counter' or ftype == '\u0441\u0447\u0451\u0442\u0447\u0438\u043a':
            fm.type = FieldType.COUNTER
            fm.start = int(args.start) if args.start else 1
            fm.format = args.format if args.format else '0001'
        elif ftype == 'today' or ftype == '\u0441\u0435\u0433\u043e\u0434\u043d\u044f':
            fm.type = FieldType.TODAY
            fm.format = args.format if args.format else 'dd.MM.yyyy'
        elif ftype == 'image' or ftype == '\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435':
            fm.type = FieldType.IMAGE
            fm.value = args.value
        else:
            print('\u041e\u0448\u0438\u0431\u043a\u0430: \u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u044b\u0439 \u0442\u0438\u043f \u043f\u043e\u043b\u044f: %s' % ftype)
            print('\u0414\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u0435: constant, table, counter, today, image')
            sys.exit(1)

        tc.fields[args.field] = fm
        print('\u041f\u043e\u043b\u0435 {{ %s }} \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u043e: \u0442\u0438\u043f=%s' % (args.field, ftype))

    if args.cycle:
        table = args.cycle[0]
        cols = {}
        for pair in args.cycle[1:]:
            if '=' in pair:
                k, v = pair.split('=', 1)
                cols[k.strip()] = v.strip()
        if cols:
            tc.cycles.append(CycleMapping(table=table, columns=cols))
            print('\u0426\u0438\u043a\u043b \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d: \u0442\u0430\u0431\u043b\u0438\u0446\u0430=%s, \u043f\u043e\u043b\u044f=%s' % (table, list(cols.keys())))

    if args.aggregation:
        name = args.aggregation[0]
        func = args.aggregation[1].lower()
        table = args.aggregation[2]
        column = args.aggregation[3]

        if func == 'sum_multiply':
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
        print('\u0410\u0433\u0440\u0435\u0433\u0430\u0446\u0438\u044f {{ %s }} \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u0430: %s(%s.%s)' % (name, func, table, column))

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

    print('\u0421\u043e\u0437\u0434\u0430\u043d\u043e \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432: %d' % len(outputs))
    if outputs:
        out_dir = os.path.dirname(outputs[0])
        print('\u041f\u0430\u043f\u043a\u0430: %s' % out_dir)
        for o in outputs:
            print('  %s' % os.path.basename(o))


def cmd_list(args):
    """List templates, data files, or config."""
    project_dir = os.path.abspath(args.project_dir)

    if args.data:
        data_dir = os.path.join(project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435')
        if os.path.exists(data_dir):
            files = sorted(os.listdir(data_dir))
            if files:
                print('\u0424\u0430\u0439\u043b\u044b \u0434\u0430\u043d\u043d\u044b\u0445 (%d):' % len(files))
                for f in files:
                    print('  \U0001f4ca %s' % f)
            else:
                print('\u041d\u0435\u0442 \u0444\u0430\u0439\u043b\u043e\u0432 \u0434\u0430\u043d\u043d\u044b\u0445')
        else:
            print('\u041f\u0430\u043f\u043a\u0430 \u0414\u0430\u043d\u043d\u044b\u0435/ \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430')

    elif args.config:
        project = _load_project(project_dir)
        if project.templates:
            print('\u041d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u043d\u044b\u0435 \u0448\u0430\u0431\u043b\u043e\u043d\u044b (%d):' % len(project.templates))
            for tname, tc in project.templates.items():
                fields = len(tc.fields)
                cycles = len(tc.cycles)
                aggr = len(tc.aggregations)
                print('  \U0001f4c4 %s \u2014 %d \u043f\u043e\u043b\u0435\u0439, %d \u0446\u0438\u043a\u043b\u043e\u0432, %d \u0430\u0433\u0440\u0435\u0433\u0430\u0446\u0438\u0439' % (
                    tname, fields, cycles, aggr))
        else:
            print('\u041d\u0435\u0442 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u043d\u044b\u0445 \u0448\u0430\u0431\u043b\u043e\u043d\u043e\u0432')

    else:
        tmpl_dir = os.path.join(project_dir, '\u0428\u0430\u0431\u043b\u043e\u043d\u044b')
        if os.path.exists(tmpl_dir):
            _print_templates_tree(tmpl_dir, tmpl_dir, 0)
        else:
            print('\u041f\u0430\u043f\u043a\u0430 \u0428\u0430\u0431\u043b\u043e\u043d\u044b/ \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430')


