"""Module 1: find and download album cover art via the iTunes Search API.

The iTunes Search API (https://performance-partners.apple.com/search-api)
is free, requires no API key, and returns an ``artworkUrl100`` field for
each result. That URL embeds the resolution in its filename
(``.../100x100bb.jpg``), so swapping the ``100x100`` for any other size
(e.g. ``600x600``) yields a larger version of the same artwork with no
extra request needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

_SEARCH_URL = "https://itunes.apple.com/search"
_USER_AGENT = "cover-art/0.1.0"
_ARTWORK_TOKEN = "100x100bb"


class CoverArtNotFound(Exception):
    """Raised when no matching album (or no artwork for it) is found."""


@dataclass(frozen=True)
class Album:
    """One album result from the iTunes Search API."""

    title: str
    artist: str
    year: int | None
    artwork_url: str
    collection_id: int


def _parse_year(release_date: str | None) -> int | None:
    if not release_date or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None


def _to_album(result: dict) -> Album | None:
    artwork_url = result.get("artworkUrl100")
    title = result.get("collectionName")
    collection_id = result.get("collectionId")
    if not artwork_url or not title or collection_id is None:
        return None
    return Album(
        title=title,
        artist=result.get("artistName", ""),
        year=_parse_year(result.get("releaseDate")),
        artwork_url=artwork_url,
        collection_id=collection_id,
    )


def search_albums(
    title: str,
    artist: str | None = None,
    year: int | None = None,
    *,
    limit: int = 25,
    country: str = "US",
) -> list[Album]:
    """Search iTunes for albums, ranked best match first.

    ``artist`` and ``year``, when given, are used to filter and rank
    results client-side -- the iTunes Search API has no server-side
    parameter for either.
    """
    term = title if not artist else f"{title} {artist}"
    params = {
        "term": term,
        "entity": "album",
        "media": "music",
        "limit": limit,
        "country": country,
    }
    headers = {"User-Agent": _USER_AGENT}
    with httpx.Client(headers=headers, timeout=10.0) as client:
        response = client.get(_SEARCH_URL, params=params)
        response.raise_for_status()
        # iTunes replies with content-type text/javascript; parse the
        # body directly rather than relying on httpx's content-type check.
        data = response.json()

    albums = [a for a in (_to_album(r) for r in data.get("results", [])) if a is not None]

    if year is not None:
        albums = [a for a in albums if a.year is None or a.year == year]

    if artist is not None:
        artist_lower = artist.lower()
        exact = [a for a in albums if a.artist.lower() == artist_lower]
        contains = [a for a in albums if artist_lower in a.artist.lower()]
        others = [a for a in albums if a not in exact and a not in contains]
        albums = exact + [a for a in contains if a not in exact] + others

    return albums


def find_album(
    title: str,
    artist: str | None = None,
    year: int | None = None,
    *,
    country: str = "US",
) -> Album | None:
    """Return the best-match Album for the query, or None."""
    albums = search_albums(title, artist, year, country=country)
    return albums[0] if albums else None


def artwork_url(album: Album, *, size: int = 600) -> str:
    """Return ``album``'s artwork URL resized to ``size``x``size``."""
    return album.artwork_url.replace(_ARTWORK_TOKEN, f"{size}x{size}bb")


def download_url(url: str) -> bytes:
    """GET raw bytes from an artwork URL."""
    headers = {"User-Agent": _USER_AGENT}
    with httpx.Client(headers=headers, timeout=10.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def find_cover_url(
    title: str,
    artist: str | None = None,
    year: int | None = None,
    *,
    size: int = 600,
    country: str = "US",
) -> str | None:
    """Return the best-match album's artwork URL at ``size``x``size``, or None."""
    album = find_album(title, artist, year, country=country)
    if album is None:
        return None
    return artwork_url(album, size=size)


def download_cover(
    title: str,
    artist: str | None = None,
    year: int | None = None,
    *,
    size: int = 600,
    country: str = "US",
) -> bytes:
    """Find and download an album's cover art, raising CoverArtNotFound on no match."""
    url = find_cover_url(title, artist, year, size=size, country=country)
    if url is None:
        raise CoverArtNotFound(
            f"no album found for title={title!r} artist={artist!r} year={year!r}"
        )
    return download_url(url)
