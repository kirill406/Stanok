# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for generate_documents: orchestration tables → resolve → render."""

import json
from pathlib import Path

import pytest
from docx import Document as DocxDocument
from openpyxl import Workbook

from stanok.engine.schema import ResolveError, StorageError, validate_pj
from stanok.services.generate import (
    GenerateCommand,
    TemplateError,
    _unique_path,
    generate_documents,
)
from stanok.services.storage import ProjectStore


def make_project(
    root: Path,
    *,
    headers=("ФИО", "Сумма"),
    rows=(("Иван", 100), ("Петр", 200)),
    mode="sequential",
    start_row=0,
    with_counter=True,
) -> Path:
    """Build minimal project folder: Данные/data.xlsx + Шаблоны/tpl.docx + legacy PJ."""
    data_dir = root / "Данные"
    tpl_dir = root / "Шаблоны"
    data_dir.mkdir(parents=True)
    tpl_dir.mkdir(parents=True)

    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    wb.save(data_dir / "data.xlsx")

    doc = DocxDocument()
    doc.add_paragraph("Договор {{ФИО}} на сумму {{Сумма}} №{{Номер}}")
    doc.save(tpl_dir / "tpl.docx")

    fields = {
        "ФИО": {"source": "table", "value": "ФИО"},
        "Сумма": {"source": "table", "value": "Сумма"},
    }
    if with_counter:
        fields["Номер"] = {"source": "counter", "value": "num"}
    else:  # pragma: no cover - template without counter
        doc2 = DocxDocument()
        doc2.add_paragraph("Договор {{ФИО}}")
        doc2.save(tpl_dir / "tpl.docx")
        del fields["Номер"]
    pj = {
        "version": "0.0.0",
        "templates": {"Договор": {"file": "Шаблоны/tpl.docx", "fields": fields}},
        "data_sources": [
            {"file": "Данные/data.xlsx", "mode": mode, "start_row": start_row}
        ],
        "counters": {"num": {"last": 0, "format": "plain"}} if with_counter else {},
        "filename_template": "Договор_{ФИО}_{i}.docx",
    }
    (root / "project.stanok").write_text(json.dumps(pj, ensure_ascii=False, indent=2))
    return root


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / ".stanok")


def _load_saved(store, folder_name):
    return validate_pj(
        json.loads((store.home_dir / f"{folder_name}.stanok").read_text())
    )


