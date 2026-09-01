# wubwub.studio

Fetch an album's cover art (via [`wubwub.covers`](../covers)),
persist it, and optionally render it into a GIF (via
[`wubwub.media`](../media)) and persist that too. Two operations:

- upload an album by artist + title -- cover goes to the `covers`
  bucket, metadata + cover URL upserted into Postgres
- batch-render stored covers into GIFs through a Blender animation --
  GIFs go to a second `gifs` bucket, GIF URL recorded on the same row.
  A static single-frame preview is rendered alongside each GIF (same
  Blender run, no extra render time) and stored under a `previews/`
  prefix in the same bucket, URL recorded on the same row too
- publish every rendered GIF + preview to a git branch, so they're
  servable over jsDelivr's free GitHub CDN for a public showcase site

## Local services

`docker compose up -d` from the repo root starts Postgres, MinIO, and
pgweb (see `compose.yaml`, `.env.example`). Defaults assume that setup:

| var | default |
|---|---|
| `DATABASE_URL` | `postgresql://wubwub:wubwub@localhost:5432/wubwub` |
| `MINIO_ENDPOINT` | `http://localhost:9000` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` / `minioadmin` |
| `MINIO_BUCKET` | `covers` |
| `MINIO_GIF_BUCKET` | `gifs` |
| `MINIO_PUBLIC_ENDPOINT` | falls back to `MINIO_ENDPOINT` |

`MINIO_PUBLIC_ENDPOINT` only needs setting when the URL boto3 talks to
(e.g. a container-internal host) differs from the URL whoever reads the
stored `cover_url`/`gif_url` later should hit.

Both buckets are created with an anonymous read policy so a stored
`cover_url`/`gif_url` is a plain fetchable link -- fine for local dev,
not for a real deployment (front it with a CDN/presigned URLs instead).

## Inspecting local data

- **Postgres**: pgweb at http://localhost:8080 -- pre-wired to the
  `wubwub` DB via `PGWEB_DATABASE_URL`, no login form. Or `psql`
  straight into the container:
  `docker compose exec postgres psql -U wubwub -d wubwub -c 'select * from albums;'`
- **MinIO**: console at http://localhost:9001, login
  `minioadmin`/`minioadmin` -- browse the `covers` and `gifs` buckets.

## Install

From the repo root:

```
uv sync
```

## Usage

**CLI:**

```
wubwub studio init
wubwub studio upload "In Rainbows" --artist "Radiohead"
wubwub studio render --blend animation.blend --material CoverMat
wubwub studio publish
```

`init` creates the `albums` table and both buckets if they don't exist
yet (the compose Postgres also runs `sql/init.sql` on first boot, so
`init` is mainly for a DB that wasn't bootstrapped that way). `upload`
prints the stored cover's URL on success.

Re-uploading the same artist+title (case-insensitive) overwrites the
existing object and row rather than creating a duplicate -- and never
touches an album's existing GIF.

`render` is a batch operation: by default it renders every album whose
`gif_key` is still `NULL` (i.e. newly uploaded albums), so re-running it
after more uploads only picks up the new ones. Pass `--all` to
re-render every album regardless -- there's no automatic detection of a
changed `.blend`, so `--all` is how you redo everything after editing
the animation. `--blend` and `--material` are required and have no
default or env var -- neither the `.blend` file nor the material name
to swap is something this package can discover on its own. Other flags:
`--fps` (default 24.0), `--limit N` (cap albums per run), `--blender`
(explicit Blender executable path, otherwise auto-detected the same way
[`wubwub.media`](../media) does). One album failing (bad material name,
missing cover object, a Blender error) is logged and skipped rather
than aborting the run; the command prints each rendered GIF's URL to
stdout and exits 1 if any album failed (the preview URL is logged, not
printed, to keep stdout a plain list of GIF URLs).

`publish` pulls every album with a rendered GIF back out of MinIO and
force-pushes them, plus a `manifest.json`, as a **single commit on an
orphan branch** (`--branch`, default `assets-dev`) of the current git
repo (`--remote`, default `origin`) -- run from within the repo (or a
worktree of it). The pushed tree mirrors the GIF/preview object keys
exactly:

```
manifest.json
gifs/<artist-slug>/<title-slug>.gif
previews/<artist-slug>/<title-slug>.gif
```

jsDelivr then serves the branch straight off GitHub, no deploy step:
`https://cdn.jsdelivr.net/gh/<owner>/<repo>@<branch>/gifs/...`. Being
an orphan branch, it carries no history and no `.gitignore`, so the
committed GIFs bypass this repo's root `*.gif` ignore rule entirely.
Every publish rewrites the branch from scratch (a fresh orphan, not an
update), so it never accumulates blob history across runs, and the
push is a plain `--force` -- the branch is wholly machine-generated
and disposable. After pushing, `publish` best-effort purges the pushed
paths from jsDelivr's cache (which otherwise holds a branch ref for up
to 12h) via `https://purge.jsdelivr.net/`; a purge failure only logs a
warning, since the assets are already live at origin either way.
`--dry-run` writes the same tree to `-o`/`--output` (a temp dir if
unset) and skips git and the purge entirely, e.g. to preview what
would be published or to feed a local dev server directly off disk.
There's only one channel today (`assets-dev`) -- no PR, no review, no
tags; a reviewed/tagged "prod" channel is a natural later addition
once there's a production site whose releases need pinning.

`site/` (repo root) is that showcase page: one `BASE` constant in
`site/app.js`, media rendered as `${BASE}/${album.gif}` /
`${BASE}/${album.preview}`:

```js
BASE = 'https://cdn.jsdelivr.net/gh/vupdivup/wubwub@assets-dev'
```

jsDelivr sends `Access-Control-Allow-Origin: *`, so a `localhost` site
can fetch this with no proxy. `site/` reads `manifest.json` from a
checked-in local copy (`site/data/manifest.json`) rather than fetching
it from jsDelivr, since publishing that copy from `publish_assets` is
not wired up yet — see `site/README.md` for the manual refresh
command.

**Python API:**

```python
from wubwub.studio import upload_album, render_albums, publish_assets

stored = upload_album("Kid A", artist="Radiohead")
print(stored.cover_url)

outcomes, failures = render_albums(blend="animation.blend", material="CoverMat")

result = publish_assets()
print(result.base_url)
```

Exports: `Settings`, `StoredAlbum`, `upload_album`, `RenderOutcome`,
`render_albums`, `PublishResult`, `publish_assets`. `upload_album`
raises `wubwub.covers.CoverArtNotFound` if no matching album or cover
exists; `publish_assets` raises `PublishError` for a git failure and
`ValueError` if there's nothing to publish.

## Logging

Same convention as `wubwub.covers`: stdlib `logging` under the
`wubwub.studio` name, `NullHandler`ed by default. `-v`/`-vv`/`-q` on the
CLI; as a library, configure `logging` yourself and optionally
`logging.getLogger("wubwub.studio").setLevel(...)`.
