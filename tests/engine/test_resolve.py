# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for resolve: rows + PJ → FillingJSON (021 composition model)."""

from datetime import date

import pytest

from stanok.engine.resolve import (
    participating_sources,
    resolve_rows,
    used_counters,
)
from stanok.engine.schema import ResolveError, validate_pj

TODAY = date(2026, 10, 5)
SRC = "Данные/X.xlsx"


def _pj(**overrides) -> dict:
    base = {
        "version": "0.0.0",
        "templates": {
            "Д": {
                "file": "Шаблоны/Д.docx",
                "fields": {
                    "ФИО": {"source": "table", "value": "fio", "counter_name": "emp"},
                    "Номер": {"source": "counter", "value": "n"},
                    "Дата": {"source": "today"},
                    "Город": {"source": "constant", "value": "Москва"},
                },
            }
        },
        "default_template": "Д",
        "data_sources": [{"file": SRC, "mode": "sequential"}],
        "counters": {
            "emp": {"format": "1", "table": SRC, "pos": 1},
            "n": {"pos": 42, "format": "plain"},
        },
        "filename_template": "{template} №{Номер}",
    }
    base.update(overrides)
    return validate_pj(base)


# Counter pos is a row index, so row 0 is the one a counter at pos 0 would read.
# The emp counter starts at pos 1, so tests pass rows with row 0 as a placeholder.
ROWS = [{"fio": "Пропуск"}, {"fio": "Иванов"}, {"fio": "Петров"}, {"fio": None}]
# Circular counter at pos 2 wraps to row 0 of a two-row circle.
CYCLE = [{"fio": "Иванов"}, {"fio": "Петров"}]


def test_basic_composition():
    fjs, names = resolve_rows({SRC: ROWS[:3]}, _pj(), "Д", today=TODAY)
    assert len(fjs) == 2
    assert fjs[0].fields == {
        "ФИО": "Иванов",
        "Номер": "42",
        "Дата": TODAY,
        "Город": "Москва",
    }
    assert fjs[0].dist == "Д №42"
    assert names == ["emp", "n"]


def test_counters_advance_across_docs():
    fjs, _ = resolve_rows({SRC: ROWS[:3]}, _pj(), "Д", today=TODAY)
    assert [f.fields["Номер"] for f in fjs] == ["42", "43"]


def test_pj_not_mutated():
    pj = _pj()
    resolve_rows({SRC: ROWS[:3]}, pj, "Д", today=TODAY)
    assert pj.counters["n"].pos == 42
    assert pj.counters["emp"].pos == 1


def test_used_counters_and_sources():
    pj = _pj()
    assert used_counters(pj, "Д") == ["emp", "n"]
    assert participating_sources(pj, "Д") == [SRC]


def test_resolve_counter_at_zero_starts_at_first_row():
    pj = _pj()
    pj.counters["emp"].pos = 0
    fjs, _ = resolve_rows({SRC: ROWS[1:3]}, pj, "Д", today=TODAY)
    assert [f.fields["ФИО"] for f in fjs] == ["Иванов", "Петров"]


def test_resolve_circular_counter_at_zero_starts_at_first_row():
    pj = _pj()
    pj.data_sources[0].mode = "circular"
    pj.counters["emp"].pos = 0
    fjs, _ = resolve_rows({SRC: CYCLE}, pj, "Д", today=TODAY)
    assert [f.fields["ФИО"] for f in fjs] == ["Иванов", "Петров"]


def test_mode_constant_repeats_counter_row_and_number():
    pj = _pj()
    pj.data_sources[0].mode = "constant"
    pj.templates["Д"].limit = 3
    pj.templates["Д"].fields["Номер"].value = "emp"
    fjs, _ = resolve_rows({SRC: ROWS}, pj, "Д", today=TODAY)
    assert [f.fields["ФИО"] for f in fjs] == ["Иванов"] * 3
    assert [f.fields["Номер"] for f in fjs] == ["1"] * 3


def test_mode_circular_single_lap():
    pj = _pj()
    pj.data_sources[0].mode = "circular"
    pj.counters["emp"].pos = 2
    fjs, _ = resolve_rows({SRC: CYCLE}, pj, "Д", today=TODAY)
    assert len(fjs) == 2


def test_circular_cycles_to_limit():
    pj = _pj()
    pj.data_sources[0].mode = "circular"
    pj.counters["emp"].pos = 2
    pj.templates["Д"].limit = 5
    fjs, _ = resolve_rows({SRC: CYCLE}, pj, "Д", today=TODAY)
    assert [f.fields["ФИО"] for f in fjs] == ["Иванов", "Петров"] * 2 + ["Иванов"]
    assert [f.fields["Номер"] for f in fjs] == ["42", "43", "44", "45", "46"]


def test_constant_with_limit():
    pj = _pj()
    pj.data_sources[0].mode = "constant"
    pj.templates["Д"].limit = 3
    fjs, _ = resolve_rows({SRC: ROWS[:3]}, pj, "Д", today=TODAY)
    assert [f.fields["ФИО"] for f in fjs] == ["Иванов"] * 3


def test_pos_limits_sequential():
    pj = _pj()
    pj.counters["emp"].pos = 2
    fjs, _ = resolve_rows({SRC: ROWS}, pj, "Д", today=TODAY)
    assert len(fjs) == 2
    assert fjs[0].fields["ФИО"] == "Петров"


