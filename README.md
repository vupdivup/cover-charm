# wubwub

Fetch album cover art, render it into an animated GIF through a Blender
animation, and publish the results for a static showcase site.

One package, `src/wubwub/`, with three subpackages behind one CLI:

- [`wubwub.covers`](src/wubwub/covers/README.md) -- fetch cover art via
  MusicBrainz + Cover Art Archive
- [`wubwub.media`](src/wubwub/media/README.md) -- swap an image into a
  Blender animation's texture, render it, assemble a GIF
- [`wubwub.studio`](src/wubwub/studio/README.md) -- persist covers/GIFs
  (Postgres + MinIO) and publish them to a git branch for jsDelivr CDN
  serving

`site/` is a static, no-build showcase page that browses the published
GIFs; see `site/README.md`.

## Install

```
uv sync
```

## Usage

```
wubwub covers fetch "Kind of Blue" --artist "Miles Davis" -o cover.jpg
wubwub media render scene.blend --image cover.jpg --material CoverMaterial
wubwub studio init
wubwub studio upload "In Rainbows" --artist "Radiohead"
wubwub studio render --blend animation.blend --material CoverMat
wubwub studio publish
```

Each subcommand's own README has the full option list. `-v/-vv/-q`
control logging verbosity on every command.

## Local services

`docker compose up -d` starts Postgres, MinIO, and pgweb for
`wubwub studio` -- see `src/wubwub/studio/README.md` for details and
`.env.example` for the environment variables to override.

## License

The code in this repository -- `src/`, `site/`, `sql/`, and the
tooling around them -- is MIT licensed; see [LICENSE](LICENSE). The
Blender scene the renders are built from is the author's own work and
falls under the same terms if it is ever committed (`.blend` files are
gitignored, so the repository currently carries none).

Album cover art is **not** covered by that license and is not the
author's to relicense. Covers come from the [Cover Art
Archive](https://coverartarchive.org/), which passes on no rights to
downstream users -- each image stays with its respective rights
holder, and the GIFs rendered from them are derivative and carry the
same restriction. Neither the covers nor the GIFs live in this branch:
`wubwub studio publish` / `deploy` push them to the orphan `assets`
and `assets-dev` branches, and the showcase site serves them from
there over jsDelivr for identification and to demonstrate the render
pipeline, non-commercially.
