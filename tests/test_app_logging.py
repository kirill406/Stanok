# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for app logging setup (018): file handler, levels, idempotency."""

import json
import logging
import logging.handlers

from stanok.app import LOG_FILE, _app_home, _setup_logging, _stored_log_level


def test_setup_logging_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("STANOK_HOME", str(tmp_path / "home"))
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    if hasattr(root, "_stanok_configured"):
        delattr(root, "_stanok_configured")
    try:
        home = _setup_logging()
        assert home == _app_home()
        assert (home / LOG_FILE).exists()
        kinds = {type(h) for h in root.handlers}
        assert logging.StreamHandler in kinds
        assert any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            for h in root.handlers
        )
        n_handlers = len(root.handlers)
        _setup_logging()
        assert len(root.handlers) == n_handlers
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        if hasattr(root, "_stanok_configured"):
            delattr(root, "_stanok_configured")


def test_stored_log_level(tmp_path):
    assert _stored_log_level(tmp_path) == logging.INFO
    home = tmp_path / "h"
    home.mkdir()
    (home / "settings.json").write_text(json.dumps({"settings": {"log_level": "warning"}}))
    assert _stored_log_level(home) == logging.WARNING
    (home / "settings.json").write_text(json.dumps({"settings": {"log_level": "nope"}}))
    assert _stored_log_level(home) == logging.INFO


def test_setup_logging_file_fallback(tmp_path, monkeypatch):
    import logging.handlers

    monkeypatch.setenv("STANOK_HOME", str(tmp_path / "home"))
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    if hasattr(root, "_stanok_configured"):
        delattr(root, "_stanok_configured")

    def boom(*a, **k):
        raise OSError("read-only")

    monkeypatch.setattr("stanok.app.RotatingFileHandler", boom)
    try:
        home = _setup_logging()
        assert home.exists()
        assert not (home / LOG_FILE).exists()
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        if hasattr(root, "_stanok_configured"):
            delattr(root, "_stanok_configured")


def test_run_gui_path(monkeypatch):
    import stanok.app as appmod

    calls = []

    class FakeWindow:
        def show(self):
            calls.append("show")

    class FakeQt:
        def exec_(self):
            calls.append("exec")
            return 0

    monkeypatch.setattr(
        appmod, "create_gui", lambda: (FakeQt(), FakeWindow())
    )
    assert appmod.main([]) == 0
    assert calls == ["show", "exec"]


def _reset_root() -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    if hasattr(root, "_stanok_configured"):
        delattr(root, "_stanok_configured")


def test_main_writes_session_separators(tmp_path, monkeypatch):
    import stanok.app as appmod

    monkeypatch.setenv("STANOK_HOME", str(tmp_path / "home"))
    _reset_root()

    class FakeWindow:
        def show(self):
            pass

    class FakeQt:
        def exec_(self):
            return 0

    monkeypatch.setattr(appmod, "create_gui", lambda: (FakeQt(), FakeWindow()))
    try:
        assert appmod.main([]) == 0
        text = (tmp_path / "home" / LOG_FILE).read_text(encoding="utf-8")
    finally:
        _reset_root()
    from stanok import __version__
    from stanok.engine.schema import current_version

    assert "===== START" in text
    assert f"stanok {__version__}" in text
    assert f"PJ {current_version()}" in text
    assert "mode=GUI" in text
    assert "===== END" in text
    assert "exit=0" in text


def test_unhandled_exception_hook_logs_and_notifies(monkeypatch, caplog):
    import stanok.app as appmod

    shown = []
    monkeypatch.setattr(appmod, "_notify_crash", shown.append)
    with caplog.at_level(logging.CRITICAL):
        appmod._handle_unhandled(ValueError, ValueError("boom"), None)
    assert shown == ["boom"]
    assert "unhandled exception: ValueError: boom" in caplog.text
