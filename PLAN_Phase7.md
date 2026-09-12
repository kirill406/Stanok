# Phase 7: Integration Tests & Polish — Detailed Plan

## Objective
Add integration tests for new features, verify generated projects work normally, run full test suite, and perform manual verification of all acceptance criteria.

## Subtasks

### 1. Create Integration Tests in `tests/test_gui_fill_form.py`
- [ ] Test checkbox toggles UI correctly (auto docs checkbox shows/hides spinbox)
- [ ] Test folder name template input appears/hides based on mode
- [ ] Test button text changes (e.g., "Создать" vs "Проверить" states)
- [ ] Test validation: empty folder name shows warning
- [ ] Test filename template "Insert field" button functionality
- [ ] Test counter column value combo sync (bidirectional)
- [ ] Test recent project template name display
- [ ] Test document count sync between main window and fill form

### 2. Integration Test: Generated Projects Can Generate Documents
- [ ] Create new project via CLI
- [ ] Configure template with fields
- [ ] Generate documents via GUI
- [ ] Verify output in "Результат" folder
- [ ] Verify documents can be re-generated

### 3. Run Full Test Suite
- [ ] `pytest tests/ -q` → all pass (exit code 0)
- [ ] Verify test count matches expected (97 tests)

### 4. Run Smoke Test
- [ ] `python test_engine.py` → exit 0

### 5. Manual Verification of All Acceptance Criteria (AC-1 through AC-8)
- [ ] AC-1: Recent projects show last generated template
- [ ] AC-2: Today field "month" format outputs Russian month name
- [ ] AC-3: "Insert field" button inserts `{{ field_name }}` at cursor
- [ ] AC-4: Counter row spin → value combo sync
- [ ] AC-5: Counter value combo → row spin sync
- [ ] AC-6: Logging to file works (docxforge.log has INFO logs)
- [ ] AC-7: New project creates "Результат" folder
- [ ] AC-8: Document count sync main window ↔ fill form

### 6. Code Quality Checks
- [ ] No new TODOs/FIXMEs introduced
- [ ] No files outside scope modified
- [ ] `rufflehog3 --no-history --no-entropy .` → no secrets

### 7. Commit and Push
- [ ] `git add -A && git commit -m "feat: add integration tests and polish"`
- [ ] `git push -u origin feat/phase-7-integration-tests`
- [ ] `git checkout main && git merge feat/phase-7-integration-tests && git push`

## Expected Outcomes
- All 97+ tests pass
- Smoke test passes
- Engine coverage ≥ 90%
- All 8 ACs manually verified
- Clean merge to main

## Dependencies
- Phases 1-6 must be complete (verified by test suite passing)
- Existing test infrastructure (qtbot, fixtures) working