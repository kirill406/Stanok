# Plan: Nested Employee/Project Generation (v1.0)
**Spec:** SPEC.md | **Status:** Approved

---

## Goals

- Extend Create Projects mode to generate two-level structure: Employee → Projects
- Input: Excel with employee + project_name columns
- Output: nested folders with full data copy, settings.json per employee
- No new dependencies; backward compatible with flat mode

---

## Constraints

- Follow existing code style: 4 spaces, UTF-8, snake_case, PascalCase
- Russian UI text
- Imports: stdlib → third-party → local, one per line
- Use existing patterns
- No external dependencies beyond requirements.txt

---

## References

| File | Purpose |
|------|---------|
| `docxforge/gui/fill_form/form_dialog.py` | Fill Form UI |
| `docxforge/gui/strings.py` | UI strings |
| `docxforge/generate.py` | Generation entry points |
| `docxforge/engine/schema.py` | Project, TemplateConfig, FieldMapping |

---

## Phases

### Phase 1: Strings & Composite Template UI
- Add 6 string constants to `strings.py`
- Replace folder name template field with composite template field in Fill Form
- Add validation: both `{{employee}}` and `{{project_name}}` required
- Update UI labels and tooltips

### Phase 2: Template Parsing & Detection
- Add `parse_composite_template()` helper in `generate.py`
- Detect composite vs flat mode in `create_projects_from_template()`
- Route to `create_nested_employee_projects()` when composite detected

### Phase 3: Core Nested Generation Logic
- Implement `create_nested_employee_projects()` in `generate.py`
- Read batch data, group by `employee` column
- For each employee: create folder, write `docxforge_settings.json`
- For each project: resolve folder name, create structure, copy data/templates, write config

### Phase 4: Project Config & File Operations
- Build project config: TABLE→CONSTANT, COUNTER reset, batch→CONSTANT
- Copy `Данные/` folder entirely (shutil.copytree)
- Copy template files to `шаблоны/`
- Create empty `результат/`
- Write `проект.docxforge` and `docxforge_settings.json`

### Phase 5: Integration with Fill Form
- Wire composite mode in `FillForm._create()`
- Show row count dialog for total projects across employees
- Show success message with employee/project counts
- Handle errors and user cancel

### Phase 6: Unit Tests
- Create `tests/test_nested_projects.py`
- Test: basic nested generation (2 employees, 3 projects each)
- Test: data folder copied fully
- Test: settings.json structure and content
- Test: config transformation (TABLE→CONSTANT, COUNTER reset)
- Test: composite template parsing
- Test: max projects limit
- Test: missing column errors
- Test: backward compatibility (flat mode still works)

### Phase 7: Integration Tests & Polish
- Add UI tests for composite template field in `test_gui_fill_form.py`
- Verify generated projects can generate documents
- Run full test suite: all pass
- Manual verification of acceptance criteria

---

## Definition of Done

- `pytest tests/ -q` → all pass
- `python test_engine.py` → passes
- Manual verification of all acceptance criteria
- No files outside scope modified
- No new TODOs/FIXMEs
- `rufflehog3 --no-history --no-entropy .` → no secrets

---

## Risks

| Risk | Mitigation |
|------|------------|
| Missing employee/project_name column | Clear error message |
| Duplicate folder names | Auto-suffix `_1`, `_2` |
| Large data copy performance | Acceptable for typical sizes |
| Permission errors | Rollback on failure |
| Backward compatibility | Detect flat vs composite template |

---

## Progress Tracking

| Phase | Tasks | Verification | Status |
|-------|-------|--------------|--------|
| 1 | Strings & Composite Template UI | Manual + grep | ✅ 231→244 passed |
| 2 | Template Parsing & Detection | Unit test | ✅ 231 passed |
| 3 | Core Nested Generation Logic | Unit test | ✅ 231 passed + smoke |
| 4 | Project Config & File Operations | Unit test | ✅ 244 passed + smoke |
| 5 | Fill Form Integration | Manual + integration test | ✅ 244 passed |
| 6 | Unit Tests | pytest test_nested_projects.py | ✅ 13 passed, 244 total |
| 7 | Integration Tests & Polish | pytest tests/ -q | ✅ 253 passed |

---

## Checkpoint Commits

- `feat: add strings and composite template UI for nested projects`
- `feat: add template parsing and mode detection`
- `feat: implement nested employee/project generation core`
- `feat: add project config transformation and file operations`
- `feat: wire nested mode in Fill Form`
- `feat: add unit tests for nested projects`
- `feat: add integration tests and polish`

---

## Execution Notes

- 7 phases → can use 7 folders (FirstAgent through FirstAgentF7)
- Each subagent: git pull → branch → implement → commit/push → merge to main
- Orchestrator waits for all, updates FirstAgent docs, commits, pushes