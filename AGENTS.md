# Repository Guidelines

## Project Structure & Module Organization

`
FirstAgent/
├── docxforge/
│   ├── engine/
│   │   ├── schema.py           # Project config model (JSON .docxforge files)
│   │   ├── template_parser.py  # Scans .docx for {{ }} placeholders
│   │   ├── renderer.py         # Core rendering: XML-run merge, substitution, cycles
│   │   ├── data_reader.py      # Reads Excel (.xlsx) data into list-of-dicts
│   │   └── __init__.py
│   └── gui/
│       ├── main_window.py      # App entry: create/open project, recent list
│       ├── project_window.py   # Template tree, data list, open fill form
│       ├── fill_form.py        # Field mapping form, batch config, autosave
│       ├── field_dialog.py     # "Add field" template picker dialog
│       └── __init__.py
├── tests/                      # pytest suite (104 tests)
├── scripts/
│   ├── pre-commit.hook         # Git hook: pytest + trufflehog3
│   └── install-hooks.bat       # One-shot hook installer for Windows
├── prototype/                  # XML-run merge prototype & test scripts
├── docs/ideas/                 # Design docs, DSL specs, user test results
├── cli.py                      # CLI: create/scan/configure/render/list/info
├── run.py                      # GUI entry point
├── test_engine.py              # Quick end-to-end engine smoke test
├── requirements.txt             # Python dependencies
├── .env.example                # Template of required environment variables
├── .env                        # Real secrets (git-ignored, never committed)
├── .gitignore                  # Exclusion rules
└── README.md                   # Setup and usage guide
`

- **docxforge/engine/** — core business logic: schema, parsing, rendering, data reading.
- **docxforge/gui/** — PyQt5 desktop UI: project management, field mapping, generation.
- **cli.py** — command-line interface for all project operations.
- **    ests/** — 104 pytest tests covering engine + CLI (~86% engine coverage).
- **scripts/** — shell automation: hook installation and pre-commit checks.
- **.env.example** — declares every variable the project expects; keep values **empty**.
- **.env** — your local copy with real credentials; listed in .gitignore.

## Build, Test, and Development Commands

| Command | Purpose |
|---|---|
| pip install -r requirements.txt | Install dependencies |
| python run.py | Launch GUI application |
| python cli.py create PROJECT_DIR | Create a new project via CLI |
| python cli.py render PROJECT_DIR TEMPLATE | Render a template via CLI |
| python -m pytest tests/ -q | Run all tests (fast) |
| python -m pytest tests/ -v | Run all tests (verbose) |
| python -m pytest --cov=docxforge.engine --cov-report=term-missing tests/ | Coverage report |
| python test_engine.py | Quick end-to-end smoke test |
| scripts/install-hooks.bat | Copies pre-commit.hook into .git/hooks/ |
|     rufflehog3 --no-history --no-entropy . | Manually scan for secrets |
| git commit --no-verify | Bypass the pre-commit hook (only when false-positive) |

## Coding Style & Naming Conventions

- **Language**: Python 3.8+. Source files use UTF-8 with BOM (# -*- coding: utf-8 -*-).
- **Environment variables**: UPPER_SNAKE_CASE (OPENAI_API_KEY, DB_HOST).
- **Imports**: standard library first, then third-party, then local. One import per line.
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE for constants.
- **Dataclasses**: use @dataclass for model objects (schema.py). Prefer str, Enum for enum types.
- **Type hints**: use     yping (Dict, List, Optional) for public APIs.
- **Shell scripts**: POSIX-compatible #!/bin/sh; use echo for user messages.
- **Batch scripts**: Windows .bat with @echo off and absolute-safe %~dp0 paths.
- **Indentation**: 4 spaces (no tabs) in Python; spaces in shell scripts and Markdown.
- **String literals**: Russian text is inline (no i18n framework). User-facing messages in Russian.
- Keep files UTF-8 encoded to preserve non-ASCII characters.

## Testing Guidelines

- **104 pytest tests** in     ests/ covering engine modules and CLI.
- Engine coverage: ~86% (schema 97%, template_parser 97%, data_reader 92%, renderer 81%).
- GUI code (5-7% coverage) requires manual testing or QTest.
- Pre-commit hook runs python -m pytest tests/ -q +     rufflehog3 on every commit.
- When adding engine features, add tests in     ests/ with descriptive names.
- Test files:     est_additional.py,     est_batch.py,     est_batch_modes.py,     est_cli.py,     est_coverage.py,     est_renderer.py,     est_single_row_selection.py.

## Commit & Pull Request Guidelines

- **Commit messages** are short and descriptive (e.g., Add batch mode configuration to fill form).
- No strict conventional-commit format is enforced; prefer the imperative mood and keep the first line under 72 characters.
- Pull requests must **not** include .env or any file containing real credentials. If     rufflehog3 flags a secret, remove it before pushing.
- Separate refactoring from feature work into different commits.

## Security & Configuration Tips

1. **Never commit .env.** It is blocked by .gitignore and the pre-commit hook.
2. When adding a new secret variable:
   - Add it with the real value to your local .env.
   - Add it with an **empty** value to .env.example so others know it exists.
   - Read it in code via os.getenv("VAR_NAME") or process.env.VAR_NAME.
3. If the hook flags a false positive, use git commit --no-verify and consider adding a .trufflehog3.yml exclusion rule.
4. The .docxforge project file contains no secrets but does contain runtime resume state — consider gitignoring it in user projects.
