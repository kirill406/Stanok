# -*- coding: utf-8 -*-
"""Application-wide logging setup (SPEC 002, block B2).

Single source of truth for the shared application log file location.
The log lives in the user's Home directory, so it survives application
restarts and reinstalls (unlike a log file next to the exe/script).

Do not hardcode the log path or file name anywhere else — import
``APP_LOG_FILE`` / ``setup_app_logging`` from this module instead.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# The one and only place defining where the shared application log lives.
APP_LOG_FILE = os.path.join(os.path.expanduser('~'), '.docxforge', 'docxforge.log')

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_MAX_BYTES = 5_000_000
LOG_BACKUP_COUNT = 3


def setup_app_logging(level=logging.INFO):
    """Configure root logging: stdout + rotating file at ``APP_LOG_FILE``.

    The file handler opens in append mode, so records written before a
    restart are preserved. Safe to call once at startup; repeated calls
    do not duplicate handlers.
    Returns the log file path.
    """
    log_dir = os.path.dirname(APP_LOG_FILE)
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        logging.basicConfig(level=level, format=LOG_FORMAT,
                            handlers=[logging.StreamHandler(sys.stdout)])
        logging.getLogger(__name__).warning(
            'Could not create log directory, file logging disabled')
        return APP_LOG_FILE

    root = logging.getLogger()
    # Idempotent: only add handlers that are not there yet, and never
    # remove foreign handlers (keeps pytest caplog working in tests).
    has_file_handler = any(
        isinstance(h, RotatingFileHandler)
        and getattr(h, 'baseFilename', None) == APP_LOG_FILE
        for h in root.handlers)
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
        for h in root.handlers)

    formatter = logging.Formatter(LOG_FORMAT)
    if not has_file_handler:
        file_handler = RotatingFileHandler(
            APP_LOG_FILE, maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    if not has_stream_handler:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)
    root.setLevel(level)
    return APP_LOG_FILE
