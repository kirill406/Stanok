# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap (CLI/GUI startup lives here, not in __init__)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .gui.strings import STRINGS

logger = logging.getLogger(__name__)

LOG_FILE = "stanok.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 3

_HOOKS_INSTALLED = False
_QT_HANDLER_INSTALLED = False
_CRASH_BRIDGE = None


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
        root.warning(f"file logging disabled: {e}", exc_info=True)
    level = _stored_log_level(home)
    root.setLevel(level)
    root._stanok_configured = True  # type: ignore[attr-defined]
    logger.debug(
        f"logging configured: home={home} level={logging.getLevelName(level)} "
        f"file={home / LOG_FILE}"
    )
    return home


def _stored_log_level(home: Path) -> int:
    """Read log level from AJ settings (INFO default / on any error)."""
    import json

    settings_file = home / "settings.json"
    if not settings_file.exists():
        return logging.INFO
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        name = str(data.get("settings", {}).get("log_level", "INFO")).upper()
        return {"DEBUG": logging.DEBUG, "INFO": logging.INFO,
                "WARNING": logging.WARNING, "ERROR": logging.ERROR}[name]
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"cannot read log level from {home}: {e}", exc_info=True)
        return logging.INFO
    except Exception as e:
        logger.critical(
            f"unexpected error reading log level from {home}: {e}", exc_info=True
        )
        return logging.INFO


def _session_stamp() -> str:
    """Human-readable local timestamp for session separators."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log_session_start(mode: str, home: Path) -> None:
    """Write a full session header (versions, mode, PID, log home)."""
    from . import __version__

    try:
        from .engine.schema import current_version

        pj_version = current_version()
    except Exception as e:
        logger.warning(f"cannot read PJ schema version: {e}", exc_info=True)
        pj_version = "?"
    logger.info(
        f"===== START {_session_stamp()} | stanok {__version__} | "
        f"PJ {pj_version} | mode={mode} | pid={os.getpid()} | home={home} ====="
    )


def _log_session_end(code: int) -> None:
    """Write the matching session footer with the final exit code."""
    logger.info(f"===== END {_session_stamp()} | exit={code} =====")


def _handle_qt_message(mode, _context, message: str) -> None:
    """Route Qt diagnostics into the log; never pop dialogs here."""
    from PyQt5.QtCore import (
        QtCriticalMsg,
        QtDebugMsg,
        QtFatalMsg,
        QtInfoMsg,
        QtWarningMsg,
    )

    level = {
        QtDebugMsg: logging.DEBUG,
        QtInfoMsg: logging.INFO,
        QtWarningMsg: logging.WARNING,
        QtCriticalMsg: logging.CRITICAL,
        QtFatalMsg: logging.CRITICAL,
    }.get(mode, logging.WARNING)
    logger.log(level, f"Qt: {message}")


def _show_crash_dialog(message: str) -> None:
    """Show a blocking crash message only when a Qt app already exists."""
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return
        QMessageBox.critical(
            None,
            STRINGS.MAIN_ERROR_TITLE,
            STRINGS.APP_CRASH.format(error=message),
        )
    except Exception as e:
        logger.critical(f"cannot show crash dialog: {e}", exc_info=True)


def _notify_crash(message: str) -> None:
    """Deliver a crash message to the GUI thread when a bridge exists."""
    if _CRASH_BRIDGE is not None:
        try:
            _CRASH_BRIDGE.crashed.emit(message)
            return
        except Exception as e:
            logger.critical(
                f"crash notification failed: {e}", exc_info=True
            )
    _show_crash_dialog(message)


def _handle_unhandled(exc_type, exc_value, exc_traceback) -> None:
    """Global sys.excepthook: log with traceback and inform the GUI user."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical(
        f"unhandled exception: {exc_type.__name__}: {exc_value}",
        exc_info=(exc_type, exc_value, exc_traceback),
    )
    _notify_crash(str(exc_value) or exc_type.__name__)


