# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Global test isolation: redirect app Home (logs, settings) to tmp."""

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_app_home(tmp_path, monkeypatch):
    monkeypatch.setenv("STANOK_HOME", str(tmp_path / "home"))
