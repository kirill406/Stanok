# PLAN_003_Phase1 — Filling JSON → docx (P1, `feat/003-render-json`)

Scope: only `src/docxforge/engine/` + tests. `gui/` / `cli.py` untouched.
Spec: `specs/003-json/spec.md` (Phase 1), Filling JSON format:
`{"template": "name.docx", "dist": "out/file.docx", "fields": {name: value}}`.

## Subpoints (one commit + push each)

- [x] 1. Plan file (`PLAN_003_Phase1.md`) — this file.
- [x] 2. `Renderer.render_from_json(filling, output_dir=None)` in
  `src/docxforge/engine/renderer.py` + validation message codes in
  `src/docxforge/engine/errors.py`. Validation: `filling` must be a dict,
  `template` non-empty string, `fields` present and a dict — else
  `ValueError` with centralized message (`message_for_code`, no hardcoded
  literals at call site, no `print`, `logging` only). Render via existing
  `render()` with `fields` as `user_values` (values coerced to `str`,
  `None` → `''`); `output_dir` param wins, else `dist` dirname (relative →
  under `project_dir`), else engine default. Returns list of created files.
  Rationale for `ValueError` over `GenerationError`: `renderer.py` cannot
  import `docxforge.generate` (circular: `generate` imports `Renderer`);
  `generate.py` (P4) wraps into `GenerationError` at its own boundary.
- [x] 3. Harness `tests/test_json_fixtures.py` → `render_from_json`
  (allowed consumer-side change; no fixture content changes).
- [x] 4. New `tests/test_003_render_json.py`: validation (missing/invalid
  `template`, `fields`), render-from-JSON without Excel, line break kept,
  table cells rendered. Full `pytest tests/ -q` green incl. fixtures.

## Done criteria

- `test_003_render_json.py` green + `test_json_fixtures.py` green.
- Full suite `pytest tests/ -q` green; merge `--no-ff` into `spec-003`.