def _handle_thread_unhandled(args) -> None:
    """Global threading.excepthook: log worker-thread crashes with traceback."""
    if args.exc_type is SystemExit:
        return
    name = args.thread.name if args.thread is not None else "unknown"
    logger.critical(
        f"unhandled exception in thread {name}: "
        f"{args.exc_type.__name__}: {args.exc_value}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    _notify_crash(str(args.exc_value) or args.exc_type.__name__)


def _install_exception_hooks() -> None:
    """Install sys/threading hooks once (Qt handler is installed in create_gui)."""
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    sys.excepthook = _handle_unhandled
    threading.excepthook = _handle_thread_unhandled
    _HOOKS_INSTALLED = True
    logger.debug("global sys/threading exception hooks installed")


def _install_gui_hooks(qt_app) -> None:
    """Install Qt message routing and a thread-safe crash-dialog bridge."""
    global _CRASH_BRIDGE, _QT_HANDLER_INSTALLED

    from PyQt5.QtCore import QObject, pyqtSignal, qInstallMessageHandler

    class _CrashBridge(QObject):
        crashed = pyqtSignal(str)

    bridge = _CrashBridge()
    bridge.crashed.connect(_show_crash_dialog)
    qt_app._stanok_crash_bridge = bridge  # type: ignore[attr-defined]
    _CRASH_BRIDGE = bridge
    if not _QT_HANDLER_INSTALLED:
        qInstallMessageHandler(_handle_qt_message)
        _QT_HANDLER_INSTALLED = True
        logger.debug("Qt message handler installed")


def _run_cli(args) -> int:
    """Generate for a project from the command line."""
    from .engine.render import RenderError
    from .engine.resolve import ResolveError
    from .services.generate import GenerateCommand, TemplateError, generate_documents
    from .services.storage import StorageError

    logger.debug(
        f"CLI run: project_ref={args.project_ref} template={args.template or 'default'}"
    )
    try:
        report = generate_documents(
            GenerateCommand(
                project_ref=args.project_ref,
                template=args.template,
            )
        )
    except (TemplateError, StorageError, ResolveError, RenderError) as e:
        logger.error(f"CLI generation failed: {e}", exc_info=True)
        print(STRINGS.APP_INTERRUPTED.format(error=e))
        return 1
    except Exception as e:
        logger.critical(f"CLI generation unexpected error: {e}", exc_info=True)
        print(STRINGS.APP_INTERRUPTED.format(error=e))
        return 1
    print(
        STRINGS.APP_DONE.format(
            created=report.created,
            errors=len(report.errors),
            elapsed=f"{report.elapsed:.1f}",
        )
    )
    for path in report.output_paths:
        print(f"  {path}")
    for index, message in report.errors:
        logger.warning(f"CLI document {index} failed: {message}")
        print(STRINGS.APP_ERROR_LINE.format(index=index, error=message))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `stanok <project>` generates; bare `stanok` opens GUI."""
    home = _setup_logging()
    _install_exception_hooks()
    parser = argparse.ArgumentParser(prog="stanok", description=STRINGS.APP_DESCR)
    parser.add_argument(
        "project_ref", nargs="?", default=None, help=STRINGS.APP_REF_HELP
    )
    parser.add_argument("--template", default=None, help=STRINGS.APP_TEMPLATE_HELP)
    args = parser.parse_args(argv)

    mode = "GUI" if args.project_ref is None else "CLI"
    _log_session_start(mode, home)
    code = 1
    try:
        if args.project_ref is None:
            code = _run_gui()
        else:
            code = _run_cli(args)
    except KeyboardInterrupt:
        logger.warning("interrupted by user (KeyboardInterrupt)")
        code = 130
    except Exception as e:
        logger.critical(f"unhandled exception in {mode}: {e}", exc_info=True)
        _notify_crash(str(e) or e.__class__.__name__)
        code = 1
    finally:
        _log_session_end(code)
    return code


def _run_gui() -> int:
    """Open main window (imports Qt lazily so CLI stays light)."""
    qt_app, window = create_gui()
    logger.debug("showing main window")
    window.show()
    return qt_app.exec_()


def _install_qt_translation(qt_app) -> None:
    """Translate Qt's own strings (file dialogs, standard buttons) to Russian."""
    from PyQt5.QtCore import QLibraryInfo, QTranslator

    if getattr(qt_app, "_stanok_translator", None) is not None:
        return
    path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    translator = QTranslator(qt_app)
    if translator.load("qtbase_ru", path):
        qt_app.installTranslator(translator)
        qt_app._stanok_translator = translator  # type: ignore[attr-defined]
    else:
        logger.warning(f"Qt Russian translation not found in {path}")


def create_gui(store=None):
    """Build QApplication + MainWindow without exec_ (tests, embedding).

    Creates one shared ProjectStore when none is passed.
    """
    from PyQt5.QtWidgets import QApplication

    from .gui.icons import apply_app_icon
    from .gui.main_window import MainWindow
    from .gui.theme import apply_theme
    from .services.storage import ProjectStore

    qt_app = QApplication.instance() or QApplication([])
    _install_gui_hooks(qt_app)
    _install_qt_translation(qt_app)
    apply_theme(qt_app)
    apply_app_icon(qt_app)
    window = MainWindow(store=store if store is not None else ProjectStore())
    return qt_app, window


if __name__ == "__main__":  # pragma: no cover - entry guard
    sys.exit(main())
