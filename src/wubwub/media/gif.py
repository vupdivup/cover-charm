"""Assemble a sequence of PNG frames into a GIF at a given frame rate."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PIL import Image


class GifError(Exception):
    """Raised when frames cannot be assembled into a GIF."""


# Sampling every frame into the shared-palette montage (see write_gif) is
# unnecessary past a point of diminishing returns -- a short animation's
# color range is well represented by a handful of frames, and capping the
# sample keeps the montage image bounded for long/high-resolution inputs.
_MAX_PALETTE_SAMPLES = 32


def write_gif(
    frames: Sequence[str | Path],
    output: str | Path,
    *,
    fps: float = 24.0,
    loop: int = 0,
    colors: int = 128,
    dither: bool = False,
) -> Path:
    """Write ``frames`` (in order) to ``output`` as an animated GIF.

    GIF has no true alpha channel, only a single palette index marked
    transparent, so a source pixel is either fully opaque or fully
    transparent in the output (alpha thresholded at 128) -- there's no
    partial-transparency/anti-aliased edges in a GIF. ``fps`` is
    converted to a per-frame duration in milliseconds. ``loop=0`` (the
    default) loops forever, matching Pillow's convention.

    All frames share one ``colors``-entry palette (built once from a
    sample of the frames) rather than each frame getting its own locally
    adaptive palette -- a per-frame palette is the dominant cost in a
    naively-encoded GIF, since every frame otherwise carries its own
    ~colors-entry color table. Palette index ``colors`` is reserved for
    transparency. ``dither`` defaults off: dithering scatters noise
    pixel-to-pixel, which defeats the run-length patterns GIF's LZW
    compression relies on, for a quality gain that's rarely visible at
    the small sizes these are actually displayed at.
    """
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps!r}")
    if not frames:
        raise GifError("no frames to assemble into a GIF")

    output = Path(output)
    duration = round(1000 / fps)

    rgba_frames = [Image.open(f).convert("RGBA") for f in frames]
    palette = _build_palette(rgba_frames, colors)
    dither_mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE

    TRANSPARENT_INDEX = colors
    images = []
    for rgba in rgba_frames:
        alpha = rgba.getchannel("A")
        paletted = rgba.convert("RGB").quantize(palette=palette, dither=dither_mode)
        mask = alpha.point(lambda a: 255 if a <= 128 else 0)
        paletted.paste(TRANSPARENT_INDEX, mask)
        paletted.info["transparency"] = TRANSPARENT_INDEX
        images.append(paletted)

    images[0].save(
        output,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=loop,
        disposal=2,
        transparency=TRANSPARENT_INDEX,
        optimize=True,
    )
    return output


def _build_palette(frames: Sequence[Image.Image], colors: int) -> Image.Image:
    """Build one shared adaptive palette from a sample of ``frames``.

    Stacks the sampled frames' RGB into a single tall image and quantizes
    that once, so every frame's palette index for a given color agrees --
    the prerequisite for a global (rather than per-frame) color table.
    """
    step = max(1, len(frames) // _MAX_PALETTE_SAMPLES)
    sample = frames[::step]
    width, height = sample[0].size
    montage = Image.new("RGB", (width, height * len(sample)))
    for i, frame in enumerate(sample):
        montage.paste(frame.convert("RGB"), (0, i * height))
    return montage.convert("P", palette=Image.ADAPTIVE, colors=colors)
