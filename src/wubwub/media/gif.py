"""Assemble a sequence of PNG frames into a GIF at a given frame rate."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PIL import Image


class GifError(Exception):
    """Raised when frames cannot be assembled into a GIF."""


def write_gif(
    frames: Sequence[str | Path],
    output: str | Path,
    *,
    fps: float = 24.0,
    loop: int = 0,
) -> Path:
    """Write ``frames`` (in order) to ``output`` as an animated GIF.

    GIF has no true alpha channel, only a single palette index marked
    transparent, so a source pixel is either fully opaque or fully
    transparent in the output (alpha thresholded at 128) -- there's no
    partial-transparency/anti-aliased edges in a GIF. Each frame is
    quantized to 255 colours (``Image.ADAPTIVE``), reserving palette
    index 255 for transparency. ``fps`` is converted to a per-frame
    duration in milliseconds. ``loop=0`` (the default) loops forever,
    matching Pillow's convention.
    """
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps!r}")
    if not frames:
        raise GifError("no frames to assemble into a GIF")

    output = Path(output)
    duration = round(1000 / fps)

    TRANSPARENT_INDEX = 255
    images = []
    for f in frames:
        rgba = Image.open(f).convert("RGBA")
        alpha = rgba.getchannel("A")
        paletted = rgba.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=TRANSPARENT_INDEX)
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
    )
    return output
