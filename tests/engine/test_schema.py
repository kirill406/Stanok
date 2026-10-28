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
    assert pj.counters["doc_num"].pos == 42
    assert pj.counters["act_num"].format == "month"
    assert pj.data_sources[1].mode == "circular"
    assert pj.counters["proj"].pos == 5
    assert pj.templates["Договор"].limit == 10
    assert pj.default_template == "Договор"
    assert pj.templates["Договор"].fields["ФИО"].counter_name == "emp"


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
    data["version"] = schema.current_version()
    assert migrate(dict(data))["version"] == schema.current_version()


def test_parse_version_accepts_pep440_prerelease():
    assert schema._parse_version("0.2.0a0") == (0, 2, 0)
    assert schema._parse_version("0.2.0-alpha") == (0, 2, 0)


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


def _pj(table_field: dict, counters: dict, sources=None) -> dict:
    if sources is None:
        sources = [{"file": "Данные/d.xlsx", "mode": "sequential"}]
    return {
        "version": "0.0.0",
        "templates": {"T": {"file": "Шаблоны/t.docx", "fields": {"F": table_field}}},
        "data_sources": sources,
        "counters": counters,
        "filename_template": "Д_{i}.docx",
    }


def test_field_needs_counter_name():
    with pytest.raises(PJValidationError, match="counter_name"):
        validate_pj(_pj({"source": "table", "value": "col"}, {}))


def test_field_counter_must_exist():
    with pytest.raises(PJValidationError, match="not defined"):
        validate_pj(
            _pj(
                {"source": "table", "value": "col", "counter_name": "ghost"},
                {},
            )
        )


def test_field_counter_must_be_bound():
    with pytest.raises(PJValidationError, match="not bound"):
        validate_pj(
            _pj(
                {"source": "table", "value": "col", "counter_name": "num"},
                {"num": {"pos": 0, "format": "1"}},
            )
        )


def test_field_counter_ok():
    pj = validate_pj(
        _pj(
            {"source": "table", "value": "col", "counter_name": "emp"},
            {"emp": {"format": "1", "table": "Данные/d.xlsx"}},
        )
    )
    assert pj.templates["T"].fields["F"].counter_name == "emp"


def test_counter_field_must_exist():
    with pytest.raises(PJValidationError, match="counter field"):
        validate_pj(
            _pj({"source": "counter", "value": "ghost"}, {}, sources=[])
        )


def test_counter_field_ok():
    pj = validate_pj(
        _pj(
            {"source": "counter", "value": "num"},
            {"num": {"pos": 0, "format": "1"}},
            sources=[],
        )
    )
    assert pj.templates["T"].fields["F"].value == "num"


def test_counter_table_must_be_known_source():
    with pytest.raises(PJValidationError, match="not in data_sources"):
        validate_pj(
            _pj(
                {"source": "constant", "value": "x"},
                {"emp": {"format": "1", "table": "Данные/gone.xlsx"}},
            )
        )


def test_source_needs_bound_counter():
    with pytest.raises(PJValidationError, match="no bound counter"):
        validate_pj(
            _pj(
                {"source": "constant", "value": "x"},
                {},
            )
        )


def test_default_template_must_exist():
    data = _pj({"source": "constant", "value": "x"}, {}, sources=[])
    data["default_template"] = "Чужой"
    with pytest.raises(PJValidationError, match="default_template"):
        validate_pj(data)


def test_default_template_defaults_to_first():
    pj = validate_pj(_pj({"source": "constant", "value": "x"}, {}, sources=[]))
    assert pj.default_template == "T"


def test_counter_pos_and_resume_defaults():
    from stanok.engine.schema import CounterDef

    cdef = CounterDef()
    assert cdef.pos == 0
    assert cdef.resume == 1
    assert CounterDef(table="Данные/d.xlsx", pos=3, resume=0).pos == 3


def test_counter_legacy_position_migrates():
    from stanok.engine.schema import CounterDef

    assert CounterDef(last=7, start_row=3, table="Данные/d.xlsx").pos == 3
    assert CounterDef(last=7, start_row=3).pos == 7
    assert CounterDef(last=7).pos == 7
    assert CounterDef(start_row=3).pos == 3
    assert CounterDef(pos=5, last=7, start_row=3).pos == 5


def test_counter_table_binding_validate():
    from stanok.engine.schema import CounterDef

    assert CounterDef(pos=0, table="Данные/d.xlsx").table == "Данные/d.xlsx"
    assert CounterDef().table is None
    with pytest.raises(Exception, match="относительным"):
        CounterDef(table="../evil.xlsx")


def test_project_folder_field():
    pj = validate_pj({
        "version": "0.0.0",
        "templates": {"T": {"file": "Шаблоны/t.docx", "fields": {}}},
        "data_sources": [],
        "counters": {},
        "filename_template": "p",
        "folder": "  ",
    })
    assert pj.folder is None
    pj2 = validate_pj({
        "version": "0.0.0",
        "templates": {"T": {"file": "Шаблоны/t.docx", "fields": {}}},
        "data_sources": [],
        "counters": {},
        "filename_template": "p",
        "folder": "relative/dir",
    })
    assert pj2.folder == "relative/dir"
