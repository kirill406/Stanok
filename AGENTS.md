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

## Versioning (Semantic Versioning 2.0.0, https://semver.org/)
- Format `MAJOR.MINOR.PATCH`: MAJOR — incompatible changes, MINOR — backwards-compatible features, PATCH — bug fixes
- `0.y.z` (current `0.0.0`): anything may change without MINOR/MAJOR bump discipline; `1.0.0` marks first stable API/GUI contract
- Single source of truth: `pyproject.toml` version only; `src/stanok/__init__.py` reads it from installed metadata (`importlib.metadata`), no manual sync — bump the version in `pyproject.toml` alone
- Pre-releases as `1.0.0-alpha`, `-beta`, `-rc.1` when testing exe with users before stable
- Release flow: move `CHANGELOG.md [Unreleased]` entries under new version header with date, bump version in both places, tag `git tag vX.Y.Z`, push tag
- Never Bump version in feature branches — only in release commits on `main`

### Development stages (current: Pre-alpha, `0.1.0`)
- Planning — name reserved, scope outlined; usually no version yet
- Pre-alpha — working sketch; architecture may change anytime; `0.x.y`
- Alpha — architecture settled; inner circle can use it; testing toward product
- Beta — feature-complete; bugfixing, performance, ergonomics
- Production/stable — no critical bugs, main scenarios tested; gets `1.0`

## Prohibitions (AI Must Never)
- Never Commit `.env` or any file with real credentials
- Never Use `print()` for logging — use Python `logging` module
- Every `except Exception as e` must log with the original level + `exc_info=True` in an f-string 
  with cause-identifying context: `logger.warning/debug/error(f'<what+context>: {e}', exc_info=True)`;
  catch the specific expected error first, then the generic `Exception`, logging both
- Never Put executable logic or heavy imports (Qt) in `__init__.py` — bootstrap lives in `app.py`
- Never Skip tests before push once `tests/` exists
- Never Add new env var without updating `.env.example` (empty value)
- Never Hardcode Russian strings in UI code — keep them reviewable in one place
- Never Change license headers or `LICENSE` without explicit user approval
- Never Delete branches (local `git branch -D` or remote `git push --delete`) without explicit user approval — merged feature branches stay

## Architecture Decisions (details: [docs/architecture.md](docs/architecture.md) — single source of truth)
- Thin entry: `run.py` contains no logic, only `sys.path` setup + `main()` call
- Package import is side-effect free (`import stanok` must not start anything)
- Layers: gui → services → engine (never vice versa, never sideways); one filling mechanism (Filling JSON → docx)
- Prefer graphics over prose for structures: mermaid diagrams for layers, flows and data pipelines in docs/specs; 
  keep diagrams next to the text they explain
- License is GPL-3.0-or-later:
  distributing the exe requires providing Corresponding Source (public GitHub repo satisfies this)

## Testing
- Test naming: `test_<module>_<scenario>_<expectation>`
- Every new engine feature → add test in `tests/`
- Bug fix → regression test
- GUI tests (when GUI lands): headless via `QT_QPA_PLATFORM=offscreen`
- Run fast loop: `pytest tests/ -q`

## Planning & Specs (specs/SUMMARY.md is the regulation)
- Feature specs live in `specs/NNN-slug/`: `spec.md` (what/why) + `plan.md` (how) + optional `tasks.md` (steps)
- Before coding: read `specs/spec.md` and `specs/SUMMARY.md`, pick next Active item
- After done: move spec to Done with one-sentence summary, update `CHANGELOG.md [Unreleased]`, 
  put lasting knowledge into `docs/` + `AGENTS.md`

## Workflow
- Before working: `git pull`
- Branch naming: `feat/<short-desc>`, `hotfix/<issue-desc>`, `release/<release-num>`
- Branching model: simplified git-flow (https://nvie.com/posts/a-successful-git-branching-model/): `main` is always releasable, work happens in short-lived branches, merge via squash after review
  - `main` — releases only (tagged `vX.Y.Z`, version bumped); never commit directly
  - `develop` — integration branch; `feat/*` and `fix/*` branch off it and merge back via squash after review
  - `release/*` — stabilization before tagging to `main`; `hotfix/*` — urgent fixes to `main`, then merged back into `develop`
- Commit messages: short, imperative, Russian allowed
- Push: `git push -u origin <branch-name>` after successful commit
  (or directly to `main` for solo trivial changes if user asks)
- Pre-commit hook runs automatically: 
  trufflehog3 secrets scan (excludes `venv/`, `uv.lock`) + `pytest tests/ -q` when tests exist;
  never commit with `--no-verify` without asking
- Build exe (when GUI lands; `Станок.spec` is gitignored, not in repo): 
  `pyinstaller --onefile --windowed --name Станок --paths src run.py`
- Open PR: one logical change per PR, link to spec item
- Squash merge to main after review
- Separate refactoring from features into different commits/branches
- **After feature implementation: check docs/ and README.md for consistency with changes; update if needed**

## User Interaction
- All user-facing messages: Russian (GUI, logs)
- Code comments/docstrings: English preferred, Russian allowed
- This file, plans and specs: Russian allowed
- Docs in ASD-STE100: short sentences, approved meanings, imperative for steps

## License
- GPL-3.0-or-later: `LICENSE` + SPDX headers (`Copyright (C) 2026 Kirill Borovoy`)
- GUI will use PyQt5 (GPL): exe distribution stays compliant via open sources
