# PLAN_Phase4 — Project Config & File Operations (nested mode)

**Parent:** PLAN.md Phase 4 | **SPEC:** SPEC.md | **Scope:** `docxforge/generate.py` only (no GUI, no tests).
**Branch:** `feat/phase4-config-fileops`
**Rule:** grouping core (`parse_composite`, `create_nested_employee_projects`) belongs to Phases 2–3 — do NOT duplicate/break it. Flat `create_projects_from_template()` stays backward compatible.

> **Folder-case decision:** SPEC defines nested layout lowercase (`данные/`, `шаблоны/`, `результат/`).
> Source lookup accepts both `Данные/` and `данные/` (existing projects use capital).
> Destinations use SPEC lowercase. Platform is Windows (case-insensitive), so the engine
> (which reads `Данные`/`Шаблоны`) resolves both spellings.

---

## Subtasks

### 4.1 Fix `_build_project_config` — TABLE→CONSTANT, COUNTER reset, batch→CONSTANT
- [x] TABLE field with `column` present in `row_data` → `FieldType.CONSTANT` with row value
  (fix: old check `fm.file in row_data` never matched — `row_data` keys are columns, not file names)
- [x] COUNTER fields: keep `start`/`step`/`format` (fresh counter, resume cleared)
- [x] CONSTANT/TODAY/IMAGE/other: copied unchanged with all attrs
- [x] ALL `batch_sources` → `RowIterationMode.CONSTANT`, `continue_from_last=False`,
  `counter_current_row=1`, lookup cleared (was: only primary source converted)
- [x] Preserve `cycles`, `aggregations`, `filename_template`, `directory_template`
- [x] Fresh `ResumeState(continue_from_last=False)`
- [x] Signature `(template_config, row_data, primary_source_file)` unchanged (Phase 3 + flat path compatible)

### 4.2 `copy_data_folder` — full copy of `Данные/` (no slicing)
- [x] `shutil.copytree(src, dst, dirs_exist_ok=True)` — entire folder, all files unchanged
- [x] Source resolved as `Данные/` → fallback `данные/`; missing source → `GenerationError`
- [x] Destination: `<project>/данные/`

### 4.3 Template copy to `шаблоны/` + empty `результат/`
- [x] `copy_template_file(src_template_path, dst_project_dir)` → `<project>/шаблоны/<name>.docx`
  via `shutil.copy2`; missing source → `GenerationError`
- [x] `create_result_folder(dst_project_dir)` → empty `<project>/результат/`
- [x] `setup_nested_project_files(...)` — composed per-project op for the Phase 3 loop:
  makedirs + data copy + template copy + result dir + `проект.docxforge` write,
  with rollback (`shutil.rmtree`) on failure

### 4.4 Writers — `проект.docxforge` + `docxforge_settings.json`
- [x] `write_nested_project_config(dst_project_dir, template_name, new_config, version)`
  → `Project(version).to_file(<project>/проект.docxforge)`
- [x] `write_employee_settings(employee_dir, employee, employee_folder, projects)`
  → `docxforge_settings.json` per SPEC schema:
  `{employee, employee_folder, created_at (ISO), projects: [{name, folder, template, row_index, created_at}]}`

### 4.5 Verification
- [x] `python -m pytest tests/ -q` green after every subtask
- [x] Smoke test in tmp: config transform + full file-ops chain (copytree, .docx copy,
  empty result, both JSON files) verified on real FS
- [x] Flat `create_projects_from_template()` untouched in behavior (only benefits from 4.1 fix)

---

## Acceptance criteria → SPEC mapping

| Criterion | Check |
|-----------|-------|
| TABLE→CONSTANT со значениями строки | 4.1: `new_config.fields[x].type == CONSTANT`, value == row value |
| COUNTER reset | 4.1: `start/step/format` kept, resume fresh |
| batch→CONSTANT | 4.1: every source `mode == CONSTANT`, `continue_from_last=False` |
| `Данные/` — полная копия copytree без слайсинга | 4.2: `filecmp`-equal trees, no row filtering |
| `шаблоны/` — копия .docx | 4.3: identical bytes |
| `результат/` — пустая | 4.3: exists, empty |
| `проект.docxforge` + `settings.json` | 4.4: valid JSON, loadable via `Project.from_file`, settings match SPEC schema |

## Files
- Modified: `docxforge/generate.py` (helpers only), `PLAN_Phase4.md` (this file)
- NOT touched: `docxforge/gui/`, `tests/`, `docxforge/engine/`, `.env`
