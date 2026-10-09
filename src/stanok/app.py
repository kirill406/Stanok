# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap (CLI/GUI startup lives here, not in __init__)."""

from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: generate docx from project folder (GUI lands later)."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="stanok", description="Генерация docx из проекта")
    parser.add_argument("project_ref", help="Папка проекта или имя конфига")
    parser.add_argument("--template", default=None, help="Имя шаблона")
    parser.add_argument("--data-source", default=None, help="Имя источника данных")
    parser.add_argument("--max-docs", type=int, default=None, help="Лимит документов")
    parser.add_argument("--resume", action="store_true", help="Продолжить с start_row")
    args = parser.parse_args(argv)

    from .services.generate import GenerateCommand, generate_documents

    try:
        report = generate_documents(
            GenerateCommand(
                project_ref=args.project_ref,
                template=args.template,
                data_source=args.data_source,
                max_docs=args.max_docs,
                resume=args.resume,
            )
        )
    except Exception as e:
        logger.error(f"генерация прервана: {e}", exc_info=True)
        return 1
    # TODO(007): строки через gui.strings
    print(
        f"Готово: создано {report.created}, пропущено {report.skipped}, "
        f"ошибок {len(report.errors)} за {report.elapsed:.1f} с"
    )
    for path in report.output_paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
