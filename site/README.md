# site

Static showcase gallery for rendered album covers, per the contract
described in `src/wubwub/studio/README.md`. Plain
HTML/CSS/JS, no build step, one runtime dependency (Fuse.js) loaded as
an ES module straight from jsDelivr.

## Run

```
wubwub studio serve            # prod assets, exactly what visitors see
wubwub studio serve --dev      # push current assets to assets-dev, then serve them
```

Both print the URL to open (`--dev` adds `?channel=dev`). Plain
`python -m http.server 8000 -d site` works too — the page is fully
static — but must be served over HTTP(S), since `app.js` is an ES
module and fetches the manifest, both blocked under `file://`.

## Hosting

`.github/workflows/pages.yml` publishes this directory to GitHub Pages
on any push to `master` that touches `site/`, or on demand via the
Actions tab (`workflow_dispatch`). It uploads `site/` as a Pages
artifact rather than pointing Pages at a branch, since branch-based
Pages can only serve the repo root or `/docs`. Requires Pages' source
set to "GitHub Actions" once, in repo settings.

Asset releases need no run here: the album list is fetched from the CDN
at runtime, so merging an `assets` PR updates the live page on its own.

## Data

Nothing is checked in: the page fetches everything from jsDelivr at
runtime.

- **Channel** — `?channel=dev` selects the force-pushed `assets-dev`
  branch; anything else (i.e. the default) selects the reviewed prod
  `assets` branch. The page looks identical either way — the query
  param is the only tell.

- **Manifest** — fetched from the channel branch,
  `https://cdn.jsdelivr.net/gh/vupdivup/wubwub@<branch>/manifest.json`.
  This is the only path served off a moving branch ref, so it's the only
  one anything ever purges — and the only one fetched with
  `cache: "no-cache"`, since jsDelivr gives browsers a week-long copy
  that no purge can reach. A merged release therefore updates the live
  album list with no commit here, for returning visitors too.

- **Media** (`gif`, animated; `preview`, static first frame) — resolved
  against `manifest.version` when the manifest carries one, i.e. the
  immutable `assets-vN` tag that release was published as; dev manifests
  have no version and stay on the branch. That's what makes the copied
  embed snippets permanent.

## Behavior notes

- Grid cards show the static `preview`; hovering or keyboard-focusing a
  card swaps in the animated `gif`. Only the last ~12 such cards keep an
  animated GIF loaded at a time, to bound memory at large catalog
  sizes.
- In-grid preview is for pointing devices and the keyboard only. Touch
  has no hover state to end the preview with, so a tap opens the detail
  panel instead, which plays the same GIF larger alongside the snippet
  and download.
- Search is fuzzy (Fuse.js) over artist + title, debounced, and
  mirrored to `?q=` so a search is linkable/shareable.
- Filtering hides/shows existing cards rather than re-rendering, so
  already-loaded images aren't refetched on every keystroke.
- The detail dialog's job is producing a copy-pasteable embed snippet
  (Markdown / HTML `<img>` / raw URL) pointed at the CDN GIF, for
  pasting into a GitHub README or similar.
