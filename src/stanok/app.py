# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap (CLI/GUI startup lives here, not in __init__)."""

from __future__ import annotations

import argparse
import logging
import sys

from .gui.strings import STRINGS

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: generate docx from project folder (GUI lands later)."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="stanok", description=STRINGS.APP_DESCR)
    parser.add_argument("project_ref", help=STRINGS.APP_REF_HELP)
    parser.add_argument("--template", default=None, help=STRINGS.APP_TEMPLATE_HELP)
    parser.add_argument("--data-source", default=None, help=STRINGS.APP_SOURCE_HELP)
    parser.add_argument("--max-docs", type=int, default=None, help=STRINGS.APP_MAXDOCS_HELP)
    parser.add_argument("--resume", action="store_true", help=STRINGS.APP_RESUME_HELP)
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
        logger.error(STRINGS.APP_INTERRUPTED.format(error=e), exc_info=True)
        return 1
    print(
        STRINGS.APP_DONE.format(
            created=report.created,
            skipped=report.skipped,
            errors=len(report.errors),
            elapsed=f"{report.elapsed:.1f}",
        )
    )
    for path in report.output_paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
