"""Module 2: normalize a cover image to a fixed square size (default 600x600).

Three resize modes are supported:

- ``stretch`` (default): scale X and Y independently to fill the square.
  Distorts the aspect ratio when the source isn't already square.
- ``crop``: center-crop to a square before scaling. No distortion, loses
  the outer edges of the non-square dimension.
- ``pad``: scale to fit inside the square, then letterbox with a solid
  background color. No distortion, no cropping, adds borders.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

MODES = ("stretch", "crop", "pad")


def _center_crop_to_square(img: Image.Image) -> Image.Image:
    width, height = img.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return img.crop((left, top, left + side, top + side))


def _resize(img: Image.Image, size: int, mode: str, background) -> Image.Image:
    if mode == "stretch":
        return img.resize((size, size), Image.LANCZOS)
    if mode == "crop":
        return _center_crop_to_square(img).resize((size, size), Image.LANCZOS)
    if mode == "pad":
        fitted = ImageOps.contain(img, (size, size), Image.LANCZOS)
        canvas_mode = "RGBA" if img.mode == "RGBA" else "RGB"
        canvas = Image.new(canvas_mode, (size, size), background)
        offset = ((size - fitted.width) // 2, (size - fitted.height) // 2)
        canvas.paste(fitted, offset, fitted if fitted.mode == "RGBA" else None)
        return canvas
    raise ValueError(f"unknown mode {mode!r}, expected one of {MODES}")


def normalize_image(
    data: bytes,
    *,
    size: int = 600,
    mode: str = "stretch",
    fmt: str = "JPEG",
    background: tuple[int, int, int] = (0, 0, 0),
) -> bytes:
    """Normalize raw image bytes to a size x size square, returned as ``fmt`` bytes."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}, expected one of {MODES}")

    img = Image.open(io.BytesIO(data))
    img.load()

    wants_alpha = fmt.upper() in ("PNG", "WEBP") and (mode == "pad" or img.mode == "RGBA")
    img = img.convert("RGBA" if wants_alpha else "RGB")

    result = _resize(img, size, mode, background)

    if fmt.upper() == "JPEG" and result.mode != "RGB":
        result = result.convert("RGB")

    out = io.BytesIO()
    result.save(out, format=fmt.upper())
    return out.getvalue()


def normalize_file(
    src: str | Path,
    dst: str | Path,
    *,
    size: int = 600,
    mode: str = "stretch",
    fmt: str | None = None,
) -> Path:
    """Normalize an image file on disk to a size x size square, written to ``dst``."""
    src = Path(src)
    dst = Path(dst)

    if fmt is None:
        suffix = dst.suffix.lstrip(".").upper()
        fmt = "JPEG" if suffix in ("JPG", "JPEG") else suffix or "JPEG"

    data = normalize_image(src.read_bytes(), size=size, mode=mode, fmt=fmt)
    dst.write_bytes(data)
    return dst
