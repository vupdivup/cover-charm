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
  servable over jsDelivr's free GitHub CDN for a public showcase site --
  either to the throwaway dev channel (`serve --dev`) or as a reviewed,
  tagged prod release (`deploy`)

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
wubwub studio serve --dev
wubwub studio deploy
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
[`wubwub.media`](../media) does), `--colors` (GIF palette size, default
128 -- lower is smaller) and `--dither` (dither the palette mapping;
off by default). One album failing (bad material name,
missing cover object, a Blender error) is logged and skipped rather
than aborting the run; the command prints each rendered GIF's URL to
stdout and exits 1 if any album failed (the preview URL is logged, not
printed, to keep stdout a plain list of GIF URLs).

### Asset channels

Both channels publish the same tree, pulled from MinIO and mirroring
the GIF/preview object keys exactly:

```
manifest.json
gifs/<artist-slug>/<title-slug>.gif
previews/<artist-slug>/<title-slug>.gif
```

jsDelivr serves either channel straight off GitHub, no deploy step:
`https://cdn.jsdelivr.net/gh/<owner>/<repo>@<ref>/gifs/...`. Both
branches carry no `.gitignore`, so the committed GIFs bypass this
repo's root `*.gif` ignore rule entirely. All git work happens in a
throwaway worktree under a temp dir, so publishing never disturbs your
checkout -- but it does need to run from inside the repo (or a worktree
of it).

**dev -- `assets-dev`, no review.** `wubwub studio serve --dev` first
force-pushes the tree as a **single commit on a fresh orphan branch**
(`--branch`, default `assets-dev`; `--remote`, default `origin`), so the
branch never accumulates blob history and is always exactly one commit.
Plain `--force`: it's wholly machine-generated and disposable. Every
pushed path is then best-effort purged from jsDelivr's cache (which
otherwise holds a branch ref for up to 12h); a purge failure only logs
a warning, the assets are live at origin either way. `--no-publish`
serves the channel without re-pushing.

**prod -- `assets`, reviewed and tagged.** `wubwub studio deploy` picks
the next version (`assets-vN`, one past the highest tag on the remote),
stamps it into the manifest as `"version"`, commits the tree on
`release/assets-vN` off the current `assets` tip, pushes it (no force --
this branch is reviewed) and opens a PR with a summary of the albums
added/removed versus what's live.

Merging the PR is the release: a tag is only ever cut by a push to
`assets` itself, so `.github/workflows/tag-assets.yml` (carried in the
release tree, since a `push` workflow runs from the pushed branch's own
copy) then creates the `assets-vN` tag the merged manifest names and
purges the one path served off the moving branch, `manifest.json`.
Abandoning a PR therefore costs nothing: no tag was cut, and the next
`deploy` computes the same version again -- it counts tags, not
branches. It does sidestep a leftover `release/assets-vN` branch with a
timestamp suffix rather than force-pushing it, so delete abandoned ones. Nothing else needs purging, because the site
reads the manifest from `@assets` but every media URL from
`@assets-vN`, which is immutable. If `assets` doesn't exist yet, the
first release is pushed straight onto it (there's no base to open a PR
against) and logged as such. Flags: `--dry-run` + `-o`/`--output` write
the tree locally and touch neither git nor `gh`; `--no-pr` pushes the
release branch and leaves the PR to you; `--limit N` caps the album
count. The prod branch, unlike dev, keeps blob history -- a PR needs a
shared ancestor with its base.

Repo rulesets back this up: `master` and `assets` both require a PR and
block force-pushes and deletion, and `assets-v*` tags are immutable
(no update, no delete). `assets-dev` is deliberately left unprotected --
force-pushing it is the whole point.

`site/` (repo root) is the showcase page both channels feed. It picks
its channel at runtime from `?channel=dev` (default prod), fetches
`<channel branch>/manifest.json` from jsDelivr -- which sends
`Access-Control-Allow-Origin: *`, so a `localhost` page needs no proxy
-- and then renders media against `manifest.version` when present. So a
merged release updates the live site with no second commit, and copied
embed snippets are permanently pinned tag URLs.

**Python API:**

```python
from wubwub.studio import upload_album, render_albums, publish_assets, deploy_assets

stored = upload_album("Kid A", artist="Radiohead")
print(stored.cover_url)

outcomes, failures = render_albums(blend="animation.blend", material="CoverMat")

result = publish_assets()          # dev channel
print(result.base_url)

release = deploy_assets()          # prod channel; None if nothing changed
print(release.pr_url)
```

Exports: `Settings`, `StoredAlbum`, `upload_album`, `RenderOutcome`,
`render_albums`, `PublishResult`, `publish_assets`, `DeployResult`,
`deploy_assets`, `serve_site`. `upload_album` raises
`wubwub.covers.CoverArtNotFound` if no matching album or cover exists;
`publish_assets` raises `PublishError` for a git failure and
`ValueError` if there's nothing to publish. `deploy_assets` raises
`DeployError` (a `PublishError`) for a git/`gh` failure and returns
`None` when the built tree already matches what's released.

## Logging

Same convention as `wubwub.covers`: stdlib `logging` under the
`wubwub.studio` name, `NullHandler`ed by default. `-v`/`-vv`/`-q` on the
CLI; as a library, configure `logging` yourself and optionally
`logging.getLogger("wubwub.studio").setLevel(...)`.
