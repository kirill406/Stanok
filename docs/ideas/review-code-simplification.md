# Review: Code Simplification - File Splitting

## Summary
Split large source files (781, 554, 508, 350, 226 lines) into focused modules of 100-200 lines each, preserving 100% backward compatibility and all 104 tests passing.

## Files Changed

### engine/ - Renderer split
- renderer.py: 554 -> 166 lines (class Renderer + project I/O)
- NEW xml_utils.py: 59 lines (XML utilities: run_text, clone_run, etc.)
- NEW merge.py: 105 lines (paragraph merge, table cycle expansion)
- NEW formatting.py: 60 lines (aggregation, counter, date formatting)
- NEW render_loop.py: 188 lines (field resolution, XML processing, file output)
- NEW render_execute.py: 152 lines (main render loop orchestration)
- engine/__init__.py: re-exports all public names

### cli/ - CLI package
- cli.py: 350 -> 8 lines (thin wrapper)
- NEW docxforge/cli/__init__.py: 3 lines
- NEW docxforge/cli/helpers.py: 24 lines (project load/save)
- NEW docxforge/cli/commands.py: 210 lines (create/scan/configure/render/list)
- NEW docxforge/cli/info_cmd.py: 73 lines (info command + tree printer)
- NEW docxforge/cli/parser.py: 92 lines (argparse setup)

### gui/fill_form/ - Fill form split into mixin package
- gui/fill_form.py: 781 -> DELETED (replaced by package)
- NEW gui/fill_form/__init__.py: 4 lines (re-exports)
- NEW gui/fill_form/constants.py: 14 lines (FIELD_TYPES, FIELD_TYPES_ENUM)
- NEW gui/fill_form/form_dialog.py: 204 lines (FillForm class with mixins)
- NEW gui/fill_form/field_rows.py: 182 lines (field widget rows)
- NEW gui/fill_form/advanced_section.py: 116 lines (cycles, aggregations)
- NEW gui/fill_form/batch_section.py: 93 lines (batch sources, resume)
- NEW gui/fill_form/config_io.py: 152 lines (load/save config, autosave)
- NEW gui/fill_form/config_collector.py: 111 lines (collect TemplateConfig from widgets)

### gui/ - Field dialog data extraction
- NEW gui/field_templates.py: 63 lines (FIELD_TEMPLATES data)
- gui/field_dialog.py: 226 -> 203 lines (now imports from field_templates.py)

### tests/ - Test file split
- test_additional.py: 508 -> 299 lines (renderer edge cases + GUI)
- NEW test_data_reader_and_schema.py: 209 lines
- NEW test_formatting_unit.py: 213 lines
- All test files: updated imports from docxforge.engine (not .renderer directly)

### Minor fixes (pre-existing)
- template_parser.py: any -> Any type hint fix
- project_window.py: import shutil moved to top
- .env.example: empty default values
- .gitignore: added htmlcov/, .pytest_cache/

## Test Results
- 104 tests: ALL PASSED
- No circular imports
- All public APIs preserved via __init__.py re-exports

## Architecture
- Dependency graph is strictly unidirectional (no cycles)
- xml_utils <- merge <- render_loop <- render_execute <- renderer
- Mixin pattern for FillForm: FieldRowsMixin, AdvancedSectionMixin, BatchSectionMixin, ConfigIOMixin, ConfigCollectorMixin
- cli package: helpers <- commands/info_cmd <- parser
