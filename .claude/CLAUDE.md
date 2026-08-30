# CLAUDE.md

## Assistant behavior

Always use the `caveman` skill (ultra-compressed communication mode)
for all responses in this repo.

## Overview

This is a `uv` workspace with three packages:

- `album_seed` (`src/album_seed/`) downloads a Kaggle album-ratings
  dataset and exports the top albums by popularity in the shape
  `album_covers` expects — source-agnostic; the dataset slug is a
  tunable, currently defaulting to AlbumOfTheYear's top-5000. See
  `src/album_seed/README.md` for full usage.
- `album-covers` (`packages/album-covers/`) fetches album cover art
  from iTunes. See `packages/album-covers/src/album_covers/README.md`
  for full usage.
- `render` (`packages/render/`) swaps an image into a Blender
  animation's texture, renders it, and assembles the frames into a
  GIF. See `packages/render/src/render/README.md` for full usage.

`album_seed` lives under `src/` and is the root package;
`album-covers` and `render` are separate `uv` workspace members under
`packages/`, each with its own `pyproject.toml`. Each package has its
own `cli.py` entry point and its own Python API; how the modules
inside a package are split up is a per-package call, not a fixed
convention to enforce across the workspace.

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
(`uv run album-covers ...`). Add the test command here once a suite exists.

## Git & commits

Only commit (or push, branch, rebase, etc.) when the user explicitly
asks. Never commit `.env` or other files holding secrets.

## Configuration & secrets

Kaggle credentials, same rule: `KAGGLE_API_TOKEN` (or the legacy
`KAGGLE_USERNAME`/`KAGGLE_KEY` pair) as environment variables only —
never a flag, never a `~/.kaggle/*` credentials file.

## External services

- **iTunes Search API** — uncredentialed, rate-limited (~20 req/min).
  Throttle/retry knobs live in
  `packages/album-covers/src/album_covers/fetch.py`
  (`SEARCH_INTERVAL`, `MAX_RETRIES`, `INITIAL_BACKOFF`). Fuzzy-match
  threshold for accepting a result is `MATCH_THRESHOLD` in same file.
- **Kaggle** — accessed via `kagglehub`. Auth from `KAGGLE_API_TOKEN`
  (current single-token scheme) or `KAGGLE_USERNAME`/`KAGGLE_KEY`
  (legacy) env vars — never a flag, never a credentials file. Dataset
  slug is `DATASET` in `src/album_seed/download.py`.
- **Blender** — a local install, driven as a subprocess in background
  mode (`--background`) by `packages/render/src/render/blender.py`,
  not imported as the `bpy` package. Auto-detected via `PATH` and the
  default per-platform install directories, or point at it explicitly
  with `--blender`/`BLENDER`. Works from WSL against a Windows-side
  install — paths are translated with `wslpath` only in that case;
  native Windows and native Linux/macOS paths pass through unchanged.
