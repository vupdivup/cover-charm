# CLAUDE.md

## Assistant behavior

Always use the `caveman` skill (ultra-compressed communication mode)
for all responses in this repo.

## Overview

This is a `uv` workspace with two packages:

- `album-covers` (`packages/album-covers/`) fetches album cover art
  via MusicBrainz + Cover Art Archive. See
  `packages/album-covers/src/album_covers/README.md` for full usage.
- `render` (`packages/render/`) swaps an image into a Blender
  animation's texture, renders it, and assembles the frames into a
  GIF. See `packages/render/src/render/README.md` for full usage.

`album-covers` and `render` are `uv` workspace members under
`packages/`, each with its own `pyproject.toml`. The root
`pyproject.toml` is a workspace-only root (`package = false`), no
source of its own. Each package has its own `cli.py` entry point and
its own Python API; how the modules inside a package are split up is
a per-package call, not a fixed convention to enforce across the
workspace.

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

## External services

- **MusicBrainz + Cover Art Archive** — uncredentialed, rate-limited
  (~1 req/sec, shared across both since Cover Art Archive is keyed by
  MusicBrainz's MBIDs); requires a descriptive `User-Agent`. Throttle/
  retry knobs live in `packages/album-covers/src/album_covers/fetch.py`
  (`SEARCH_INTERVAL`, `MAX_RETRIES`, `INITIAL_BACKOFF`). Fuzzy-match
  threshold for accepting a result is `MATCH_THRESHOLD` in same file.
- **Blender** — a local install, driven as a subprocess in background
  mode (`--background`) by `packages/render/src/render/blender.py`,
  not imported as the `bpy` package. Auto-detected via `PATH` and the
  default per-platform install directories, or point at it explicitly
  with `--blender`/`BLENDER`. Works from WSL against a Windows-side
  install — paths are translated with `wslpath` only in that case;
  native Windows and native Linux/macOS paths pass through unchanged.
