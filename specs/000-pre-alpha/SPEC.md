# SPEC.md — Nested Employee/Project Generation (v1.0)

Status: done

## Overview
Extend "Create Projects" mode to generate **two-level nested folder structure**: Employee → Projects. Input: single Excel batch source with `employee` and `project_name` columns. Output: `EmployeeFolder/ProjectFolder/` with data, templates, result folders + `проект.docxforge`. Employee folder contains `docxforge_settings.json` listing their projects.

---

## User Flow

1. User opens Fill Form for template with batch source containing `employee` + `project_name` columns
2. Checks **"Создать проекты вместо документов"**
3. Enters **composite folder template**: e.g., `{{employee}}/{{project_name}}`
4. Clicks **"Создать проекты"**
5. System:
   - Reads batch source, groups rows by `employee` value
   - For each unique employee:
     - Creates `EmployeeFolder/` (resolved from template)
     - Creates `docxforge_settings.json` with list of their projects
     - For each project row of that employee:
       - Creates `ProjectFolder/` inside employee folder
       - **Copies entire `Данные/` folder** from source project (all Excel files unchanged)
       - Copies template → `шаблоны/`
       - Creates empty `результат/`
       - Generates `проект.docxforge` with:
         - CONSTANT fields preserved
         - TABLE fields → CONSTANT with row values
         - COUNTER reset to start
         - Batch sources → CONSTANT mode (data already in `данные/`)
6. Shows summary: "Создано N сотрудников, M проектов в [path]"

---

## Folder Structure

```
<project_root>/
  Projects/
    {{employee_folder}}/             # e.g., "Иванов_Иван"
      docxforge_settings.json        # {employee: "Иванов Иван", projects: [...]}
      {{project_folder}}/            # e.g., "Договор_001"
        данные/                      # FULL COPY of source project's Данные/
        шаблоны/                     # copied .docx template
        результат/                   # empty, for generated docs
        проект.docxforge             # config for this project
```

---

## docxforge_settings.json (Employee Folder)

```json
{
  "employee": "Иванов Иван",
  "employee_folder": "Иванов_Иван",
  "created_at": "2025-09-12T14:30:00",
  "projects": [
    {
      "name": "Договор_001",
      "folder": "Договор_001",
      "template": "all_fields.docx",
      "row_index": 0,
      "created_at": "2025-09-12T14:30:00"
    }
  ]
}
```

---

## UI Changes (Fill Form)

- **Single composite template** field:
  - Label: "Шаблон пути (сотрудник/проект)"
  - Placeholder: `{{employee}}/{{project_name}}`
  - Tooltip: "{{employee}} — папка сотрудника, {{project_name}} — папка проекта"
- Validation: template must contain both placeholders
- Strings: 6 new constants in `docxforge/gui/strings.py`

---

## Core Logic

- New function `create_nested_employee_projects()` in `docxforge/generate.py`
- Detects composite template (contains `/` and both placeholders)
- Groups primary source rows by `employee` column
- For each employee group: creates folder, writes settings.json, iterates projects
- For each project: resolves folder name, copies `Данные/`, `шаблоны/`, creates `результат/`, writes `проект.docxforge`
- Falls back to flat structure if template doesn't match composite pattern

---

## Data Handling

- **No slicing**: `Данные/` folder copied entirely from source project (shutil.copytree)
- Batch sources in new project config → CONSTANT mode (data already present)
- Original Excel files unchanged, referenced by copied data

---

## Edge Cases

| Case | Handling |
|------|----------|
| Missing `employee`/`project_name` column | Error with clear message |
| Duplicate project folders in same employee | Append `_1`, `_2` |
| Empty resolved folder name | Fallback: `employee_N`, `project_N` |
| No sequential batch source | Error (required) |
| Permission denied | Rollback, show error |
| User cancels row count dialog | Abort, no folders created |

---

## Acceptance Criteria

- [ ] Composite template `{{employee}}/{{project_name}}` works
- [ ] Employee folders with `docxforge_settings.json` created
- [ ] Project folders with `данные/`, `шаблоны/`, `результат/`, `проект.docxforge`
- [ ] `данные/` is full copy of source project's data
- [ ] `проект.docxforge`: TABLE→CONSTANT, COUNTER reset, batch→CONSTANT
- [ ] `docxforge_settings.json` lists all employee's projects
- [ ] Row count dialog works for total projects
- [ ] Success message shows employee and project counts
- [ ] Backward compatible with flat structure
- [ ] All existing tests pass