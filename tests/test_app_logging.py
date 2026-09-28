# -*- coding: utf-8 -*-
"""Tests for shared application logging (SPEC 002, block B2)."""

import logging
import os

import pytest

from docxforge import app_logging


@pytest.fixture
def isolated_root_logging():
    """Snapshot root handlers, restore after test (setup_app_logging mutates root)."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield root
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)


def _close_test_handlers(root, log_path):
    """Close handlers pointing at log_path to simulate process exit."""
    for handler in list(root.handlers):
        if getattr(handler, 'baseFilename', None) == log_path:
            root.removeHandler(handler)
            handler.close()


def test_app_logging_path_in_home():
    """APP_LOG_FILE must live in Home with the fixed file name."""
    home = os.path.expanduser('~')
    assert app_logging.APP_LOG_FILE.startswith(home)
    assert os.path.basename(app_logging.APP_LOG_FILE) == 'docxforge.log'


def test_app_logging_setup_appends_after_restart(isolated_root_logging, tmp_path, monkeypatch):
    """Log file content survives a simulated restart (append, not overwrite)."""
    log_path = str(tmp_path / 'docxforge.log')
    monkeypatch.setattr(app_logging, 'APP_LOG_FILE', log_path)

    # First "run".
    app_logging.setup_app_logging()
    logging.getLogger('phase4-test').info('MARKER_FIRST_RUN')
    _close_test_handlers(isolated_root_logging, log_path)

    # Second "run" (fresh process): must append, not truncate.
    app_logging.setup_app_logging()
    logging.getLogger('phase4-test').info('MARKER_SECOND_RUN')
    _close_test_handlers(isolated_root_logging, log_path)

    with open(log_path, encoding='utf-8') as f:
        content = f.read()
    assert 'MARKER_FIRST_RUN' in content
    assert 'MARKER_SECOND_RUN' in content


def test_app_logging_setup_does_not_duplicate_handlers(isolated_root_logging, tmp_path, monkeypatch):
    """Repeated setup must not stack duplicate file handlers."""
    log_path = str(tmp_path / 'docxforge.log')
    monkeypatch.setattr(app_logging, 'APP_LOG_FILE', log_path)

    app_logging.setup_app_logging()
    app_logging.setup_app_logging()

    file_handlers = [h for h in isolated_root_logging.handlers
                     if getattr(h, 'baseFilename', None) == log_path]
    assert len(file_handlers) == 1
    _close_test_handlers(isolated_root_logging, log_path)


def test_app_logging_path_single_source_of_truth():
    """Literal 'docxforge.log' must appear only in app_logging.py (no hardcode)."""
    import docxforge

    package_dir = os.path.dirname(os.path.abspath(docxforge.__file__))
    offenders = []
    for dirpath, _, filenames in os.walk(package_dir):
        for name in filenames:
            if not name.endswith('.py'):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding='utf-8') as f:
                if 'docxforge.log' in f.read() and full != os.path.join(package_dir, 'app_logging.py'):
                    offenders.append(full)
    assert offenders == [], f'hardcoded log path in: {offenders}'

    repo_root = os.path.dirname(package_dir)  # src/ -> repo root layout root
    for candidate in ('run.py', 'cli.py'):
        path = os.path.join(os.path.dirname(repo_root), candidate)
        if os.path.isfile(path):
            with open(path, encoding='utf-8-sig') as f:
                content = f.read()
            if candidate == 'run.py':
                # run.py may only reference the log via the app_logging import.
                assert 'app_logging' in content
                assert "'docxforge.log'" not in content and '"docxforge.log"' not in content
