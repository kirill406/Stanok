# -*- coding: utf-8 -*-
"""CLI helper functions: project loading and saving."""

import os
import sys

from docxforge.engine.schema import Project, TemplateConfig


def _load_project(project_dir: str) -> Project:
    from docxforge.generate import resolve_project_file
    pf = resolve_project_file(project_dir)
    if not pf or not os.path.exists(pf):
        # Runtime error (exit 1): errors go to stderr, results stay on stdout.
        print('Ошибка: проект не найден в %s' % project_dir, file=sys.stderr)
        print('Создайте проект: python cli.py create %s' % project_dir,
              file=sys.stderr)
        sys.exit(1)
    return Project.from_file(pf)


def _save_project(project: Project, project_dir: str):
    project.to_file(os.path.join(project_dir, '\u043f\u0440\u043e\u0435\u043a\u0442.docxforge'))


def _get_or_create_template(project: Project, template: str) -> TemplateConfig:
    return project.templates.setdefault(template, TemplateConfig())
