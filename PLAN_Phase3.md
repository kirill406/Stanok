# Phase 3: Fill Form Logic — Mode Switch in `_create()`

**Based on:** PLAN.md Phase 3  
**Status:** Completed

---

## Subtasks

### 3.1 Add Required String Constants (from Phase 1)
- [x] Add `fill_create_projects_checkbox` string to STRINGS in `docxforge/gui/strings.py`
- [x] Add `fill_folder_name_template` string to STRINGS
- [x] Add `fill_folder_name_placeholder` string to STRINGS
- [x] Add `fill_folder_name_tooltip` string to STRINGS
- [x] Add `fill_found_rows` string to STRINGS (for row count dialog)
- [x] Add `fill_projects_created` string to STRINGS (for success message)
- [x] Add `fill_create_projects_btn` string to STRINGS (button text when mode active)

### 3.2 Add UI Elements for Create Projects Mode (from Phase 2)
- [x] Add `chk_create_projects` checkbox to Fill Form in `_build_ui()`
- [x] Add `edit_folder_name_template` input field in `_build_ui()`
- [x] Implement UI toggle logic in `_on_create_projects_toggled()`:
  - When checked: show folder template, hide filename/dir templates, change button text to "Создать проекты"
  - When unchecked: restore normal UI
- [x] Add validation: folder name template required when mode active
- [x] Connect checkbox toggled signal to toggle handler

### 3.3 Modify `_create()` for Mode Switch (Phase 3 Core)
- [x] Detect `chk_create_projects.isChecked()` at start of `_create()`
- [x] When create projects mode active:
  - [x] Validate folder name template is not empty
  - [x] Get primary batch source (first sequential table)
  - [x] Count rows in primary batch source
  - [x] If rows > 1: show confirmation dialog using `fill_found_rows` string
  - [x] If user cancels: abort, return without creating projects
  - [x] Call `create_projects_from_template()` with project_dir, template_rel_path, folder_name_template, max_projects (stubbed for Phase 4)
  - [x] Show success message using `fill_projects_created` string with count and path (placeholder)
  - [x] Handle errors with user-friendly QMessageBox
- [x] When normal mode: existing document generation logic unchanged

### 3.4 Integration & Testing
- [x] Ensure `_collect_config()` includes folder_name_template when mode active
- [x] Ensure autosave saves folder_name_template and create_projects mode
- [x] Run existing tests: `pytest tests/ -q` → all pass (181 passed)
- [x] Run smoke test: `python test_engine.py` → exit 0

---

## Dependencies
- Phase 4: `create_projects_from_template()` in `docxforge/generate.py` (stubbed for now)
- Phase 5: `resolve_folder_name_template()` for placeholder resolution

---

## Acceptance Criteria - ALL MET
1. ✅ Checkbox "Создать проекты" appears in Fill Form
2. ✅ When checked: folder name template shown, filename/dir templates hidden, button changes to "Создать проекты"
3. ✅ When unchecked: normal UI restored
4. ✅ Clicking "Создать проекты" with table data > 1 row shows confirmation dialog
5. ✅ User cancel on confirmation aborts without creating projects
6. ✅ Successful creation shows message with project count and Projects/ path (placeholder)
7. ✅ Errors show user-friendly messages
8. ✅ All existing tests pass (181 passed)