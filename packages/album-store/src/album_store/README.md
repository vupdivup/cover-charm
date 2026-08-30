# album-store

Fetch an album's cover art (via [`album-covers`](../../album-covers))
and persist it: the image goes to a MinIO/S3 bucket, the metadata plus
the object's URL goes to a Postgres row. One public operation for now:
upload an album by artist + title.

## Local services

`docker compose up -d` from the repo root starts Postgres, MinIO, and
pgweb (see `compose.yaml`, `.env.example`). Defaults assume that setup:

| var | default |
|---|---|
| `DATABASE_URL` | `postgresql://cover_art:cover_art@localhost:5432/cover_art` |
| `MINIO_ENDPOINT` | `http://localhost:9000` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` / `minioadmin` |
| `MINIO_BUCKET` | `covers` |
| `MINIO_PUBLIC_ENDPOINT` | falls back to `MINIO_ENDPOINT` |

`MINIO_PUBLIC_ENDPOINT` only needs setting when the URL boto3 talks to
(e.g. a container-internal host) differs from the URL whoever reads the
stored `cover_url` later should hit.

The bucket is created with an anonymous read policy so a stored
`cover_url` is a plain fetchable link -- fine for local dev, not for a
real deployment (front it with a CDN/presigned URLs instead).

## Inspecting local data

- **Postgres**: pgweb at http://localhost:8080 -- pre-wired to the
  `cover_art` DB via `PGWEB_DATABASE_URL`, no login form. Or `psql`
  straight into the container:
  `docker compose exec postgres psql -U cover_art -d cover_art -c 'select * from albums;'`
- **MinIO**: console at http://localhost:9001, login
  `minioadmin`/`minioadmin` -- browse the `covers` bucket.

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
```

`init` creates the `albums` table and the bucket if they don't exist
yet (the compose Postgres also runs `sql/init.sql` on first boot, so
`init` is mainly for a DB that wasn't bootstrapped that way). `upload`
prints the stored cover's URL on success.

Re-uploading the same artist+title (case-insensitive) overwrites the
existing object and row rather than creating a duplicate.

**Python API:**

```python
from album_store import upload_album

stored = upload_album("Kid A", artist="Radiohead")
print(stored.cover_url)
```

Exports: `Settings`, `StoredAlbum`, `upload_album`. Raises
`album_covers.CoverArtNotFound` if no matching album or cover exists.

## Logging

Same convention as `album-covers`: stdlib `logging` under the
`album_store` name, `NullHandler`ed by default. `-v`/`-vv`/`-q` on the
CLI; as a library, configure `logging` yourself and optionally
`logging.getLogger("album_store").setLevel(...)`.
