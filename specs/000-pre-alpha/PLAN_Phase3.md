# PLAN_Phase3 — Core Nested Generation Logic

**Parent:** PLAN.md Phase 3 | **Spec:** SPEC.md (Nested Employee/Project Generation)
**Scope:** `docxforge/generate.py` only. GUI (Phases 1/5) and tests (Phases 6/7) are NOT touched.
**Status:** In Progress | **Branch:** `feat/phase3-nested-core`

---

## Function contract (for Phases 2/4/5/6)

```python
def create_nested_employee_projects(
    project_path: str,
    template_name: str,
    folder_name_template: str,          # composite, e.g. "{{employee}}/{{project_name}}"
    max_projects: Optional[int] = None, # cap on TOTAL projects (only when > 0)
                                        # 4th positional: composite routing in
                                        # create_projects_from_template() passes it positionally
    employee_column: str = 'employee',
    project_column: str = 'project_name',
) -> Tuple[str, int, int]:              # (projects_dir, employee_count, project_count)
```

- Raises `GenerationError` (from `docxforge.generate`) with a clear message on all failures.
- Phase 2 routes composite templates here; Phase 5 passes the composite string through
  `folder_name_template`. Parts come from the Phase 2 helper `parse_composite_template()`
  (composite = `/` plus both `{{employee}}` and `{{project_name}}`): the employee part
  resolves the employee folder, the project part the project folder (via existing
  `_resolve_folder_name_template` + sanitizing). Non-composite → employee folder from
  the raw `employee` value, whole template used for the project folder (backward compatible).
- Phase 4 may take over config/file-op details; current implementation reuses the existing
  `_build_project_config()` + `_copy_template_files()` and copies `Данные/` fully via
  `shutil.copytree` (per SPEC.md). Folder names use codebase convention
  `Данные/`, `Шаблоны/`, `Результат/` (capitalized, as everywhere else in the project).
- `row_index` in settings.json = 0-based index of the row in the primary batch source.

## `docxforge_settings.json` format (per employee folder)

```json
{
  "employee": "Иванов Иван",
  "employee_folder": "Иванов_Иван",
  "created_at": "2025-09-12T14:30:00",
  "projects": [
    {"name": "Договор_001", "folder": "Договор_001",
     "template": "all_fields.docx", "row_index": 0,
     "created_at": "2025-09-12T14:30:00"}
  ]
}
```

`created_at` = `datetime.now().isoformat(timespec='seconds')`.

---

## Subtasks

### 3.1 Planning & contract
- [x] Write this `PLAN_Phase3.md` (checklist, criteria, settings.json format, edges, contract)
- [x] Commit + push: `docs: add PLAN_Phase3 breakdown`

### 3.2 Private helpers in `generate.py`
- [ ] `_sanitize_folder_name(name)` — replace `<>:"/\|?*` + control chars with `_`,
      strip trailing dots/spaces, truncate to 100 chars, `''` if nothing left
- [ ] `_unique_folder_name(base, used, parent_dir)` — append `_1`, `_2`… while the name
      is taken (in-run set or already on disk); registers the chosen name in `used`
- [ ] `_split_composite_template(template)` — split on first `/` → `(employee_part|None, project_part)`
- [ ] `_rollback_created(paths)` — `shutil.rmtree` in reverse order, `ignore_errors=True`
- [ ] Criteria: helpers pure/local, `logging` only, no `print()`, no new TODOs

### 3.3 Core `create_nested_employee_projects()`
- [ ] Load project / validate template + template file / require batch sources /
      primary SEQUENTIAL source (same patterns as `create_projects_from_template`)
- [ ] Read rows via `DataReader.read_all_batch_sources()`; empty → `GenerationError`
- [ ] Validate `employee`/`project_name` columns present → else `GenerationError` naming the column
- [ ] Attach original row indices, cap total rows when `max_projects > 0`, group by `employee`
      (first-seen order; blank value → `employee_N` fallback)
- [ ] Per employee: resolve + sanitize + dedupe folder, `makedirs`, track for rollback
- [ ] Per project: resolve + sanitize + dedupe folder inside employee dir; create
      `Данные/` (full `copytree` of source `Данные/`), `Шаблоны/` (copy template),
      `Результат/` (empty); config via `_build_project_config()` with all batch sources
      forced to CONSTANT; write `проект.docxforge`
- [ ] Write `docxforge_settings.json` per employee after its projects; return
      `(projects_dir, employee_count, project_count)`
- [ ] Criteria: smoke 2 employees × 2–3 projects passes; structure + settings.json match SPEC

### 3.4 Verification & merge
- [ ] `python -m pytest tests/ -q` → exit 0 after each sub-implementation
- [ ] Manual smoke via `python -c` in temp dir (2 employees × 2–3 projects)
- [ ] Commit + push per subitem (`feat: <что> [phase3]`)
- [ ] Final: `git pull origin main` → merge branch to `main` → push (no `--force`;
      on conflict keep both sides, never drop `parse_composite_template`/Phase 4 code)

---

## Edge cases

| Case | Handling |
|------|----------|
| Missing `employee` / `project_name` column | `GenerationError` naming the column + batch file |
| No batch sources / no SEQUENTIAL source / empty rows | `GenerationError` (same messages as flat mode) |
| Empty employee value | Fallback `employee_N` (N = 1-based employee counter) |
| Empty project folder name | Fallback `project_N` (N = 1-based counter within employee) |
| Duplicate employee folders | Suffix `_1`, `_2`… (also against pre-existing dirs on disk) |
| Duplicate project folders in one employee | Suffix `_1`, `_2`… |
| Filesystem-unsafe chars | Sanitized to `_` |
| Permission / OS error mid-run | Rollback all dirs created in this call, then `GenerationError` |
| `max_projects <= 0` / `None` | No cap (same semantics as flat `create_projects_from_template`) |
| Missing template file | `GenerationError` before creating anything |

## Acceptance criteria

1. `create_nested_employee_projects()` importable from `docxforge.generate`
2. Grouping by `employee` correct; employee folders + `docxforge_settings.json` per SPEC format
3. Project folders contain `Данные/` (full copy), `Шаблоны/` (template), `Результат/` (empty), `проект.docxforge` (TABLE→CONSTANT, COUNTER reset, batch→CONSTANT)
4. All edge cases above behave as specified
5. `pytest tests/ -q` green; smoke green; no files outside `generate.py` + `PLAN_Phase3.md` modified
