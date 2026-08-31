# site

Static showcase gallery for rendered album covers, per the contract
described in `packages/album-store/src/album_store/README.md`. Plain
HTML/CSS/JS, no build step, one runtime dependency (Fuse.js) loaded as
an ES module straight from jsDelivr.

## Run

```
python -m http.server 8000 -d site
```

Open `http://localhost:8000`. Must be served over HTTP(S) — `app.js`
is an ES module and fetches `data/manifest.json`, both of which are
blocked under `file://`.

## Data

- `data/manifest.json` — a checked-in **copy** of the manifest
  published to the `assets-dev` branch by `album-store publish`. It is
  refreshed by hand for now:

  ```
  git show origin/assets-dev:manifest.json > site/data/manifest.json
  ```

  Automating this copy as part of `publish` is a known follow-up, not
  yet implemented.

- GIFs (`gif`, animated; `preview`, static first frame) are **not**
  copied locally — the page fetches them straight from jsDelivr via
  the `BASE` constant at the top of `app.js`:

  ```js
  const BASE = "https://cdn.jsdelivr.net/gh/vupdivup/cover-charm@assets-dev";
  ```

  Update `BASE` if/when a reviewed "prod" `assets` channel replaces
  `assets-dev` for this site.

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
