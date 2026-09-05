# -*- coding: utf-8 -*-
"""CLI helper functions: project loading and saving."""

import os
import sys

from docxforge.engine.schema import Project, TemplateConfig


def _load_project(project_dir: str) -> Project:
    pf = os.path.join(project_dir, '\u043f\u0440\u043e\u0435\u043a\u0442.docxforge')
    if not os.path.exists(pf):
        print('\u041e\u0448\u0438\u0431\u043a\u0430: \u043f\u0440\u043e\u0435\u043a\u0442 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0432 %s' % project_dir)
        print('\u0421\u043e\u0437\u0434\u0430\u0439\u0442\u0435 \u043f\u0440\u043e\u0435\u043a\u0442: python cli.py create %s' % project_dir)
        sys.exit(1)
    return Project.from_file(pf)


def _save_project(project: Project, project_dir: str):
    project.to_file(os.path.join(project_dir, '\u043f\u0440\u043e\u0435\u043a\u0442.docxforge'))


def _get_or_create_template(project: Project, template: str) -> TemplateConfig:
    return project.templates.setdefault(template, TemplateConfig())
