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

## Data

Nothing is checked in: the page fetches everything from jsDelivr at
runtime.

- **Channel** — `?channel=dev` selects the force-pushed `assets-dev`
  branch; anything else (i.e. the default) selects the reviewed prod
  `assets` branch. A `dev assets` badge shows in the header on the dev
  channel so it can't be mistaken for prod.

- **Manifest** — fetched from the channel branch,
  `https://cdn.jsdelivr.net/gh/vupdivup/wubwub@<branch>/manifest.json`.
  This is the only path served off a moving branch ref, so it's the only
  one anything ever purges. A merged release therefore updates the live
  album list with no commit here.

- **Media** (`gif`, animated; `preview`, static first frame) — resolved
  against `manifest.version` when the manifest carries one, i.e. the
  immutable `assets-vN` tag that release was published as; dev manifests
  have no version and stay on the branch. That's what makes the copied
  embed snippets permanent.

## Behavior notes

- Grid cards show the static `preview`; hovering/focusing a card swaps
  in the animated `gif`. Only the last ~12 hovered cards keep an
  animated GIF loaded at a time, to bound memory at large catalog
  sizes.
- Search is fuzzy (Fuse.js) over artist + title, debounced, and
  mirrored to `?q=` so a search is linkable/shareable.
- Filtering hides/shows existing cards rather than re-rendering, so
  already-loaded images aren't refetched on every keystroke.
- The detail dialog's job is producing a copy-pasteable embed snippet
  (Markdown / HTML `<img>` / raw URL) pointed at the CDN GIF, for
  pasting into a GitHub README or similar.