def test_limit_truncates_sequential():
    pj = _pj()
    pj.templates["Д"].limit = 1
    fjs, _ = resolve_rows({SRC: ROWS[:3]}, pj, "Д", today=TODAY)
    assert len(fjs) == 1


def test_multi_source_composition():
    pj = validate_pj(
        {
            "version": "0.0.0",
            "templates": {
                "Д": {
                    "file": "Шаблоны/Д.docx",
                    "fields": {
                        "ФИО": {"source": "table", "value": "fio", "counter_name": "ea"},
                        "Город": {"source": "table", "value": "city", "counter_name": "eb"},
                    },
                }
            },
            "default_template": "Д",
            "data_sources": [
                {"file": "Данные/A.xlsx", "mode": "sequential"},
                {"file": "Данные/B.xlsx", "mode": "sequential"},
            ],
            "counters": {
                "ea": {"format": "1", "table": "Данные/A.xlsx", "pos": 1},
                "eb": {"format": "1", "table": "Данные/B.xlsx", "pos": 1},
            },
            "filename_template": "{i}",
        }
    )
    rows = {
        "Данные/A.xlsx": [{"fio": "Пропуск"}, {"fio": "Иванов"}, {"fio": "Петров"}],
        "Данные/B.xlsx": [
            {"city": "Пропуск"},
            {"city": "Москва"},
            {"city": "Тверь"},
            {"city": "Казань"},
        ],
    }
    fjs, _ = resolve_rows(rows, pj, "Д", today=TODAY)
    assert len(fjs) == 2  # min(2, 3)
    assert fjs[0].fields == {"ФИО": "Иванов", "Город": "Москва"}
    assert fjs[1].fields == {"ФИО": "Петров", "Город": "Тверь"}
    assert participating_sources(pj, "Д") == ["Данные/A.xlsx", "Данные/B.xlsx"]


def test_counter_month_format():
    pj = _pj()
    pj.counters["n"].format = "month"
    pj.counters["n"].pos = 7
    fjs, _ = resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)
    assert fjs[0].fields["Номер"] == "2026-10-007"


def test_counter_month_overflow():
    pj = _pj()
    pj.counters["n"].format = "month"
    pj.counters["n"].pos = 1000
    with pytest.raises(ResolveError, match="overflow"):
        resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)


def test_counter_width_padding():
    pj = _pj()
    pj.counters["n"].format = "001"
    fjs, _ = resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)
    assert fjs[0].fields["Номер"] == "042"


def test_missing_column_raises():
    pj = _pj()
    with pytest.raises(ResolveError, match="not found"):
        resolve_rows({SRC: [{"fio": "Пропуск"}, {"oops": 1}]}, pj, "Д", today=TODAY)


def test_unknown_dist_placeholder():
    pj = _pj(filename_template="{Нетакого}")
    with pytest.raises(ResolveError, match="unknown placeholder"):
        resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)


def test_dist_traversal_wrapped_in_resolve_error():
    pj = _pj(filename_template="../evil_{i}.docx")
    with pytest.raises(ResolveError, match="dist"):
        resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)


def test_unknown_template_raises():
    with pytest.raises(ResolveError, match="template not found"):
        resolve_rows({SRC: ROWS[:2]}, _pj(), "Чужой", today=TODAY)


def test_unknown_mode_raises():
    pj = _pj()
    pj.data_sources[0].mode = "telepathy"
    with pytest.raises(ResolveError, match="unknown mode"):
        resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)


def test_empty_row_gives_none_fields():
    fjs, _ = resolve_rows(
        {SRC: [{"fio": "Пропуск"}, {"fio": None}]}, _pj(), "Д", today=TODAY
    )
    assert fjs[0].fields["ФИО"] is None


def test_undefined_counter_raises():
    pj = _pj()
    pj.templates["Д"].fields["Номер"].value = "ghost"
    with pytest.raises(ResolveError, match="counter not defined"):
        resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)


def test_unknown_source_raises():
    from stanok.engine.schema import FieldDef

    pj = _pj()
    broken = FieldDef.model_construct(source="telepathy", value=None)
    pj.templates["Д"].fields["X"] = broken
    with pytest.raises(ResolveError, match="unknown field source"):
        resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)


def test_unexpected_error_wrapped_and_logged(monkeypatch, caplog):
    import stanok.engine.resolve as resolve_mod

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(resolve_mod, "_format_counter", boom)
    with caplog.at_level("ERROR", logger="stanok.engine.resolve"):
        with pytest.raises(ResolveError, match=r"fields\.Номер"):
            resolve_rows({SRC: ROWS[:2]}, _pj(), "Д", today=TODAY)
    assert any("boom" in r.message for r in caplog.records)


def test_no_rows_returns_empty():
    fjs, names = resolve_rows({SRC: []}, _pj(), "Д", today=TODAY)
    assert fjs == []
    assert names == ["emp", "n"]


def test_today_presets():
    pj = _pj()
    presets = {
        "dmy": "05.10.2026",
        "day": "5",
        "month_ru": "октября",
        "month_num": "10",
        "year": "2026",
        "ru_long": "5 октября 2026",
    }
    for preset, expected in presets.items():
        pj.templates["Д"].fields["Дата"].value = preset
        fjs, _ = resolve_rows({SRC: ROWS[:2]}, pj, "Д", today=TODAY)
        assert fjs[0].fields["Дата"] == expected


def test_today_legacy_none_is_date():
    fjs, _ = resolve_rows({SRC: ROWS[:2]}, _pj(), "Д", today=TODAY)
    assert fjs[0].fields["Дата"] == TODAY
