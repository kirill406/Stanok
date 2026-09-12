# PLAN_Phase2 — Template Parsing & Detection

**Parent:** PLAN.md Phase 2 | **Spec:** SPEC.md (Nested Employee/Project Generation) | **Status:** In Progress
**Scope:** ONLY `docxforge/generate.py` (helper + detection + routing). No GUI, no tests.

---

## Goal

Add composite-template parsing and flat/composite mode detection in `create_projects_from_template()`,
routing composite templates to `create_nested_employee_projects()` (stub in this phase, full impl = Phase 3).
Flat path must remain byte-for-byte behavior-compatible.

---

## Subtasks

### 2.1 `parse_composite_template()` helper in `docxforge/generate.py`
- [ ] Add `parse_composite_template(template: str) -> Dict[str, Any]` returning:
  - `is_composite: bool`
  - `employee_part: str` (segment before first `/`)
  - `project_part: str` (remainder after first `/`)
- [ ] Composite criteria (ALL must hold, else flat):
  - template is non-empty string AND
  - contains `/` AND
  - contains `{{employee}}` placeholder (whitespace-tolerant: `{{ employee }}`) AND
  - contains `{{project_name}}` placeholder (whitespace-tolerant)
- [ ] Edge cases → flat (`is_composite=False`):
  - empty / `None` / whitespace-only template
  - no `/`
  - only one of the two placeholders
- [ ] Use `logging`, no `print()`; pure Python, no Qt deps.

### 2.2 Detection + routing in `create_projects_from_template()`
- [ ] At the top of `create_projects_from_template()`, call `parse_composite_template(folder_name_template)`.
- [ ] If `is_composite` → delegate immediately to `create_nested_employee_projects(project_path, template_name, folder_name_template, max_projects)` and return its result.
- [ ] Else → existing flat path unchanged (backward compat, no behavior change).

### 2.3 Stub `create_nested_employee_projects()` (Phase 3 contract)
- [ ] Add signature: `create_nested_employee_projects(project_path: str, template_name: str, folder_name_template: str, max_projects: Optional[int] = None) -> Tuple[str, int]`.
- [ ] Body: log + `raise NotImplementedError(...)` (full implementation is Phase 3).
- [ ] Documented contract for Phases 3–4 (return `(projects_dir, count)`; raises `GenerationError` on bad columns/data).

### 2.4 Verification
- [ ] `python -m pytest tests/ -q` → all pass (no regressions; flat path untouched).
- [ ] Manual sanity: flat template (`Project_{{client}}`) → flat; composite (`{{employee}}/{{project_name}}`) → routes to stub (`NotImplementedError`); empty/single-placeholder → flat.

---

## API Contract (for Phases 3–4)

```python
from docxforge.generate import parse_composite_template, create_nested_employee_projects

parsed = parse_composite_template("{{employee}}/{{project_name}}")
# {"is_composite": True, "employee_part": "{{employee}}", "project_part": "{{project_name}}"}

parsed = parse_composite_template("Project_{{client}}")
# {"is_composite": False, "employee_part": "", "project_part": "Project_{{client}}"}

# Routing inside create_projects_from_template():
#   parsed = parse_composite_template(folder_name_template)
#   if parsed["is_composite"]:
#       return create_nested_employee_projects(project_path, template_name, folder_name_template, max_projects)
#   ... flat path ...

def create_nested_employee_projects(project_path, template_name, folder_name_template, max_projects=None):
    # Phase 3: group rows by `employee`, resolve folders, copy Данные/, write проект.docxforge + docxforge_settings.json
    # Returns: Tuple[str, int] = (projects_dir, total_projects_created)
    raise NotImplementedError(...)
```

- Split rule: split on FIRST `/` (`template.split("/", 1)`); extra `/` stay in `project_part`.
- Placeholder match: regex `\{\{\s*employee\s*\}\}` and `\{\{\s*project_name\s*\}\}`, case-sensitive.
- Flat fallback returns `employee_part=""`, `project_part=<original template or "">`.

---

## Acceptance Criteria

| AC | Description |
|----|-------------|
| AC-1 | `parse_composite_template("{{employee}}/{{project_name}}")` → `is_composite=True` with correct parts |
| AC-2 | Empty template / no `/` / single placeholder → `is_composite=False` (flat) |
| AC-3 | `create_projects_from_template()` with composite template calls `create_nested_employee_projects()` |
| AC-4 | Flat templates follow the old code path unchanged (existing tests pass) |
| AC-5 | Only `docxforge/generate.py` (+ this doc) modified |

---

## Files

1. `docxforge/generate.py` — helper + detection + routing + stub
2. `PLAN_Phase2.md` — this file (planning doc, committed separately)
