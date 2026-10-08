# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for resolve: rows + PJ → FillingJSON."""

from datetime import date

import pytest

from stanok.engine.resolve import resolve_rows
from stanok.engine.schema import ResolveError, validate_pj

TODAY = date(2026, 10, 5)


def _pj(**overrides) -> dict:
    base = {
        "version": "0.0.0",
        "templates": {
            "Д": {
                "file": "Шаблоны/Д.docx",
                "fields": {
                    "ФИО": {"source": "table", "value": "fio"},
                    "Номер": {"source": "counter", "value": "n"},
                    "Дата": {"source": "today"},
                    "Город": {"source": "constant", "value": "Москва"},
                },
            }
        },
        "data_sources": [{"file": "Данные/X.xlsx", "mode": "sequential", "start_row": 0}],
        "counters": {"n": {"last": 42, "format": "plain"}},
        "filename_template": "{template} №{Номер}",
    }
    base.update(overrides)
    return validate_pj(base)


ROWS = [{"fio": "Иванов"}, {"fio": "Петров"}, {"fio": None}]


def test_all_sources_resolved():
    fjs, counters = resolve_rows(ROWS[:2], _pj(), today=TODAY)
    assert len(fjs) == 2
    assert fjs[0].fields == {
        "ФИО": "Иванов",
        "Номер": "43",
        "Дата": TODAY,
        "Город": "Москва",
    }
    assert fjs[0].dist == "Д №43"
    assert counters == {"n": 44}


def test_counters_advance_across_docs():
    fjs, _ = resolve_rows(ROWS[:2], _pj(), today=TODAY)
    assert [f.fields["Номер"] for f in fjs] == ["43", "44"]


def test_pj_not_mutated():
    pj = _pj()
    resolve_rows(ROWS[:2], pj, today=TODAY)
    assert pj.counters["n"].last == 42


def test_mode_constant_repeats_first_row():
    pj = _pj()
    pj.data_sources[0].mode = "constant"
    fjs, _ = resolve_rows(ROWS[:2], pj, today=TODAY)
    assert [f.fields["ФИО"] for f in fjs] == ["Иванов", "Иванов"]


def test_mode_circular_single_lap():
    pj = _pj()
    pj.data_sources[0].mode = "circular"
    fjs, _ = resolve_rows(ROWS[:2], pj, today=TODAY)
    assert len(fjs) == 2  # один круг до FR-18


def test_start_row_resume():
    pj = _pj()
    pj.data_sources[0].start_row = 1
    fjs, _ = resolve_rows(ROWS[:2], pj, today=TODAY)
    assert len(fjs) == 1
    assert fjs[0].fields["ФИО"] == "Петров"


def test_counter_month_format():
    pj = _pj()
    pj.counters["n"].format = "month"
    pj.counters["n"].last = 7
    fjs, _ = resolve_rows(ROWS[:1], pj, today=TODAY)
    assert fjs[0].fields["Номер"] == "2026-10-008"


def test_counter_month_overflow():
    pj = _pj()
    pj.counters["n"].format = "month"
    pj.counters["n"].last = 999
    with pytest.raises(ResolveError, match="overflow"):
        resolve_rows(ROWS[:1], pj, today=TODAY)


def test_missing_column():
    pj = _pj()
    with pytest.raises(ResolveError, match="not found in data source"):
        resolve_rows([{"oops": 1}], pj, today=TODAY)


def test_unknown_dist_placeholder():
    pj = _pj(filename_template="{Нетакого}")
    with pytest.raises(ResolveError, match="unknown placeholder"):
        resolve_rows(ROWS[:1], pj, today=TODAY)


def test_no_templates_raises():
    pj = _pj(templates={})
    with pytest.raises(ResolveError, match="no templates"):
        resolve_rows(ROWS[:1], pj, today=TODAY)


def test_no_data_sources_raises():
    pj = _pj(data_sources=[])
    with pytest.raises(ResolveError, match="no data sources"):
        resolve_rows(ROWS[:1], pj, today=TODAY)


def test_unknown_mode_raises():
    pj = _pj()
    pj.data_sources[0].mode = "telepathy"
    with pytest.raises(ResolveError, match="unknown mode"):
        resolve_rows(ROWS[:1], pj, today=TODAY)


def test_multi_template_first_plus_warn(caplog):
    pj = _pj(
        templates={
            "A": {"file": "Шаблоны/A.docx", "fields": {}},
            "B": {"file": "Шаблоны/B.docx", "fields": {}},
        },
        filename_template="{template}",
    )
    with caplog.at_level("WARNING", logger="stanok.engine.resolve"):
        fjs, _ = resolve_rows(ROWS[:1], pj, today=TODAY)
    assert fjs[0].template == "A"
    assert any("multiple templates" in r.message for r in caplog.records)


def test_empty_row_gives_none_fields():
    fjs, _ = resolve_rows([{"fio": None}], _pj(), today=TODAY)
    assert fjs[0].fields["ФИО"] is None


def test_undefined_counter_raises():
    pj = _pj()
    pj.templates["Д"].fields["Номер"].value = "ghost"
    with pytest.raises(ResolveError, match="not defined in project"):
        resolve_rows(ROWS[:1], pj, today=TODAY)


def test_unknown_source_raises():
    from stanok.engine.schema import FieldDef

    pj = _pj()
    broken = FieldDef.model_construct(source="telepathy", value=None)
    pj.templates["Д"].fields["X"] = broken
    with pytest.raises(ResolveError, match="unknown field source"):
        resolve_rows(ROWS[:1], pj, today=TODAY)


def test_unexpected_error_wrapped_and_logged(monkeypatch, caplog):
    import stanok.engine.resolve as resolve_mod

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(resolve_mod, "_format_counter", boom)
    with caplog.at_level("ERROR", logger="stanok.engine.resolve"):
        with pytest.raises(ResolveError, match=r"fields\.Номер"):
            resolve_rows(ROWS[:1], _pj(), today=TODAY)
    assert any("boom" in r.message for r in caplog.records)


def test_multi_source_first_plus_warn(caplog):
    pj = _pj()
    pj.data_sources.append(pj.data_sources[0].model_copy())
    with caplog.at_level("WARNING", logger="stanok.engine.resolve"):
        fjs, _ = resolve_rows(ROWS[:1], pj, today=TODAY)
    assert len(fjs) == 1
    assert any("multiple data sources" in r.message for r in caplog.records)


def test_no_rows_returns_empty_counters():
    pj = _pj()
    fjs, counters = resolve_rows([], pj, today=TODAY)
    assert fjs == []
    assert counters == {"n": 42}
