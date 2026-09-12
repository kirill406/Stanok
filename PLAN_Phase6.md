# Plan: Phase 6 — Unit Tests for Create Projects Mode
**Spec:** SPEC.md | **Status:** Approved

---

## Goals

- Create comprehensive unit tests for the "Create Projects" mode
- Test that multiple projects can be generated from a single template and batch source
- Verify constant fields, table fields, counters, and folder name templates work correctly
- Ensure edge cases are handled (no batch sources, max projects limit)

---

## Non-Goals

- Implementation of the "Create Projects" feature (separate phase)
- GUI integration tests
- CLI command tests

---

## Constraints

- Follow existing code style: 4 spaces, UTF-8, snake_case functions, PascalCase classes
- Russian UI text (existing convention)
- Imports: stdlib → third-party → local, one per line
- Use existing patterns in referenced files
- No external dependencies beyond current requirements.txt
- Use fixtures from `tests/documents/` pattern
- Mock user dialog for row count

---

## References

| File | Purpose |
|------|---------|
| `docxforge/engine/schema.py:254-260` | `create_project` — project folder creation |
| `docxforge/engine/render_loop.py:241-250` | `directory_template` resolution |
| `tests/create_fixtures.py` | Fixture creation patterns |
| `tests/conftest.py` | Shared pytest fixtures |
| `tests/test_cli.py` | CLI test patterns |

---

## Subtasks

### 6.1: Create PLAN_Phase6.md
- [x] Document detailed subtasks for Phase 6

### 6.2: Implement `create_projects` function in `docxforge/engine/schema.py`
- [ ] Add `create_projects` function that creates multiple projects from template + batch source
- [ ] Accept parameters: template project dir, output base dir, batch source file, max projects limit
- [ ] For each row in batch source (sequential mode), create a new project with:
  - Constant fields copied unchanged
  - Table fields populated from row data
  - Counter fields reset to start value
  - Folder name resolved from `directory_template` with row data
- [ ] Return list of created project paths

### 6.3: Create `tests/test_create_projects.py` with tests:
- [ ] `test_create_projects_basic`: 1 template, 1 table, 3 rows → 3 projects
- [ ] `test_constants_preserved`: constant fields copied unchanged
- [ ] `test_table_fields_populated`: each project gets correct row values
- [ ] `test_counter_reset`: each project counter starts at start value
- [ ] `test_folder_name_template`: template resolved with row data
- [ ] `test_max_projects_limit`: user limit respected
- [ ] `test_no_batch_sources`: graceful handling (returns empty list or raises appropriate error)
- [ ] Use fixtures from `tests/documents/` pattern
- [ ] Mock user dialog for row count (if applicable)

### 6.4: Run tests and verify
- [ ] `pytest tests/test_create_projects.py -v` → all tests pass

### 6.5: Commit and push
- [ ] `git add -A && git commit -m "feat: add unit tests for create projects mode"`
- [ ] `git push -u origin feat/phase-6-unit-tests`
- [ ] `git checkout main && git merge feat/phase-6-unit-tests && git push`

---

## Definition of Done

- [ ] `pytest tests/test_create_projects.py -v` → exit 0 (all tests pass)
- [ ] `pytest tests/ -q` → exit 0 (no regressions)
- [ ] No files outside scope modified
- [ ] No new TODOs or FIXMEs in code

---

## Risks / Open Questions

| Risk | Mitigation |
|------|------------|
| Feature not yet implemented | Implement minimal `create_projects` function alongside tests |
| Fixture setup complexity | Reuse `create_fixtures.py` patterns and `temp_project_dir` fixture |
| Counter reset logic | Ensure each new project gets fresh counter state from template config |