# AGENTS.md — stanok

## Commands
- Install: `uv sync`
- Run (dev): `python run.py` or `PYTHONPATH=src python -m stanok`
- Installed script: `.venv/Scripts/stanok` (after `uv sync`)
- Install git hooks: `scripts/install-hooks.bat` (pre-commit: trufflehog3 + pytest)
- Test (fast): `python -m pytest tests/ -q`
- Test (verbose): `python -m pytest tests/ -v`

## Stack
- Python 3.13 (`requires-python == 3.13.*`, pinned via `.python-version`, gitignored)
- Package: `src/stanok/` (`app.main` — entry logic, `__main__` — `python -m`)
- Entry: `run.py` in root (thin wrapper, also used by PyInstaller)
- GUI (planned): PyQt5 — implies GPL distribution, see License
- License: GPL-3.0-or-later (`LICENSE`, SPDX headers in source files)
- Testing: pytest (suite not yet written, `tests/` is empty)

## Structure
- `run.py` — dev/PyInstaller entry: puts `src/` on `sys.path`, calls `stanok.app:main`
- `src/stanok/__init__.py` — version + docstring only, no side effects on import
- `src/stanok/app.py` — application bootstrap (`main()`)
- `src/stanok/__main__.py` — `python -m stanok` support
- `specs/spec.md` — general spec: FR/NFR, C4, contracts (source of truth)
- `specs/SUMMARY.md` — spec workflow regulation (Active/Done)
- `CHANGELOG.md` — Keep a Changelog, `[Unreleased]` section
- `docs/` — design notes and decisions (empty for now)
- `tests/` — pytest suite (empty for now)

## Prohibitions (AI Must Never)
- Never Commit `.env` or any file with real credentials
- Never Use `print()` for logging — use Python `logging` module
- Every `except Exception as e` must log with the original level + `exc_info=True` in an f-string with cause-identifying context: `logger.warning/debug/error(f'<what+context>: {e}', exc_info=True)`; catch the specific expected error first, then the generic `Exception`, logging both
- Never Put executable logic or heavy imports (Qt) in `__init__.py` — bootstrap lives in `app.py`
- Never Skip tests before push once `tests/` exists
- Never Add new env var without updating `.env.example` (empty value)
- Never Hardcode Russian strings in UI code — keep them reviewable in one place
- Never Change license headers or `LICENSE` without explicit user approval

## Architecture Decisions
- Thin entry: `run.py` contains no logic, only `sys.path` setup + `main()` call
- Package import is side-effect free (`import stanok` must not start anything)
- Planned split: engine (pure Python, no Qt, testable in isolation) vs GUI (depends on engine, never vice versa)
- License is GPL-3.0-or-later: distributing the exe requires providing Corresponding Source (public GitHub repo satisfies this)

## Testing
- Test naming: `test_<module>_<scenario>_<expectation>`
- Every new engine feature → add test in `tests/`
- Bug fix → regression test
- GUI tests (when GUI lands): headless via `QT_QPA_PLATFORM=offscreen`
- Run fast loop: `pytest tests/ -q`

## Planning & Specs (specs/SUMMARY.md is the regulation)
- Feature specs live in `specs/NNN-slug/`: `spec.md` (what/why) + `plan.md` (how) + optional `tasks.md` (steps)
- Before coding: read `specs/spec.md` and `specs/SUMMARY.md`, pick next Active item
- After done: move spec to Done with one-sentence summary, update `CHANGELOG.md [Unreleased]`, put lasting knowledge into `docs/` + `AGENTS.md`

## Workflow
- Before working: `git pull`
- Branch naming: `feat/<short-desc>`, `fix/<issue-desc>`, `chore/<task>`
- Commit messages: short, imperative, Russian allowed (e.g., "Добавить батч-режим в форму заполнения")
- Push: `git push -u origin <branch-name>` after successful commit (or directly to `main` for solo trivial changes if user asks)
- Pre-commit hook runs automatically: trufflehog3 secrets scan (excludes `venv/`, `uv.lock`) + `pytest tests/ -q` when tests exist; never commit with `--no-verify` without asking
- Build exe (when GUI lands; `Станок.spec` is gitignored, not in repo): `pyinstaller --onefile --windowed --name stanok --paths src run.py`
- Open PR: one logical change per PR, link to spec item
- Squash merge to main after review
- Separate refactoring from features into different commits/branches

## User Interaction
- All user-facing messages: Russian (GUI, CLI output, logs)
- Code comments/docstrings: English preferred, Russian allowed
- This file, plans and specs: Russian allowed

## License
- GPL-3.0-or-later: `LICENSE` + SPDX headers (`Copyright (C) 2026 Kirill Borovoy`)
- GUI will use PyQt5 (GPL): exe distribution stays compliant via open sources
