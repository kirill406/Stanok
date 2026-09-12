# -*- coding: utf-8 -*-
"""Product version checks."""

import os
import subprocess
import sys

import docxforge


def test_product_version_defined():
    assert docxforge.__version__ == '0.1.0-alpha'


def test_cli_version_flag_reports_product_version():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        [sys.executable, os.path.join(repo_root, 'cli.py'), '--version'],
        capture_output=True, text=True, cwd=repo_root)
    assert proc.returncode == 0
    assert '0.1.0-alpha' in proc.stdout
