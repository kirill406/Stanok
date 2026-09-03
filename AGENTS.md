# Repository Guidelines

## Project Structure & Module Organization

```
FirstAgent/
├── scripts/
│   ├── pre-commit.hook      # Git pre-commit hook (trufflehog3 scanner)
│   └── install-hooks.bat    # One-shot hook installer for Windows
├── .env.example             # Template of required environment variables
├── .env                     # Real secrets (git-ignored, never committed)
├── .gitignore               # Exclusion rules for secrets, artifacts, IDE files
└── README.md                # Setup and secrets-management guide
```

- **`scripts/`** — shell automation: hook installation and pre-commit checks.
- **`.env.example`** — declares every variable the project expects; keep values **empty**.
- **`.env`** — your local copy with real credentials; listed in `.gitignore`.

## Build, Test, and Development Commands

| Command | Purpose |
|---|---|
| `scripts/install-hooks.bat` | Copies `pre-commit.hook` into `.git/hooks/` after clone |
| `trufflehog3 --no-history --no-entropy .` | Manually scan the working tree for secrets |
| `git commit --no-verify` | Bypass the pre-commit hook (only when false-positive) |

No build step is required — this project is configuration-driven.

## Coding Style & Naming Conventions

- **Environment variables**: `UPPER_SNAKE_CASE` (`OPENAI_API_KEY`, `DB_HOST`).
- **Shell scripts**: POSIX-compatible `#!/bin/sh`; use `echo` for user messages.
- **Batch scripts**: Windows `.bat` with `@echo off` and absolute-safe `%~dp0` paths.
- **Indentation**: spaces (no tabs) in shell scripts and Markdown files.
- Keep files UTF-8 encoded to preserve non-ASCII characters.

## Testing Guidelines

No automated test suite exists yet. The primary safety check is the **pre-commit hook**:

- Every commit triggers `trufflehog3`, which blocks the commit if a secret (API key, token, password) is detected.
- Install the hook once after cloning: run `scripts/install-hooks.bat` (Windows) or `cp scripts/pre-commit.hook .git/hooks/pre-commit` (Unix).

## Commit & Pull Request Guidelines

- **Commit messages** are short and descriptive (e.g., `Add README with secrets management guide`).
- No strict conventional-commit format is enforced; prefer the imperative mood and keep the first line under 72 characters.
- Pull requests must **not** include `.env` or any file containing real credentials. If `trufflehog3` flags a secret, remove it before pushing.

## Security & Configuration Tips

1. **Never commit `.env`.** It is blocked by `.gitignore` and the pre-commit hook.
2. When adding a new secret variable:
   - Add it with the real value to your local `.env`.
   - Add it with an **empty** value to `.env.example` so others know it exists.
   - Read it in code via `os.getenv("VAR_NAME")` or `process.env.VAR_NAME`.
3. If the hook flags a false positive, use `git commit --no-verify` and consider adding a `.trufflehog3.yml` exclusion rule.