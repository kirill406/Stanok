# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap (CLI/GUI startup lives here, not in __init__)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .gui.strings import STRINGS

logger = logging.getLogger(__name__)

LOG_FILE = "stanok.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 3


def _app_home() -> Path:
    """User Home dir, overridable via STANOK_HOME (tests, portable mode)."""
    override = os.environ.get("STANOK_HOME")
    return Path(override).expanduser() if override else Path.home() / ".stanok"


def _setup_logging() -> Path:
    """Console + rotating file logging in Home; level from AJ (018/NFR-5).

    Idempotent: repeated calls attach nothing twice.
    """
    home = _app_home()
    home.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if getattr(root, "_stanok_configured", False):
        return home
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        fh = RotatingFileHandler(
            home / LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as e:
        root.warning("file logging disabled: %s", e)
    level = _stored_log_level(home)
    root.setLevel(level)
    root._stanok_configured = True  # type: ignore[attr-defined]
    return home


def _stored_log_level(home: Path) -> int:
    """Read log level from AJ settings (INFO default / on any error)."""
    import json

    try:
        data = json.loads((home / "settings.json").read_text(encoding="utf-8"))
        name = str(data.get("settings", {}).get("log_level", "INFO")).upper()
        return {"DEBUG": logging.DEBUG, "INFO": logging.INFO,
                "WARNING": logging.WARNING, "ERROR": logging.ERROR}[name]
    except Exception:
        return logging.INFO


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `stanok <project>` generates; bare `stanok` opens GUI."""
    _setup_logging()
    parser = argparse.ArgumentParser(prog="stanok", description=STRINGS.APP_DESCR)
    parser.add_argument(
        "project_ref", nargs="?", default=None, help=STRINGS.APP_REF_HELP
    )
    parser.add_argument("--template", default=None, help=STRINGS.APP_TEMPLATE_HELP)
    parser.add_argument(
        "--data-source", "--source", dest="data_source", default=None,
        help=STRINGS.APP_SOURCE_HELP,
    )
    parser.add_argument("--max-docs", type=int, default=None, help=STRINGS.APP_MAXDOCS_HELP)
    parser.add_argument("--resume", action="store_true", help=STRINGS.APP_RESUME_HELP)
    args = parser.parse_args(argv)

    if args.project_ref is None:
        return _run_gui()

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


def _run_gui() -> int:
    """Open main window (imports Qt lazily so CLI stays light)."""
    qt_app, window = create_gui()
    window.show()
    return qt_app.exec_()


def create_gui(store=None):
    """Build QApplication + MainWindow without exec_ (tests, embedding).

    Creates one shared ProjectStore when none is passed.
    """
    from PyQt5.QtWidgets import QApplication

    from .gui.main_window import MainWindow
    from .services.storage import ProjectStore

    qt_app = QApplication.instance() or QApplication([])
    window = MainWindow(store=store if store is not None else ProjectStore())
    return qt_app, window


if __name__ == "__main__":
    sys.exit(main())
