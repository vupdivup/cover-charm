"""Module 4: tie fetch, normalize, and upload together into one call.

This is the only module in the package that imports the other three --
fetch, normalize, and upload stay independent of each other. Everything
here happens in memory: album art in, normalized bytes to R2, nothing
touches disk unless ``save`` is given.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from ._util import slugify
from .fetch import Album, CoverArtNotFound, artwork_url, download_url, find_album
from .normalize import normalize_image
from .upload import R2Config, upload_bytes

_EXTENSIONS = {"JPEG": "jpg"}


@dataclass(frozen=True)
class PublishResult:
    """What publish_cover matched and wrote."""

    album: Album
    key: str
    size: int
    mode: str


def default_key(album: Album, *, prefix: str = "", fmt: str = "JPEG") -> str:
    """Build an object key from a matched album, e.g. 'covers/miles-davis-kind-of-blue.jpg'."""
    ext = _EXTENSIONS.get(fmt.upper(), fmt.lower())
    parts = [slugify(album.artist)] if album.artist else []
    parts.append(slugify(album.title))
    name = f"{'-'.join(parts)}.{ext}"

    if not prefix:
        return name
    prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    return f"{prefix}{name}"


def publish_cover(
    title: str,
    artist: str | None = None,
    year: int | None = None,
    *,
    size: int = 600,
    mode: str = "stretch",
    fmt: str = "JPEG",
    key: str | None = None,
    prefix: str = "",
    country: str = "US",
    save: str | Path | None = None,
    config: R2Config | None = None,
    bucket: str | None = None,
) -> PublishResult:
    """Fetch an album's cover, normalize it, and upload it to R2 in one call.

    Raises CoverArtNotFound when no album matches. Nothing is written
    to disk unless ``save`` is given. R2 config/credentials (env or
    ``config``, optionally with ``bucket`` overriding the target
    bucket) are only resolved right before the upload step, so a caller
    using ``save`` still gets fetch + normalize even without R2 set up.
    """
    album = find_album(title, artist, year, country=country)
    if album is None:
        raise CoverArtNotFound(
            f"no album found for title={title!r} artist={artist!r} year={year!r}"
        )

    data = download_url(artwork_url(album, size=size))
    data = normalize_image(data, size=size, mode=mode, fmt=fmt)

    key = key or default_key(album, prefix=prefix, fmt=fmt)

    if save is not None:
        Path(save).write_bytes(data)

    config = config or R2Config.from_env()
    if bucket:
        config = dataclasses.replace(config, bucket=bucket)

    upload_bytes(data, key, config=config)

    return PublishResult(album=album, key=key, size=size, mode=mode)
