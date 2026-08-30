# CLAUDE.md

## Assistant behavior

Always use the `caveman` skill (ultra-compressed communication mode)
for all responses in this repo.

## Overview

`cover-art` fetches album cover art from iTunes, normalizes it to a
square, and uploads it to Cloudflare R2. `fetch`, `normalize`, and
`upload` are independent modules; `pipeline` composes them; `cli` is
the entry point. See `src/cover_art/README.md` for full usage.

## Environment & dependencies

Use `uv` for everything — `uv sync`, `uv add`/`uv remove`, `uv run`.
Don't use pip or hand-edit the venv. Dependency changes go through
`uv add`/`uv remove` so `pyproject.toml` and `uv.lock` stay in sync.

## Code style & documentation

Document business logic, changes to it, and architectural decisions
in-code (docstring or a short comment at the decision site) — briefly,
covering the *why*, not a restatement of the code. Match the style of
the surrounding code.

## Testing & verification

No automated test suite yet. Verify changes by running the CLI
(`uv run cover-art ...`). Add the test command here once a suite exists.

## Git & commits

Only commit (or push, branch, rebase, etc.) when the user explicitly
asks. Never commit `.env` or other files holding secrets.

## Configuration & secrets

R2 credentials/bucket are read from environment variables only —
`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET` — never passed as flags or committed to the repo.

## External services

- **iTunes Search API** — uncredentialed, rate-limited (~20 req/min).
  Throttle/retry knobs live in `src/cover_art/fetch.py`
  (`SEARCH_INTERVAL`, `MAX_RETRIES`, `INITIAL_BACKOFF`).
- **Cloudflare R2** — reached via its S3-compatible endpoint
  (`region_name="auto"`), configured in `src/cover_art/upload.py`.
