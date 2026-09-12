# PLAN_Phase1 — Strings & Composite Template UI

**Spec:** SPEC.md (UI Changes) | **Status:** In Progress
**Branch:** `feat/phase1-strings-composite-ui`

---

## Goal

Replace the flat folder-name template field in Fill Form with a single
composite path template field (`{{employee}}/{{project_name}}`), with all
Russian UI text via `strings.py` constants and validation requiring both
placeholders.

---

## Subtasks

- [ ] 1. Strings: add 6 new constants to `docxforge/gui/strings.py`
  - `fill_composite_template_label` — field label
  - `fill_composite_template_placeholder` — placeholder text
  - `fill_composite_template_tooltip` — tooltip text
  - `msg_composite_template_required` — empty template error
  - `msg_composite_employee_required` — missing `{{employee}}` error
  - `msg_composite_project_required` — missing `{{project_name}}` error
- [ ] 2. UI: switch folder-name row in `form_dialog.py` to composite
  constants (label / placeholder / tooltip); add
  `validate_composite_template()` helper + placeholder constants
- [ ] 3. Validation: require both `{{employee}}` and `{{project_name}}`
  in `_validate()` and `_create()` (config_io.py) using new strings
- [ ] 4. Verification: `pytest tests/ -q`, grep checks for constants,
  no hardcoded Russian strings, no changes outside scope

---

## Acceptance Criteria

| AC | Description |
|----|-------------|
| AC-1 | 6 new constants present in `strings.py`, Russian text only there |
| AC-2 | Fill Form folder row shows label "Шаблон пути (сотрудник/проект)", placeholder `{{employee}}/{{project_name}}`, correct tooltip |
| AC-3 | Empty template → `msg_composite_template_required`-based error; missing `{{employee}}` / `{{project_name}}` → respective errors |
| AC-4 | `pytest tests/ -q` passes; no `print()`; engine untouched; `generate.py` untouched |

---

## Files

1. `docxforge/gui/strings.py` — 6 new constants (only addition)
2. `docxforge/gui/fill_form/form_dialog.py` — composite UI + helper
3. `docxforge/gui/fill_form/config_io.py` — validation wiring (minimal, additive)
4. `PLAN_Phase1.md` — this file

Out of scope: `docxforge/generate.py`, `docxforge/engine/*`, `tests/`.

---

## Constraints

- No `print()` — `logging` only
- No hardcoded Russian strings in code — only via `STRINGS`
- Engine stays pure Python (no Qt)
- No `.env` in commits
