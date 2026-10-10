# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for PJ/AJ/Filling schemas."""

import json
from pathlib import Path

import pytest

from stanok.engine import schema
from stanok.engine.schema import (
    AJValidationError,
    FillingJSON,
    FillingValidationError,
    FormatTooNewError,
    PJValidationError,
    migrate,
    normalize,
    validate_aj,
    validate_fj,
    validate_pj,
)


FIXTURE_DIR = Path(__file__).parent.parent / "json" / "002-schema"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_validate_pj_minimal():
    pj = validate_pj(_load("pj_minimal.stanok"))
    assert pj.version == "0.0.0"
    assert set(pj.templates) == {"Договор"}


def test_validate_pj_full():
    pj = validate_pj(_load("pj_full.stanok"))
    assert pj.counters["doc_num"].last == 42
    assert pj.counters["act_num"].format == "month"
    assert pj.data_sources[1].mode == "circular"
    assert pj.data_sources[1].start_row == 5


def test_validate_fj_example():
    fj = validate_fj(_load("fj_example.json"))
    assert isinstance(fj, FillingJSON)
    assert fj.dist == "Результат/Договор №43.docx"
    assert fj.fields["Номер"] == 43


def test_validate_aj_example():
    aj = validate_aj(_load("aj_example.json"))
    assert len(aj.recent) == 1
    assert "templates" not in aj.settings


def test_extra_keys_warn_not_fail(caplog):
    data = _load("pj_minimal.stanok")
    data["unknown_future_key"] = 1
    with caplog.at_level("WARNING", logger="stanok.engine.schema"):
        pj = validate_pj(data)
    assert pj.version == "0.0.0"
    assert any("unknown keys" in r.message for r in caplog.records)


def test_broken_type_path():
    with pytest.raises(PJValidationError) as exc_info:
        validate_pj(_load("pj_broken_type.stanok"))
    assert exc_info.value.path == "$"


def test_fj_bad_fields_type():
    with pytest.raises(FillingValidationError) as exc_info:
        validate_fj({"version": "0.0.0", "template": "X", "fields": "not-a-dict"})
    assert exc_info.value.path == "$"


def test_aj_bad_recent_type():
    with pytest.raises(AJValidationError) as exc_info:
        validate_aj({"version": "0.0.0", "recent": "nope"})
    assert exc_info.value.path == "$"


def test_migrate_chain(monkeypatch):
    monkeypatch.setattr(schema, "_get_package_version", lambda: "0.1.0")
    monkeypatch.setitem(
        schema.MIGRATIONS,
        ("0.0.0", "0.1.0"),
        lambda d: {**d, "version": "0.1.0", "migrated": True},
    )
    out = migrate({"version": "0.0.0"})
    assert out["version"] == "0.1.0"
    assert out["migrated"] is True


def test_migrate_missing_step(monkeypatch):
    monkeypatch.setattr(schema, "_get_package_version", lambda: "0.2.0")
    with pytest.raises(FormatTooNewError):
        migrate({"version": "0.0.1"})


@pytest.mark.parametrize("validator,model", [
    (validate_pj, "ProjectJSON"),
    (validate_aj, "ApplicationJSON"),
    (validate_fj, "FillingJSON"),
])
def test_validate_unexpected_error_logged(monkeypatch, caplog, validator, model):
    def boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(schema, model, boom)
    with caplog.at_level("ERROR", logger="stanok.engine.schema"):
        with pytest.raises(RuntimeError):
            validator({})
    assert any("boom" in r.message for r in caplog.records)


def test_dotdot_path_rejected():
    with pytest.raises(PJValidationError):
        validate_pj(_load("pj_broken_path.stanok"))


def test_future_version_rejected():
    data = _load("pj_minimal.stanok")
    data["version"] = "99.0.0"
    with pytest.raises(FormatTooNewError):
        migrate(data)


def test_migrate_same_version_passthrough():
    data = _load("pj_minimal.stanok")
    assert migrate(dict(data))["version"] == schema.current_version()


def test_aj_recent_capped_and_deduped():
    aj = validate_aj(_load("aj_many_recent.json"))
    assert len(aj.recent) == 10
    data = _load("aj_many_recent.json")
    data["recent"].append(data["recent"][0])
    aj2 = validate_aj(data)
    assert len(aj2.recent) == 10
    assert aj2.recent[0].folder == "C:/Docs/P01"


def test_engine_has_no_qt(tmp_path):
    import subprocess
    import sys

    code = "import stanok.engine.schema, sys; print('qt' in ''.join(sys.modules))"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path
    )
    assert out.stdout.strip() == "False"


def test_normalize_strips_strings():
    assert normalize({"a": "  x  ", "n": {"b": ["  y  ", 1]}}) == {
        "a": "x",
        "n": {"b": ["y", 1]},
    }


def test_normalize_tuple_to_list():
    assert normalize(("a", "  b  ", 1)) == ["a", "b", 1]


def test_get_package_version_not_installed(monkeypatch):
    # Patch the bound name (schema.pkg_version), not importlib.metadata.version.
    import importlib.metadata

    import stanok.engine.schema as schema_mod

    def raise_not_found(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(schema_mod, "pkg_version", raise_not_found)
    assert schema_mod._get_package_version() == "0.0.0"


def test_migrate_no_version_update(monkeypatch):
    monkeypatch.setattr(schema, "_get_package_version", lambda: "0.1.0")
    monkeypatch.setitem(
        schema.MIGRATIONS,
        ("0.0.0", "0.1.0"),
        lambda d: {**d, "version": "0.0.0"},  # doesn't update version
    )
    with pytest.raises(schema.SchemaError, match="didn't update version"):
        migrate({"version": "0.0.0"})
