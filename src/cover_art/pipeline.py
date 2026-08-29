"""Module 4: tie fetch, normalize, and upload together into one call.

This is the only module in the package that imports the other three --
fetch, normalize, and upload stay independent of each other. Everything
here happens in memory: album art in, normalized bytes to R2, nothing
touches disk unless ``save`` is given.

``publish_covers`` runs the same pipeline over many albums, throttled
to stay under the iTunes Search API's rate limit and resilient to a
single album failing.
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from ._util import slugify
from .fetch import Album, CoverArtNotFound, artwork_url, download_url, find_album
from .normalize import normalize_image
from .upload import R2Config, R2ConfigError, upload_bytes

_EXTENSIONS = {"JPEG": "jpg"}

# The iTunes Search API allows roughly 20 requests/minute per IP,
# uncredentialed, and answers 403 (sometimes 429) past that. Each album
# in a batch costs exactly one search request (fetch.find_album), so
# spacing whole publish_cover calls by this interval is equivalent to
# spacing the search requests themselves.
DEFAULT_SEARCH_INTERVAL = 3.0
_RATE_LIMITED_STATUSES = (403, 429)


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


@dataclass(frozen=True)
class PublishOutcome:
    """The result of one album in a publish_covers batch."""

    title: str
    artist: str | None
    year: int | None
    result: PublishResult | None = None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _normalize_item(item) -> tuple[str, str | None, int | None]:
    """Coerce a batch item into a (title, artist, year) triple."""
    if isinstance(item, str):
        return item, None, None
    if isinstance(item, Mapping):
        if "title" not in item:
            raise ValueError(f"batch item missing 'title': {item!r}")
        return item["title"], item.get("artist"), item.get("year")
    if isinstance(item, Sequence):
        if not 1 <= len(item) <= 3:
            raise ValueError(f"batch item must have 1-3 elements: {item!r}")
        padded = list(item) + [None] * (3 - len(item))
        return padded[0], padded[1], padded[2]
    raise ValueError(f"unrecognized batch item: {item!r}")


class _Throttle:
    """Enforces a minimum gap between successive wait() calls."""

    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._last: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last is not None:
            remaining = self._interval - (now - self._last)
            if remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
        self._last = now


def _is_rate_limited(exc: Exception) -> bool:
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in _RATE_LIMITED_STATUSES
    )


def publish_covers(
    items: Iterable[str | Sequence | Mapping],
    *,
    size: int = 600,
    mode: str = "stretch",
    fmt: str = "JPEG",
    prefix: str = "",
    country: str = "US",
    config: R2Config | None = None,
    bucket: str | None = None,
    search_interval: float = DEFAULT_SEARCH_INTERVAL,
    max_retries: int = 5,
    initial_backoff: float = 5.0,
    on_result: Callable[[PublishOutcome], None] | None = None,
) -> list[PublishOutcome]:
    """Run publish_cover over many albums.

    Throttled to ``search_interval`` seconds between albums to stay
    under the iTunes Search API's rate limit, and retries a rate-limited
    album (HTTP 403/429) with exponential backoff up to ``max_retries``
    times before giving up on it. One album failing doesn't stop the
    rest -- its failure is recorded in that album's PublishOutcome.

    R2 config/credentials are resolved once up front (same rules as
    publish_cover's ``config``/``bucket``), so a bad config fails
    immediately rather than after downloading everything, and a
    R2ConfigError raised mid-batch (which shouldn't happen, since it's
    already resolved) is re-raised rather than recorded per album, since
    every remaining album would fail identically.

    ``items`` accepts, per album: a bare title string, a
    ``(title, artist)`` or ``(title, artist, year)`` sequence, or a
    ``{"title": ..., "artist": ..., "year": ...}`` mapping.

    Not a batch parameter: ``save`` -- a batch writes to R2, and one
    local path can't serve many albums.
    """
    config = config or R2Config.from_env()
    if bucket:
        config = dataclasses.replace(config, bucket=bucket)

    throttle = _Throttle(search_interval)
    outcomes: list[PublishOutcome] = []

    for item in items:
        title, artist, year = _normalize_item(item)

        attempt = 0
        while True:
            throttle.wait()
            try:
                result = publish_cover(
                    title,
                    artist,
                    year,
                    size=size,
                    mode=mode,
                    fmt=fmt,
                    prefix=prefix,
                    country=country,
                    config=config,
                )
                outcome = PublishOutcome(title=title, artist=artist, year=year, result=result)
            except R2ConfigError:
                raise
            except Exception as exc:
                if _is_rate_limited(exc) and attempt < max_retries:
                    time.sleep(initial_backoff * (2**attempt))
                    attempt += 1
                    continue
                outcome = PublishOutcome(title=title, artist=artist, year=year, error=exc)

            outcomes.append(outcome)
            if on_result is not None:
                on_result(outcome)
            break

    return outcomes
