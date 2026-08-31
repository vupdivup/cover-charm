# CLAUDE.md

## Assistant behavior

Always use the `caveman` skill (ultra-compressed communication mode)
for all responses in this repo.

Do not react or comment on shell mode commands (`!`-prefixed) run by
the user unless asked to.

## Overview

This is a `uv` workspace with two packages:

- `album-covers` (`packages/album-covers/`) fetches album cover art
  via MusicBrainz + Cover Art Archive. See
  `packages/album-covers/src/album_covers/README.md` for full usage.
- `render` (`packages/render/`) swaps an image into a Blender
  animation's texture, renders it, and assembles the frames into a
  GIF. See `packages/render/src/render/README.md` for full usage.
- `album-store` (`packages/album-store/`) fetches a cover via
  `album-covers` and persists it: image to MinIO/S3, metadata + object
  URL to Postgres. It can also `publish` rendered GIFs by force-pushing
  them to the `assets-dev` git branch, served over jsDelivr for the
  `site/` showcase. See
  `packages/album-store/src/album_store/README.md` for full usage.
- `site/` is a static, no-build showcase page (plain HTML/CSS/JS, not
  a `uv` workspace member) that browses `assets-dev` GIFs from a
  checked-in copy of the manifest at `site/data/manifest.json`. See
  `site/README.md`.

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

## Logging

Every package can be driven both as a CLI and as a library by another
package in this workspace (e.g. `album-covers` from a future caller in
`render` or `album_seed`), so logging follows the standard stdlib
`logging` library/application split:

- **Library modules only emit.** Each module gets
  `logger = logging.getLogger(__name__)` and calls
  `logger.debug/info/warning/error` — never `print`, never configures
  handlers, never calls `logging.basicConfig`. Use lazy `%s` formatting
  (`logger.info("...%s", x)`, not f-strings) so unemitted records cost
  nothing in hot/bulk loops.
- **Each package's `__init__.py` attaches a `logging.NullHandler()`** to
  its top-level logger, so importing the package is silent and doesn't
  trigger the stdlib's "no handlers found" warning when the host hasn't
  configured logging.
- **Only a `cli.py` configures handlers**, via `logging.basicConfig` on
  `sys.stderr`, gated by `-v/--verbose` (repeatable: info, then debug)
  and `-q/--quiet` flags. stdout stays reserved for the CLI's machine
  output (a URL, a written path, JSON); stderr carries both today's
  error messages and the new log stream.
- **A caller package needs nothing extra**: configuring `logging` once in
  its own entry point picks up every dependency package's records for
  free, and `logging.getLogger("<dep_package>").setLevel(...)` tunes just
  one of them.
- Level guide: DEBUG for per-request detail (queries, scores, byte
  counts), INFO for one line per successful/skipped unit of work,
  WARNING for retried/degraded paths, ERROR only for something the
  caller must handle. See `packages/album-covers/src/album_covers/fetch.py`
  and `cli.py` for a worked example.

## Testing & verification

No automated test suite yet. Verify changes by running the CLI
(`uv run album-covers ...`). Add the test command here once a suite exists.

## Git & commits

Only commit (or push, branch, rebase, etc.) when the user explicitly
asks. Never commit `.env` or other files holding secrets.

**NEVER push unless the user explicitly asks for a push, in that
specific turn.** A prior "commit pls" / "commit this too" does NOT
imply push, and push permission does NOT carry over to later commits
in the same session — ask again, or wait, each time. Committing does
not require push to "complete" the task; stop after the commit and
report it, don't chain a push onto it on your own judgment.

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
- **Postgres + MinIO** — local only, via `docker compose up -d` (repo
  root `compose.yaml`; copy `.env.example` to `.env` to override
  defaults). Postgres holds the `albums` table (schema in
  `sql/init.sql`, mirrored in
  `packages/album-store/src/album_store/schema.sql`); MinIO is the
  S3-compatible object store, accessed with boto3, split across two
  buckets: `covers` (album art) and `gifs` (rendered via `render`).
  Config env vars (`DATABASE_URL`, `MINIO_ENDPOINT`,
  `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`, `MINIO_BUCKET`,
  `MINIO_GIF_BUCKET`, `MINIO_PUBLIC_ENDPOINT`) are read in
  `packages/album-store/src/album_store/config.py`.
