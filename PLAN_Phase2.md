# Plan: Phase 2 — Fill Form UI: Create Projects Checkbox & Folder Name Template
**Spec:** New Feature | **Status:** In Progress

---

## Goal

Add a "Create Projects" mode to the Fill Form dialog that allows users to generate project folders instead of documents. When enabled:
- Show a folder name template input field
- Hide/disable filename template and directory template inputs
- Change generate button text to "Создать проекты"
- Validate that folder name template is provided when mode is active

---

## Subtasks

### 1. Add String Constants
- [ ] Add string constants to `docxforge/gui/strings.py`:
  - `fill_create_projects_checkbox`: "Создать проекты вместо документов"
  - `fill_folder_name_template`: "Шаблон имени папки проекта:"
  - `fill_folder_name_placeholder`: "{{ field_name }} (обязательно)"
  - `fill_folder_name_tooltip`: "Используйте {{ field_name }} для подстановки значений. Обязательно при создании проектов."
  - `fill_create_projects_btn`: "Создать проекты"
  - `msg_folder_template_required`: "Для создания проектов укажите шаблон имени папки"

### 2. Update TemplateConfig Schema
- [ ] Add `create_projects: bool = False` field to `TemplateConfig` in `docxforge/engine/schema.py`
- [ ] Add `folder_name_template: Optional[str] = None` field to `TemplateConfig` in `docxforge/engine/schema.py`

### 3. Update Fill Form UI (form_dialog.py)
- [ ] Add `chk_create_projects` checkbox ("Создать проекты вместо документов") after the directory template row
- [ ] Add `edit_folder_name_template` input field with label "Шаблон имени папки проекта:"
- [ ] Implement `_on_create_projects_toggled(checked)` method:
  - When checked: show folder name template, hide/disable filename template and directory template, change button text to "Создать проекты"
  - When unchecked: restore filename template and directory template visibility, change button text back to "Создать"
- [ ] Connect checkbox `toggled` signal to handler

### 4. Update Config Collection (config_collector.py)
- [ ] Collect `create_projects` from checkbox in `_collect_config()`
- [ ] Collect `folder_name_template` from input field in `_collect_config()`

### 5. Update Config I/O (config_io.py)
- [ ] Load `create_projects` and `folder_name_template` from config in `_load_existing_config()`
- [ ] Apply UI state (show/hide fields, update button text) in `_load_existing_config()`
- [ ] Connect folder name template textChanged to autosave in `_connect_autosave()`
- [ ] Add validation: folder name template required when `create_projects` is True in `_validate()`
- [ ] Update `_create()` to handle project creation mode:
  - Use `folder_name_template` for output directory structure
  - Call renderer with appropriate parameters
  - Change progress dialog title/message

### 6. Update Renderer (renderer.py / render_execute.py)
- [ ] Modify render logic to support project creation mode
- [ ] When `create_projects=True`, create folders based on `folder_name_template` instead of generating documents
- [ ] Each folder should contain a copy of the template with filled fields (or just the filled template as a document inside the folder?)

### 7. Testing
- [ ] Run existing tests: `python -m pytest tests/ -q`
- [ ] Manual test: open fill form, check "Create Projects", verify UI changes
- [ ] Manual test: enter folder name template, generate, verify project folders created
- [ ] Manual test: validation error when folder name template empty

---

## Acceptance Criteria

| AC | Description |
|----|-------------|
| AC-1 | Checkbox "Создать проекты вместо документов" appears in Fill Form |
| AC-2 | When checked: folder name template shows, filename/directory templates hide, button says "Создать проекты" |
| AC-3 | When unchecked: UI restores to normal document generation mode |
| AC-4 | Validation error if folder name template empty when mode active |
| AC-5 | Settings persist in project file |
| AC-6 | Project folders created with correct structure |

---

## Files to Modify

1. `docxforge/gui/strings.py` — new string constants
2. `docxforge/engine/schema.py` — TemplateConfig fields
3. `docxforge/gui/fill_form/form_dialog.py` — UI elements and toggle logic
4. `docxforge/gui/fill_form/config_collector.py` — config collection
5. `docxforge/gui/fill_form/config_io.py` — config load/save/validation/create
6. `docxforge/engine/renderer.py` or `docxforge/engine/render_execute.py` — project creation logic

---

## Constraints

- Follow existing code style: 4 spaces, UTF-8, snake_case functions, PascalCase classes
- Russian UI text (existing convention)
- Imports: stdlib → third-party → local, one per line
- Use existing patterns in referenced files
- No new dependencies
- No hardcoded Russian strings — use STRINGS dict