def test_full_sequential_run(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 2
    assert report.skipped == 0
    assert report.errors == []
    assert len(report.output_paths) == 2
    assert all(p.exists() for p in report.output_paths)
    saved = _load_saved(store, "proj")
    assert saved.counters["num"].last == 2
    assert saved.data_sources[0].start_row == 2


def test_resume_continues_from_saved_row(tmp_path, store):
    folder = make_project(tmp_path / "proj", start_row=1)
    report = generate_documents(
        GenerateCommand(project_ref=folder, resume=True), store=store
    )
    assert report.created == 1
    assert "Петр" in report.output_paths[0].name


def test_no_resume_starts_from_zero(tmp_path, store):
    folder = make_project(tmp_path / "proj", start_row=1)
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 2


def test_max_docs_truncates(tmp_path, store):
    folder = make_project(
        tmp_path / "proj", rows=(("А", 1), ("Б", 2), ("В", 3))
    )
    report = generate_documents(
        GenerateCommand(project_ref=folder, max_docs=2), store=store
    )
    assert report.created == 2
    saved = _load_saved(store, "proj")
    assert saved.counters["num"].last == 2
    assert saved.data_sources[0].start_row == 2


def test_max_docs_zero_generates_nothing(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    report = generate_documents(
        GenerateCommand(project_ref=folder, max_docs=0), store=store
    )
    assert report.created == 0
    assert report.output_paths == []
    assert not (folder / "Результат").exists()


def test_empty_source_returns_empty_report(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=())
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 0
    assert report.errors == []


def test_empty_rows_skipped(tmp_path, store):
    folder = make_project(
        tmp_path / "proj", rows=(("Иван", 100), (None, None), ("Петр", 200))
    )
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 2
    assert report.skipped == 1


def test_error_continues(monkeypatch, tmp_path, store):
    folder = make_project(tmp_path / "proj")
    import stanok.services.generate as gen

    real_render = gen.render
    calls = {"n": 0}

    def flaky(fj, template_path):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real_render(fj, template_path)

    monkeypatch.setattr(gen, "render", flaky)
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 1
    assert len(report.errors) == 1
    assert report.errors[0][0] == 1
    assert "boom" in report.errors[0][1]


def test_missing_template_file(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    (folder / "Шаблоны" / "tpl.docx").unlink()
    with pytest.raises(TemplateError, match="template file not found"):
        generate_documents(GenerateCommand(project_ref=folder), store=store)


def test_missing_project(store, tmp_path):
    with pytest.raises(StorageError):
        generate_documents(
            GenerateCommand(project_ref="nope"), store=store
        )


def test_unknown_template_name(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    with pytest.raises(TemplateError, match="template not found"):
        generate_documents(
            GenerateCommand(project_ref=folder, template="Чужой"), store=store
        )


def test_unique_names_on_collision(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=(("Иван", 100),))
    out = folder / "Результат"
    out.mkdir()
    (out / "Договор_Иван_1.docx").write_bytes(b"old")
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 1
    assert report.output_paths[0].name == "Договор_Иван_1 (1).docx"
    assert (out / "Договор_Иван_1.docx").read_bytes() == b"old"


def test_constant_mode(tmp_path, store):
    folder = make_project(
        tmp_path / "proj",
        rows=(("Иван", 100), ("Петр", 200), ("Сидор", 300)),
        mode="constant",
    )
    report = generate_documents(
        GenerateCommand(project_ref=folder, max_docs=2), store=store
    )
    assert report.created == 2
    saved = _load_saved(store, "proj")
    assert saved.data_sources[0].start_row == 1


def test_config_name_ref_via_recent(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=(("Иван", 100),))
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 1
    store.add_recent(str(folder), "proj")
    report2 = generate_documents(GenerateCommand(project_ref="proj"), store=store)
    assert report2.created == 1


def test_config_name_without_folder_fails(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=(("Иван", 100),))
    generate_documents(GenerateCommand(project_ref=folder), store=store)
    with pytest.raises(TemplateError, match="project folder not found"):
        generate_documents(GenerateCommand(project_ref="proj"), store=store)


def test_unique_path_helper(tmp_path):
    base = tmp_path / "a.docx"
    assert _unique_path(base) == base
    base.write_bytes(b"x")
    assert _unique_path(base) == tmp_path / "a (1).docx"
    (tmp_path / "a (1).docx").write_bytes(b"x")
    assert _unique_path(base) == tmp_path / "a (2).docx"


def _rewrite_pj(folder: Path, **overrides):
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data.update(overrides)
    pj_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def test_no_templates_fails(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _rewrite_pj(folder, templates={})
    with pytest.raises(TemplateError, match="no templates"):
        generate_documents(GenerateCommand(project_ref=folder), store=store)


def test_named_template_pick(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    data = json.loads((folder / "project.stanok").read_text())
    data["templates"]["Второй"] = data["templates"]["Договор"]
    (folder / "project.stanok").write_text(json.dumps(data, ensure_ascii=False))
    report = generate_documents(
        GenerateCommand(project_ref=folder, template="Второй"), store=store
    )
    assert report.created == 2


def test_multiple_templates_warn_first(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    data = json.loads((folder / "project.stanok").read_text())
    data["templates"]["Второй"] = data["templates"]["Договор"]
    (folder / "project.stanok").write_text(json.dumps(data, ensure_ascii=False))
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 2


def test_no_data_sources_fails(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _rewrite_pj(folder, data_sources=[])
    with pytest.raises(TemplateError, match="no data sources"):
        generate_documents(GenerateCommand(project_ref=folder), store=store)


def test_named_data_source_pick(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    data = json.loads((folder / "project.stanok").read_text())
    data["data_sources"].append(data["data_sources"][0])
    (folder / "project.stanok").write_text(json.dumps(data, ensure_ascii=False))
    report = generate_documents(
        GenerateCommand(project_ref=folder, data_source="Данные/data.xlsx"),
        store=store,
    )
    assert report.created == 2
    with pytest.raises(TemplateError, match="data source not found"):
        generate_documents(
            GenerateCommand(project_ref=folder, data_source="nope.xlsx"), store=store
        )


def _add_source(folder, name="data2.xlsx", rows=(("Зоя", 300),), mode="sequential",
               start_row=0):
    """Append second xlsx + data_sources entry to a make_project folder."""
    wb = Workbook()
    ws = wb.active
    ws.append(["ФИО", "Сумма"])
    for r in rows:
        ws.append(list(r))
    wb.save(folder / "Данные" / name)
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["data_sources"].append(
        {"file": f"Данные/{name}", "mode": mode, "start_row": start_row}
    )
    pj_path.write_text(json.dumps(data, ensure_ascii=False))
    return f"Данные/{name}"


def test_multiple_sources_run_all(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    data = json.loads((folder / "project.stanok").read_text())
    data["data_sources"].append(data["data_sources"][0])
    (folder / "project.stanok").write_text(json.dumps(data, ensure_ascii=False))
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 4
    saved = _load_saved(store, "proj")
    assert saved.counters["num"].last == 4
    assert [ds.start_row for ds in saved.data_sources] == [2, 2]


def test_two_sources_shared_counters(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_source(folder)
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 3
    assert report.resumed_from is None
    saved = _load_saved(store, "proj")
    assert saved.counters["num"].last == 3
    assert [ds.start_row for ds in saved.data_sources] == [2, 1]


def test_named_second_source_uses_own_mode(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    second = _add_source(folder, rows=(("А", 1), ("Б", 2)), mode="circular")
    report = generate_documents(
        GenerateCommand(project_ref=folder, data_source=second, max_docs=5),
        store=store,
    )
    assert report.created == 5
    saved = _load_saved(store, "proj")
    assert saved.counters["num"].last == 5
    assert [ds.start_row for ds in saved.data_sources] == [0, 2]


def test_broken_second_source_continues(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["data_sources"].append(
        {"file": "Данные/none.xlsx", "mode": "sequential", "start_row": 0}
    )
    pj_path.write_text(json.dumps(data, ensure_ascii=False))
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 2
    assert len(report.errors) == 1
    idx, msg = report.errors[0]
    assert idx == -1
    assert msg.startswith("Данные/none.xlsx: ")


def test_resumed_from_first_source(tmp_path, store):
    folder = make_project(tmp_path / "proj", start_row=1)
    _add_source(folder)
    report = generate_documents(
        GenerateCommand(project_ref=folder, resume=True), store=store
    )
    assert report.created == 2
    assert report.resumed_from == 1


def test_single_broken_source_raises(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["data_sources"] = [
        {"file": "Данные/none.xlsx", "mode": "sequential", "start_row": 0}
    ]
    pj_path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(Exception, match="none.xlsx"):
        generate_documents(GenerateCommand(project_ref=folder), store=store)


def test_cancel_stops_before_second_source(tmp_path, store):
    folder = make_project(tmp_path / "proj")
    _add_source(folder)

    def stop_after_first(created, total):
        return True

    report = generate_documents(
        GenerateCommand(project_ref=folder), store=store,
        progress=stop_after_first,
    )
    assert report.created == 1
    saved = _load_saved(store, "proj")
    assert [ds.start_row for ds in saved.data_sources] == [2, 0]


def test_save_document_escape_rejected(tmp_path):
    from docx import Document as DocxDocument

    from stanok.services.generate import _save_document

    with pytest.raises(TemplateError, match="escapes"):
        _save_document(DocxDocument(), tmp_path, "../evil.docx", 0)


def test_progress_callback_error_ignored(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=(("А", 1),))

    def bad_progress(created, total):
        raise RuntimeError("callback boom")

    report = generate_documents(
        GenerateCommand(project_ref=folder), store=store, progress=bad_progress
    )
    assert report.created == 1


def test_dist_escape_fails_fast(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=(("Иван", 100),))
    _rewrite_pj(folder, filename_template="../evil_{i}.docx")
    with pytest.raises(ResolveError, match="dist"):
        generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert not (folder.parent / "evil_1.docx").exists()


def test_only_empty_rows(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=((None, None), (None, None)))
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 0
    assert report.skipped == 2


def test_circular_cycles_to_max_docs(tmp_path, store):
    folder = make_project(
        tmp_path / "proj", rows=(("А", 1), ("Б", 2)), mode="circular"
    )
    report = generate_documents(
        GenerateCommand(project_ref=folder, max_docs=5), store=store
    )
    assert report.created == 5
    assert report.resumed_from is None
    saved = _load_saved(store, "proj")
    assert saved.counters["num"].last == 5
    assert saved.data_sources[0].start_row == 2


def test_resumed_from_reported(tmp_path, store):
    folder = make_project(tmp_path / "proj", start_row=1)
    fresh = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert fresh.resumed_from is None
    resumed = generate_documents(
        GenerateCommand(project_ref=folder, resume=True), store=store
    )
    assert resumed.created == 0
    assert resumed.resumed_from == 2


def test_dist_from_counter_and_today(tmp_path, store):
    import re

    folder = make_project(tmp_path / "proj", rows=(("Иван", 100),))
    pj_path = folder / "project.stanok"
    data = json.loads(pj_path.read_text())
    data["templates"]["Договор"]["fields"]["Дата"] = {"source": "today"}
    data["filename_template"] = "Д_{Номер}_{Дата}.docx"
    pj_path.write_text(json.dumps(data, ensure_ascii=False))
    report = generate_documents(GenerateCommand(project_ref=folder), store=store)
    assert report.created == 1
    name = report.output_paths[0].name
    assert re.fullmatch(r"Д_1_\d{4}-\d{2}-\d{2}\.docx", name), name


def test_progress_callback_cancel(tmp_path, store):
    folder = make_project(
        tmp_path / "proj", rows=(("А", 1), ("Б", 2), ("В", 3))
    )
    seen = []

    def progress(created, total):
        seen.append((created, total))
        return created >= 1

    report = generate_documents(
        GenerateCommand(project_ref=folder), store=store, progress=progress
    )
    assert report.created == 1
    assert seen[0] == (1, 3)
    saved = _load_saved(store, "proj")
    assert saved.data_sources[0].start_row == 3


def test_progress_callback_no_cancel(tmp_path, store):
    folder = make_project(tmp_path / "proj", rows=(("А", 1), ("Б", 2)))
    calls = []
    report = generate_documents(
        GenerateCommand(project_ref=folder),
        store=store,
        progress=lambda c, t: calls.append((c, t)) or False,
    )
    assert report.created == 2
    assert calls == [(1, 2), (2, 2)]
