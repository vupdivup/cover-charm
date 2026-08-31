# album-store

Fetch an album's cover art (via [`album-covers`](../../album-covers)),
persist it, and optionally render it into a GIF (via
[`render`](../../render)) and persist that too. Two operations:

- upload an album by artist + title -- cover goes to the `covers`
  bucket, metadata + cover URL upserted into Postgres
- batch-render stored covers into GIFs through a Blender animation --
  GIFs go to a second `gifs` bucket, GIF URL recorded on the same row

## Local services

`docker compose up -d` from the repo root starts Postgres, MinIO, and
pgweb (see `compose.yaml`, `.env.example`). Defaults assume that setup:

| var | default |
|---|---|
| `DATABASE_URL` | `postgresql://cover_art:cover_art@localhost:5432/cover_art` |
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
  `cover_art` DB via `PGWEB_DATABASE_URL`, no login form. Or `psql`
  straight into the container:
  `docker compose exec postgres psql -U cover_art -d cover_art -c 'select * from albums;'`
- **MinIO**: console at http://localhost:9001, login
  `minioadmin`/`minioadmin` -- browse the `covers` and `gifs` buckets.

## Install

From within this directory:

```
uv sync
```

## Usage

**CLI:**

```
album-store init
album-store upload "In Rainbows" --artist "Radiohead"
album-store render --blend animation.blend --material CoverMat
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
[`render`](../../render) does). One album failing (bad material name,
missing cover object, a Blender error) is logged and skipped rather
than aborting the run; the command prints each rendered GIF's URL to
stdout and exits 1 if any album failed.

**Python API:**

```python
from album_store import upload_album, render_albums

stored = upload_album("Kid A", artist="Radiohead")
print(stored.cover_url)

outcomes, failures = render_albums(blend="animation.blend", material="CoverMat")
```

Exports: `Settings`, `StoredAlbum`, `upload_album`, `RenderOutcome`,
`render_albums`. `upload_album` raises `album_covers.CoverArtNotFound`
if no matching album or cover exists.

## Logging

Same convention as `album-covers`: stdlib `logging` under the
`album_store` name, `NullHandler`ed by default. `-v`/`-vv`/`-q` on the
CLI; as a library, configure `logging` yourself and optionally
`logging.getLogger("album_store").setLevel(...)`.
