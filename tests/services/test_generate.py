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
