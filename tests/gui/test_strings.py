# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for STRINGS: no Qt, non-empty keys, no Cyrillic literals elsewhere."""

import ast
import string
import sys
from pathlib import Path

from stanok.gui.strings import STRINGS

SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "stanok"


def _has_cyrillic(text: str) -> bool:
    return any("А" <= c <= "я" or c in "Ёё" for c in text)


def test_import_without_qt():
    source = (SRC_ROOT / "gui" / "strings.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert "PyQt5" not in imports
    assert "stanok.gui.strings" in sys.modules


def test_all_keys_non_empty():
    keys = [k for k in vars(STRINGS) if k.isupper()]
    assert keys, "STRINGS has no keys"
    for key in keys:
        value = getattr(STRINGS, key)
        assert isinstance(value, str) and value.strip(), f"empty key: {key}"


def test_placeholders_format():
    fmt = string.Formatter()
    for key in [k for k in vars(STRINGS) if k.isupper()]:
        value = getattr(STRINGS, key)
        fields = [f[1] for f in fmt.parse(value) if f[1]]
        assert len(fields) == len(set(fields)), f"dup placeholder in {key}"
        value.format(**{name: "X" for name in fields})


def _docstring_lines(tree: ast.AST) -> set[int]:
    """Line numbers of docstrings (module/class/function first-statement strings)."""
    lines = set()

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = child.body
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    lines.add(body[0].lineno)
            visit(child)

    visit(tree)
    return lines


def test_no_cyrillic_literals_outside_strings():
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path.name == "strings.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = _docstring_lines(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.lineno not in docstrings
                and _has_cyrillic(node.value)
            ):
                offenders.append(f"{path.relative_to(SRC_ROOT)}:{node.lineno}")
    assert not offenders, f"Cyrillic literals outside strings.py: {offenders}"
