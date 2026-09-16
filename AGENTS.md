# AGENTS.md — FirstAgent (docxforge)

## Commands
- Install: `uv sync` (needs network once for `uv lock`)
- Run GUI: `python run.py`
- Run CLI: `python cli.py --help`
- Test (fast): `python -m pytest tests/ -q`
- Test (verbose): `python -m pytest tests/ -v`
- Coverage: `python -m pytest --cov=docxforge.engine --cov-report=term-missing tests/`
- Smoke test: `python tests/smoke_engine.py`
- Install git hooks: `scripts/install-hooks.bat`

## Stack
- Python 3.8+
- Core: docxforge.engine (schema, parser, renderer, data_reader)
- GUI: PyQt5 (docxforge.gui)
- CLI: click (cli.py)
- Testing: pytest
- Pre-commit: pytest + trufflehog3 (auto on commit)

## Structure
- `src/docxforge/engine/` — core business logic (pure Python, no Qt)
- `src/docxforge/gui/` — PyQt5 desktop UI (depends on engine)
- `cli.py` — CLI adapter over engine
- `tests/` — pytest suite mirroring engine modules
- `scripts/` — automation (hook installer, pre-commit)

## Prohibitions (AI Must Never)
- Never Commit `.env` or any file with real credentials — blocked by pre-commit hook
- Never Use `print()` for logging — use Python `logging` module
- Never Modify `docxforge/gui/` without understanding Qt event loop — ask first
- Never Skip tests before push — pre-commit runs `pytest tests/ -q` automatically
- Never Add new env var without updating `.env.example` (empty value)
- Never Hardcode Russian strings

## Architecture Decisions
- Layered: CLI/GUI → engine (Dependency Inversion via imports)
- Engine is pure Python, zero external UI deps — testable in isolation
- GUI imports engine, never vice versa
- Schema (`engine/schema.py`) = single source of truth for .docxforge config
- Renderer uses XML-run merge (preserves formatting), not text replacement
- Nested project generation (Employee → Projects) lives in `generate.py`, details in `docs/nested-projects.md`

## Testing
- Unit tests in `tests/` mirroring `docxforge/engine/` modules
- Engine coverage target: 85%+ (currently ~86%)
- GUI: manual testing, QTest optional
- Every new engine feature → add test in `tests/`
- Bug fix → regression test
- Test naming: `test_<module>_<scenario>_<expectation>`
- Run fast loop: `pytest tests/ -q` (pre-commit does this)

## Planning & Specs (PLAN.md / SPEC.md)
- **PLAN.md** — high-level task list with checkboxes. One file per feature/epic.
- **SPEC.md** — detailed specification for a single task (requirements, acceptance criteria, edge cases).
- Before coding: read PLAN.md, pick next unchecked item, create SPEC.md for it.
- After implementation: update PLAN.md (check off), update SPEC.md if scope changed.
- Both files live in project root or `specs/` — commit them.

## Workflow
- Before working: `git pull`
- **Each plan item = new git branch**: `git checkout -b feat/<plan-item-slug>` before starting work
- Branch naming: `feat/<short-desc>`, `fix/<issue-desc>`, `chore/<task>`
- Commit messages: short, imperative, Russian allowed (e.g., "Добавить батч-режим в форму заполнения")
- Pre-commit hook runs automatically: `pytest tests/ -q` + `trufflehog3`
- If hook false-positive: ask user
- Push: `git push -u origin <branch-name>` after successful commit
- Open PR: one logical change per PR, link to PLAN.md item
- Squash merge to main after review
- Separate refactoring from features into different commits/branches

## User Interaction
- All user-facing messages: Russian (GUI, CLI output, logs)
- Code comments/docstrings: English preferred, Russian allowed
- `.docxforge` project files: JSON, contain runtime state (consider gitignore in user projects)

## Detailed Docs (read on demand)
- Design docs: `docs/ideas/`