"""render: swap an image into a Blender animation and turn it into a GIF."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .blender import BlenderError, find_blender, render_frames
from .gif import GifError, write_gif

__all__ = [
    "BlenderError",
    "find_blender",
    "render_frames",
    "GifError",
    "write_gif",
    "RenderResult",
    "render_gif",
]


@dataclass(frozen=True)
class RenderResult:
    """What render_gif rendered and wrote."""

    gif: Path
    frames: list[Path]
    fps: float


def render_gif(
    blend: str | Path,
    image: str | Path,
    *,
    material: str,
    output: str | Path | None = None,
    fps: float = 24.0,
    keep_frames: bool = False,
    blender: str | Path | None = None,
) -> RenderResult:
    """Render ``blend``'s animation with ``image`` swapped into ``material``'s image texture node, and assemble the frames into a GIF at ``fps``.

    ``blend`` is copied into a scratch directory before rendering.
    Background Blender doesn't write back to the file it opens, so this
    is belt-and-braces rather than strictly required -- but it makes
    "your file is never touched" a property of this tool, not of
    whatever the ``.blend`` happens to do. ``output`` defaults to
    ``<blend stem>.gif`` in the current directory. Frames are discarded
    after assembly unless ``keep_frames`` is set, in which case they're
    left in ``<output stem>_frames/`` next to the GIF.
    """
    blend = Path(blend)
    output = Path(output) if output is not None else Path(f"{blend.stem}.gif")

    scratch = Path(tempfile.mkdtemp(prefix="render-"))
    try:
        scratch_blend = scratch / blend.name
        shutil.copy2(blend, scratch_blend)

        frame_dir = scratch / "frames"
        frames = render_frames(
            scratch_blend, image, material=material, out_dir=frame_dir, blender=blender
        )
        write_gif(frames, output, fps=fps)

        if keep_frames:
            kept_dir = Path(f"{output.stem}_frames")
            kept_dir.mkdir(parents=True, exist_ok=True)
            kept_frames = []
            for frame in frames:
                dst = kept_dir / frame.name
                shutil.move(str(frame), dst)
                kept_frames.append(dst)
            frames = kept_frames
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    return RenderResult(gif=output, frames=frames, fps=fps)
