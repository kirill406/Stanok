# -*- coding: utf-8 -*-
"""CLI info and list commands."""

import os
from .helpers import _load_project

def _print_templates_tree(base_dir, root_dir, depth):
    """Recursively print template tree."""
    items = sorted(os.listdir(base_dir))
    for name in items:
        full = os.path.join(base_dir, name)
        prefix = '  ' * depth
        if os.path.isdir(full):
            print(prefix + '\U0001f4c1 %s/' % name)
            _print_templates_tree(full, root_dir, depth + 1)
        elif name.endswith('.docx'):
            print(prefix + '\U0001f4c4 %s' % name)


def cmd_info(args):
    """Show project summary."""
    project_dir = os.path.abspath(args.project_dir)
    project = _load_project(project_dir)

    print('\u041f\u0440\u043e\u0435\u043a\u0442: %s' % project_dir)
    print('\u0412\u0435\u0440\u0441\u0438\u044f: %d' % project.version)
    print()

    data_dir = os.path.join(project_dir, '\u0414\u0430\u043d\u043d\u044b\u0435')
    data_count = 0
    if os.path.exists(data_dir):
        data_count = len([f for f in os.listdir(data_dir)
                          if f.endswith(('.xlsx', '.xls'))])
    print('\u0424\u0430\u0439\u043b\u043e\u0432 \u0434\u0430\u043d\u043d\u044b\u0445: %d' % data_count)

    tmpl_dir = os.path.join(project_dir, '\u0428\u0430\u0431\u043b\u043e\u043d\u044b')
    tmpl_count = 0
    if os.path.exists(tmpl_dir):
        for root, dirs, files in os.walk(tmpl_dir):
            tmpl_count += len([f for f in files if f.endswith('.docx')])
    print('\u0428\u0430\u0431\u043b\u043e\u043d\u043e\u0432: %d' % tmpl_count)

    configured = len(project.templates)
    total_fields = sum(len(tc.fields) for tc in project.templates.values())
    total_cycles = sum(len(tc.cycles) for tc in project.templates.values())
    total_aggr = sum(len(tc.aggregations) for tc in project.templates.values())

    print('\u041d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u043d\u044b\u0445 \u0448\u0430\u0431\u043b\u043e\u043d\u043e\u0432: %d' % configured)
    print('  \u041f\u043e\u043b\u0435\u0439: %d' % total_fields)
    print('  \u0426\u0438\u043a\u043b\u043e\u0432: %d' % total_cycles)
    print('  \u0410\u0433\u0440\u0435\u0433\u0430\u0446\u0438\u0439: %d' % total_aggr)

    if configured:
        print()
        for tname, tc in project.templates.items():
            print('  \U0001f4c4 %s:' % tname)
            for fn, fm in tc.fields.items():
                detail = fm.type.value
                if fm.file:
                    detail += ' \u2192 %s.%s' % (fm.file, fm.column)
                elif fm.value:
                    detail += ': "%s"' % fm.value
                if fm.linked_to:
                    detail += ' (\u0441\u0432\u044f\u0437\u0430\u043d\u043e \u0441 %s)' % fm.linked_to
                print('      {{ %s }} \u2014 %s' % (fn, detail))
            if tc.cycles:
                for c in tc.cycles:
                    print('      [\u0446\u0438\u043a\u043b] %s \u2190 %s' % (
                        list(c.columns.keys()), c.table))
            if tc.aggregations:
                for aname, a in tc.aggregations.items():
                    print('      {{ %s }} = %s(%s.%s)' % (
                        aname, a.function.value, a.table, a.column))
