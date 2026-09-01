# wubwub.render

Take a Blender `.blend` file, swap an image into one of its image
textures, render the animation, and assemble the frames into a GIF.

The `.blend` you point it at is never modified — it's copied into a
scratch directory before rendering, and background Blender doesn't
write back to the file it opens anyway.

## Install

From the repo root:

```
uv sync
```

## Requirements

A local Blender install. Not bundled — this drives Blender as a
subprocess rather than depending on the `bpy` PyPI package, since `bpy`
wheels are pinned to one exact Python version and are ~300MB, while a
Blender install is something most users already have.

Auto-detected, in order: `--blender`/`blender=`, the `BLENDER` env var,
`blender`/`blender.exe` on `PATH`, then the default per-platform
install directories (newest version wins). Point at it explicitly if
detection doesn't find yours.

**Windows / WSL:** works from either side. Run natively on Windows, or
from WSL against a Windows-side Blender install (paths are translated
via `wslpath` automatically when needed — nothing to configure).

## CLI

```
wubwub render gif scene.blend --image cover.jpg --material CoverMaterial -o out.gif --fps 12
```

Options: `--image` (required), `--material` (required — the name of the
material whose image texture node gets the new image; visible at the
top of the Properties > Material tab and in the Outliner, unlike an
image datablock's name, which is buried in the Shader Editor. On a
mismatch, the error lists every node-enabled material name the
`.blend` actually has), `-o/--output` (default: `<blend stem>.gif`),
`--fps` (default 24), `--keep-frames` (keep the rendered PNGs in
`<output stem>_frames/` instead of discarding them), `--blender` (path
to the executable, overriding auto-detection), `--preview` (write only
the first frame as a single-frame GIF), `--preview-output` (also write a
single-frame preview GIF to this path, alongside the normal output).

Prints the frame count to stderr and the GIF path alone to stdout.

## Python API

```python
from wubwub.render import render_gif

result = render_gif("scene.blend", "cover.jpg", material="CoverMaterial", fps=12)
print(result.gif, len(result.frames), result.fps)

# preview=True keeps only the first rendered frame
still = render_gif("scene.blend", "cover.jpg", material="CoverMaterial", preview=True)

# preview_output writes a second, single-frame GIF from the same render
result = render_gif(
    "scene.blend", "cover.jpg", material="CoverMaterial", preview_output="cover_preview.gif"
)
print(result.preview)
```

Exports: `render_gif`, `RenderResult`, `BlenderError`, `find_blender`,
`render_frames`, `GifError`, `write_gif`.

## Notes

- The `.blend`'s own frame range, resolution, engine, and sample count
  are used as authored — none of that is overridable from this tool.
- The named material must have exactly one image texture node. Zero
  is an error naming the material; more than one is also an error,
  listing the node names, rather than guessing which one you meant.
- If the target image is packed into the `.blend`, it's unpacked
  before the swap (a packed image otherwise ignores a new file path).
- GIF is a 256-colour paletted format: frames are quantized with
  adaptive palette selection, and alpha is preserved as binary
  transparency (thresholded at 128) -- no partial/anti-aliased
  transparency, since GIF has no true alpha channel.
- `--preview` doesn't shorten the Blender render itself — the full
  authored frame range is always rendered, and everything after the
  first frame is dropped afterward. Narrowing the frame range inside
  `_script.py` would be fragile, so this is deliberate.
- `--preview-output` is independent of `--preview`: it adds a second,
  single-frame GIF next to the normal output rather than replacing it,
  and reuses the frames from the one Blender run instead of rendering
  again.
- **Windows support is implemented but not yet verified on a native
  Windows host** — everything here has been tested from WSL against a
  Windows-side Blender install. If you hit a platform-specific issue
  running natively on Windows, please report it.
