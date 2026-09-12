# -*- coding: utf-8 -*-
"""Project generation function: UI-free entry point for rendering documents."""

import os
from typing import List, Optional

from docxforge.engine.schema import Project, ResumeState
from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer


class GenerationError(Exception):
    """Raised when document generation fails."""
    pass


def generate_project(
    project_path: str,
    template_name: Optional[str] = None,
    num_docs: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> List[str]:
    """
    Generate documents for a project using saved configuration.

    Args:
        project_path: Path to project directory (containing проект.docxforge)
        template_name: Template filename (relative to Шаблоны/). If None, uses first configured.
        num_docs: Maximum number of documents to generate (overrides project config)
        output_dir: Output directory. If None, uses <project>/output/

    Returns:
        List of generated output file paths.

    Raises:
        GenerationError: If project/template not found or generation fails.
    """
    project_file = os.path.join(project_path, 'проект.docxforge')
    if not os.path.exists(project_file):
        raise GenerationError(f'Project file not found: {project_file}')

    project = Project.from_file(project_file)
    if not project.templates:
        raise GenerationError('No templates configured in project')

    # Determine template to use
    if template_name is None:
        template_name = next(iter(project.templates.keys()))
    elif template_name not in project.templates:
        raise GenerationError(f'Template not configured: {template_name}')

    # Check template file exists
    template_full = os.path.join(project_path, 'Шаблоны', template_name)
    if not os.path.exists(template_full):
        raise GenerationError(f'Template file not found: {template_full}')

    # Prepare renderer
    data_reader = DataReader()
    renderer = Renderer(project_path, data_reader)
    renderer.project = project

    # Output directory
    if output_dir is None:
        # Backward compatibility: use existing "output" folder if present
        legacy_output = os.path.join(project_path, 'output')
        new_output = os.path.join(project_path, 'Результат')
        if os.path.exists(legacy_output):
            output_dir = legacy_output
        else:
            output_dir = new_output
    os.makedirs(output_dir, exist_ok=True)

    # Get resume state from project config for persistence
    template_config = project.templates[template_name]
    resume = template_config.resume
    if resume is None:
        resume = ResumeState(continue_from_last=True)

    # Render with resume state persistence
    try:
        outputs = renderer.render(
            template_name,
            {},
            output_dir=output_dir,
            max_docs=num_docs,
            resume=resume,
        )
    except Exception as e:
        raise GenerationError(f'Generation failed: {e}') from e

    if not outputs:
        raise GenerationError('No documents generated (check data sources and batch config)')

    # Save project to persist resume state (counter, source positions)
    renderer.save_project()

    return outputs


def generate_cli(project_path: str, template: str = None, count: int = None, out: str = None) -> List[str]:
    """CLI-friendly wrapper that prints progress."""
    print(f'Project: {project_path}')
    print(f'Template: {template or "first configured"}')
    print(f'Count: {count or "auto"}')
    print(f'Output: {out or "<project>/output/"}')

    outputs = generate_project(project_path, template, count, out)

    print(f'Generated: {len(outputs)} document(s)')
    for o in outputs:
        print(f'  {os.path.basename(o)}')
    return outputs