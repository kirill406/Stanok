# SPEC.md — Create Projects from Template Mode

## Overview
Add a "Create Projects" mode to Fill Form that generates separate project folders (each with its own `проект.docxforge`) from the current template, instead of generating documents. Constant fields are preserved for later document generation; TABLE fields are populated from Excel data (one row per project); COUNTER fields reset to start.

---

## User Flow

1. User opens Fill Form for a template
2. Checks new checkbox **"Создать проекты вместо документов"** (Create projects instead of documents)
3. UI adapts:
   - Shows **"Шаблон имени папки проекта"** (folder name template) input
   - Hides filename/directory template outputs (not applicable)
   - Shows **"Найдено строк: N. Сколько проектов создать?"** dialog if table rows > expected
4. User clicks **"Создать проекты"**
5. For each row (up to user-confirmed count):
   - Create `Projects/<folder_name>/` subfolder
   - Copy current project structure (templates, schemas)
   - Write `проект.docxforge` with:
     - Constant fields → same values
     - TABLE fields → values from current row
     - COUNTER fields → reset to start
     - All other settings copied (batch sources, filename templates, etc.)
6. Show summary: "Создано M проектов в Projects/"

---

## UI Changes

### Fill Form (`docxforge/gui/fill_form/form_dialog.py`)
- Add checkbox: `chk_create_projects` — "Создать проекты вместо документов"
- When checked:
  - Show `edit_folder_name_template` (string, e.g., `Project_{{client_name}}_{{doc_number}}`)
  - Hide `edit_filename_template`, `edit_directory_template` (or disable)
  - Change button text: "Создать проекты" (instead of "Сгенерировать")
- Validation: folder name template must not be empty when mode active

### Strings (`docxforge/gui/strings.py`)
```python
'fill_create_projects': 'Создать проекты вместо документов',
'fill_folder_name_template': 'Шаблон имени папки проекта',
'fill_found_rows': 'Найдено строк: {count}. Сколько проектов создать?',
'fill_projects_created': 'Создано {count} проектов в {path}',
```

---

## Core Logic

### Entry Point
- New method in `generate.py` or `render_execute.py`: `create_projects_from_template()`
- Called from `FillForm._create()` when checkbox checked

### Algorithm
```python
def create_projects_from_template(project_path, template_name, folder_name_template, max_projects=None):
    # 1. Load current project
    project = Project.from_file(project_path + '/проект.docxforge')
    config = project.templates[template_name]
    
    # 2. Read all table data for batch sources
    all_table_data = DataReader.read_all_batch_sources(project_path, config.batch_sources)
    primary_source = config.get_primary_batch_source()  # first sequential source
    rows = all_table_data[primary_source.file]
    
    # 3. Determine count
    total_rows = len(rows)
    if max_projects is None:
        max_projects = ask_user(f"Найдено строк: {total_rows}. Сколько проектов создать?")
    max_projects = min(max_projects, total_rows)
    
    # 4. Create output folder
    projects_dir = os.path.join(project_path, 'Projects')
    os.makedirs(projects_dir, exist_ok=True)
    
    # 5. For each row
    for i in range(max_projects):
        row = rows[i]
        
        # 5a. Resolve folder name
        folder_name = resolve_template(folder_name_template, row, constants=config.get_constants())
        project_dir = os.path.join(projects_dir, folder_name)
        os.makedirs(project_dir, exist_ok=True)
        
        # 5b. Build new project config
        new_config = deepcopy(config)
        new_config.fields = {}
        
        for field_name, field_mapping in config.fields.items():
            if field_mapping.type == FieldType.CONSTANT:
                # Copy constant as-is
                new_config.fields[field_name] = field_mapping
            elif field_mapping.type == FieldType.TABLE:
                # Fill with row value
                value = row.get(field_mapping.column, '')
                new_config.fields[field_name] = FieldMapping(
                    type=FieldType.CONSTANT, value=value
                )
            elif field_mapping.type == FieldType.COUNTER:
                # Reset to start
                new_config.fields[field_name] = FieldMapping(
                    type=FieldType.COUNTER,
                    start=field_mapping.start,
                    step=field_mapping.step,
                    format=field_mapping.format
                )
            else:
                # Copy other types as-is (AGGREGATION, TODAY, etc.)
                new_config.fields[field_name] = field_mapping
        
        # 5c. Copy batch sources, filename/dir templates, resume (empty)
        # Resume state: fresh (no continue_from_last)
        
        # 5d. Write проект.docxforge
        new_project = Project(
            version=project.version,
            templates={template_name: new_config}
        )
        new_project.to_file(os.path.join(project_dir, 'проект.docxforge'))
        
        # 5e. Copy template files to project/Шаблоны/
        copy_templates(project_path, project_dir, [template_name])
    
    return projects_dir, max_projects
```

---

## Data Structures

### FieldMapping changes
- No changes needed; reuse existing `FieldMapping` with `type=CONSTANT` for populated TABLE fields

### Project structure copied
- `Шаблоны/<template_name>.docx` → new project/Шаблоны/
- `проект.docxforge` regenerated with new field values
- `Данные/` — NOT copied (each project references original Excel files via batch sources)

---

## Edge Cases

| Case | Handling |
|------|----------|
| Folder name resolves to empty/duplicate | Append `_1`, `_2`... or show error |
| Template file missing | Abort with error |
| No batch sources configured | Disable checkbox / show warning |
| User cancels row count dialog | Abort, no projects created |
| Permission denied on folder create | Show error, rollback created folders |

---

## Testing

### Unit tests (`tests/test_create_projects.py`)
- `test_create_projects_basic`: 1 template, 1 table, 3 rows → 3 projects
- `test_constants_preserved`: constant fields copied unchanged
- `test_table_fields_populated`: each project gets correct row values
- `test_counter_reset`: each project counter starts at start value
- `test_folder_name_template`: template resolved with row data
- `test_max_projects_limit`: user limit respected
- `test_no_batch_sources`: graceful handling

### Integration tests
- Full flow via Fill Form UI (QTest)
- Verify generated `проект.docxforge` can generate documents

---

## Files to Modify

| File | Changes |
|------|---------|
| `docxforge/gui/fill_form/form_dialog.py` | Checkbox, folder name template input, logic switch |
| `docxforge/gui/strings.py` | New string constants |
| `docxforge/generate.py` | New `create_projects_from_template()` function |
| `docxforge/engine/render_execute.py` | Reuse `resolve_field_values` logic for folder name |
| `tests/test_create_projects.py` | New test file |
| `tests/test_gui_fill_form.py` | UI tests for new mode |

---

## Acceptance Criteria

- [ ] Checkbox appears in Fill Form, toggles UI correctly
- [ ] Folder name template works with `{{field}}` placeholders
- [ ] Projects created in `Projects/` subfolder
- [ ] Each project has valid `проект.docxforge`
- [ ] Constant fields preserved, TABLE fields populated per row, COUNTER reset
- [ ] Template .docx files copied to each project
- [ ] Row count dialog appears when rows > 1
- [ ] Generated projects can generate documents normally
- [ ] All existing tests pass
- [ ] New tests cover core logic and UI