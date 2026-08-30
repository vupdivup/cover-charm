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

    GIF is a paletted 256-colour format, so each frame is quantized
    with ``Image.ADAPTIVE``; alpha is flattened, not preserved. ``fps``
    is converted to a per-frame duration in milliseconds. ``loop=0``
    (the default) loops forever, matching Pillow's convention.
    """
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps!r}")
    if not frames:
        raise GifError("no frames to assemble into a GIF")

    output = Path(output)
    duration = round(1000 / fps)

    images = [Image.open(f).convert("RGB").convert("P", palette=Image.ADAPTIVE) for f in frames]

    images[0].save(
        output,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=loop,
        disposal=2,
    )
    return output
