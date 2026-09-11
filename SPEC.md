# Spec: UI Improvements and Bug Fixes (v1.1)
**Status:** Draft | **Version:** 1.0

---

## Context / Problem

The "Станок" (DocxForge) application has several usability issues and bugs that need to be addressed:

1. **Recent projects list** doesn't show which template was last generated, making it hard for users to identify projects.
2. **Today field** lacks a "month" format option for full Russian month names (e.g., "сентября").
3. **Filename template** field has no "Insert field" button, forcing users to type `{{ field_name }}` manually.
4. **Counter column current row** in batch generation only shows a spin box with row number, but not the actual value from that row. Users can't see or select the row by its content.
5. **Logging** is configured but doesn't write to file (`docxforge.log` is created but empty or missing).
6. **Output folder** is named "output" (English) instead of "Результат" (Russian) for new projects.
7. **Document count sync** between main window's recent project spin box and the fill form's total docs spin box is broken — changes in fill form don't propagate to main window.

---

## Functional Requirements

### FR-1: Recent Projects Show Last Generated Template
- FR-1.1: The recent project widget in the main window MUST display the name of the last generated template next to the project name.
- FR-1.2: This template name MUST be persisted in settings and restored on app restart.
- FR-1.3: When generating from main window ("Сгенерировать" button), the template used MUST be recorded.

### FR-2: Today Field "month" Format
- FR-2.1: The today field format combobox MUST include a "month" option (or equivalent) that outputs the full Russian month name (e.g., "сентября").
- FR-2.2: The format MUST work both in template placeholders (`{{ today:month }}`) and in GUI field configuration.
- FR-2.3: The format string MUST be parseable by the existing `format_today` function.

### FR-3: "Insert Field" Button in Filename Template
- FR-3.1: The filename template row in the fill form MUST have an "Insert field" button (or dropdown) next to the input field.
- FR-3.2: Clicking the button MUST show a list of available field names from the current template configuration.
- FR-3.3: Selecting a field MUST insert `{{ field_name }}` at the current cursor position in the filename template input.

### FR-4: Counter Column Current Row Value Display and Selection
- FR-4.1: For batch sources in "По строкам" (sequential) or "По кругу" (circular) mode, the counter panel MUST show both:
  - "Текущая строка" (row number spin box) — existing
  - "Значение текущей строки" (combo box with distinct values from the counter column) — NEW
- FR-4.2: Changing the row number spin box MUST update the value combo box to show the corresponding value from that row.
- FR-4.3: Changing the value combo box MUST update the row number spin box to the matching row index (1-based).
- FR-4.4: Both controls MUST stay in sync bidirectionally.
- FR-4.5: The counter column MUST be selectable (already implemented via combo box).

### FR-5: Fix Logging to File
- FR-5.1: Application logs MUST be written to `docxforge.log` in the working directory (next to executable or script).
- FR-5.2: Log file MUST use UTF-8 encoding.
- FR-5.3: Log level MUST be INFO or higher.
- FR-5.4: Log format MUST include timestamp, logger name, level, and message.

### FR-6: Rename Output Folder to "Результат"
- FR-6.1: When creating a new project, the default output directory MUST be named "Результат" instead of "output".
- FR-6.2: The generate function MUST use "Результат" as the default output directory name.
- FR-6.3: Existing projects with "output" folder MUST continue to work (backward compatibility).

### FR-7: Document Count Sync Between Main Window and Fill Form
- FR-7.1: When the user changes "Количество документов" in the fill form, the value MUST be saved to settings.
- FR-7.2: The main window's recent project spin box MUST reflect this value when the project is re-opened or refreshed.
- FR-7.3: The sync MUST work in both directions: main window → fill form and fill form → main window.

---

## Non-Functional Requirements

- NFR-1: All changes MUST maintain backward compatibility with existing projects.
- NFR-2: No new external dependencies MUST be added.
- NFR-3: UI text MUST remain in Russian (existing convention).
- NFR-4: Performance impact MUST be negligible (<50ms additional latency).

---

## Acceptance Criteria

| AC | Requirement | Given / When / Then |
|----|-------------|---------------------|
| AC-1 | FR-1 | Given a project with generated documents, When user opens main window, Then recent project shows template name |
| AC-2 | FR-2 | Given a template with `{{ today:month }}`, When document is generated in September, Then output contains "сентября" |
| AC-3 | FR-3 | Given fill form open, When user clicks "Insert field" and selects "client_name", Then `{{ client_name }}` appears in filename template |
| AC-4 | FR-4 | Given batch source in sequential mode with counter column "name", When user changes row spin to 3, Then value combo shows row 3's name value |
| AC-5 | FR-4 | Given batch source in sequential mode, When user selects "Ivanov" in value combo, Then row spin updates to row index of "Ivanov" |
| AC-6 | FR-5 | Given app runs and generates documents, When checking `docxforge.log`, Then file contains INFO level logs with timestamps |
| AC-7 | FR-6 | Given new project created, When checking project folder, Then "Результат" folder exists (not "output") |
| AC-8 | FR-7 | Given fill form with total docs = 5, When user closes form and reopens main window, Then recent project spin shows 5 |

---

## Edge Cases / Error Scenarios

| EC | Scenario | Handling |
|----|----------|----------|
| EC-1 | Counter column has duplicate values | Value combo shows duplicates; row spin picks first match |
| EC-2 | Counter column is empty | Value combo disabled; row spin works normally |
| EC-3 | Template name contains special chars | Escaped properly in settings JSON |
| EC-4 | Log file permission denied | Fallback to stdout only; show warning in UI |
| EC-5 | "Результат" folder already exists | Use existing folder; don't create "output" |
| EC-6 | Settings file corrupted | Reset to defaults; don't crash |

---

## API Contracts

No external API changes. Internal changes only:

### Settings File (`docxforge_settings.json`)
```json
{
  "recent_projects": ["/path/to/project1", "/path/to/project2"],
  "doc_counts": {
    "/path/to/project1": 5
  },
  "last_template": {
    "/path/to/project1": "Договоры/договор_поставки.docx"
  }
}
```

### Template Parser / Formatter
- `format_today(fmt, dt)` — add support for `month` or `MMMM` token → full Russian month name
- `scan_template()` — no changes needed

---

## Data Models

### RecentProjectWidget (main_window.py)
- Add `last_template_name: str` field
- Persist in settings under `last_template` map

### BatchSourceRow (batch_section.py)
- Add `counter_value_combo: QComboBox` for displaying/selecting row values
- Bidirectional sync with `counter_row_spin` (ccr)

### Project Creation (schema.py / generate.py)
- Default output directory name: "Результат" (Russian)

---

## Out of Scope

- Web version or cloud sync
- Multiple template selection in main window generation
- Advanced date formats beyond "month" (e.g., "quarter", "weekday")
- Drag-and-drop for field insertion
- Migration tool for existing "output" folders (handled by backward compatibility)
- Custom log file location (uses working directory)

---

## References

- `docxforge/gui/main_window.py` — main window, recent projects, generation
- `docxforge/gui/fill_form/batch_section.py` — batch source rows, counter panel
- `docxforge/gui/fill_form/field_rows.py` — today format combobox
- `docxforge/gui/fill_form/form_dialog.py` — fill form, filename template
- `docxforge/engine/formatting.py` — `format_today` function
- `docxforge/engine/schema.py` — project creation, default output dir
- `docxforge/generate.py` — generation entry point, output directory
- `run.py` — logging configuration