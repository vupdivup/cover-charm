"""Module 1: find and download album cover art via MusicBrainz + Cover Art Archive.

MusicBrainz (https://musicbrainz.org/doc/MusicBrainz_API) is a free,
no-API-key, community-maintained music encyclopedia; its ``release-group``
search resolves a title/artist query to a stable MBID. Cover Art Archive
(https://musicbrainz.org/doc/Cover_Art_Archive/API), keyed by that same
MBID, hosts the actual artwork. The iTunes Search API was tried first but
its ranking regularly omits canonical albums entirely for plausible
queries (e.g. Nirvana's "Nevermind" and Green Day's "Dookie" never turned
up, even though both exist in Apple's own catalog) -- MusicBrainz search
returned the correct release group as the top hit for every such case
checked, so it replaces iTunes outright rather than sitting behind it.
"""

from __future__ import annotations

import difflib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass

import httpx

from ._util import Throttle

logger = logging.getLogger(__name__)

_MB_SEARCH_URL = "https://musicbrainz.org/ws/2/release-group/"
_CAA_URL = "https://coverartarchive.org/release-group/"
# MusicBrainz asks that clients identify themselves with a descriptive
# User-Agent including contact info; an anonymous one risks a harder block
# than the ordinary rate limit.
_USER_AGENT = "album-covers/0.1.0 (https://github.com/vupdivup/cover-art)"

# MusicBrainz allows roughly 1 request/second, uncredentialed, and answers
# 503 (sometimes 429) past that -- Cover Art Archive shares the block since
# it's keyed by the same MBID space. Read at call time (not cached), so
# reassigning these takes effect immediately.
SEARCH_INTERVAL = 1.1
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0
_RATE_LIMITED_STATUSES = (429, 503)

# Cover Art Archive serves only these fixed thumbnail sizes (plus the
# full-size original) -- there's no arbitrary-resize trick like iTunes'
# filename token, so a requested size is snapped to the nearest of these.
_CAA_SIZES = (250, 500, 1200)

# Once search_albums ranks candidates, only the first few are worth an
# artwork lookup -- each is a separate rate-limited request, and a bad
# query would otherwise burn many of them for nothing.
_MAX_ARTWORK_LOOKUPS = 4

# Minimum blended title/artist similarity for a result to count as the
# requested album. MusicBrainz's own relevance score still ranks
# tributes/demos/remixes close to the real thing, so without a floor a
# typo'd or absent album could silently yield the wrong cover.
MATCH_THRESHOLD = 0.75

# Release-group secondary types that score well on title similarity but
# are rarely what a bare title+artist query means (a demo take, a live
# recording, a remix set, a spoken interview disc). Compilation and
# Soundtrack are deliberately NOT here -- they're often the *correct*
# answer for a Various Artists query (e.g. a movie soundtrack).
_DEPRIORITIZED_SECONDARY_TYPES = {"demo", "remix", "live", "interview"}
_SECONDARY_TYPE_PENALTY = 0.15

# Edition noise a release title carries that the query never does
# (e.g. "OK Computer (Deluxe Edition)"), stripped before comparing.
_EDITION_SUFFIX_RE = re.compile(
    r"[\(\[][^\)\]]*[\)\]]|\b(deluxe|remaster(?:ed)?|expanded|anniversary|edition|version)\b",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")

# Characters with special meaning in MusicBrainz's Lucene query syntax that
# must be escaped before interpolating user text into a quoted phrase.
_LUCENE_ESCAPE_RE = re.compile(r'([\\"])')

# Shared across every search_albums/artwork_url call, including
# single-shot ones -- the first call never sleeps, so interactive use is
# unaffected. MusicBrainz and Cover Art Archive share one budget since
# they're the same service's rate limit.
_search_throttle = Throttle(lambda: SEARCH_INTERVAL)


class CoverArtNotFound(Exception):
    """Raised when no matching album (or no artwork for it) is found."""


@dataclass(frozen=True)
class Album:
    """One release-group result from the MusicBrainz Search API."""

    title: str
    artist: str
    year: int | None
    release_group_id: str  # MusicBrainz MBID


def _parse_year(release_date: str | None) -> int | None:
    if not release_date or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None


def _to_album(result: dict) -> Album | None:
    title = result.get("title")
    release_group_id = result.get("id")
    if not title or not release_group_id:
        return None
    artist_credit = result.get("artist-credit") or []
    artist = "".join(
        (c.get("name", "") + c.get("joinphrase", "")) for c in artist_credit if isinstance(c, dict)
    )
    return Album(
        title=title,
        artist=artist,
        year=_parse_year(result.get("first-release-date")),
        release_group_id=release_group_id,
    )


def _lucene_escape(s: str) -> str:
    return _LUCENE_ESCAPE_RE.sub(r"\\\1", s)


def _normalize(s: str) -> str:
    """Casefold and strip accents, edition noise, and punctuation for comparison."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _EDITION_SUFFIX_RE.sub(" ", s.casefold())
    s = _PUNCT_RE.sub(" ", s)
    return _WHITESPACE_RE.sub(" ", s).strip()


def _similarity(a: str, b: str) -> float:
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    # A whole-word prefix match (e.g. "blonde" vs. "blonde deluxe" once
    # edition noise is stripped) is as good as identical.
    shorter, longer = sorted((na, nb), key=len)
    if longer.startswith(shorter):
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _match_score(album: Album, title: str, artist: str | None, result: dict) -> float:
    title_score = _similarity(album.title, title)
    score = title_score if artist is None else 0.6 * title_score + 0.4 * _similarity(album.artist, artist)

    secondary_types = {t.lower() for t in result.get("secondary-types") or []}
    if secondary_types & _DEPRIORITIZED_SECONDARY_TYPES:
        score -= _SECONDARY_TYPE_PENALTY

    return score


def _is_rate_limited(exc: Exception) -> bool:
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in _RATE_LIMITED_STATUSES
    )


def _get_with_retry(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET with raise_for_status(), retrying a 429/503 with exponential backoff."""
    attempt = 0
    while True:
        try:
            response = client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if not _is_rate_limited(exc):
                raise
            if attempt >= MAX_RETRIES:
                logger.warning(
                    "giving up after %d retries on %s: HTTP %d", attempt, url, exc.response.status_code
                )
                raise
            backoff = INITIAL_BACKOFF * (2**attempt)
            logger.warning(
                "HTTP %d from %s, retry %d/%d in %.1fs", exc.response.status_code, url, attempt + 1, MAX_RETRIES, backoff
            )
            time.sleep(backoff)
            attempt += 1


def search_albums(title: str, artist: str | None = None, *, limit: int = 25) -> list[Album]:
    """Search MusicBrainz for albums (release groups), ranked best match first.

    Results are scored client-side by fuzzy title/artist similarity --
    MusicBrainz's own relevance score still ranks tributes, demos, and
    remixes close to a correct match -- and anything under MATCH_THRESHOLD
    is dropped.

    Release year is deliberately not used as a matching signal: a release
    group's first-release-date can reflect a reissue's catalog entry
    rather than the queried edition, so filtering on it risks discarding
    correct matches more often than it rejects wrong ones.
    """
    query = f'releasegroup:"{_lucene_escape(title)}"'
    if artist:
        query += f' AND artist:"{_lucene_escape(artist)}"'
    params = {"query": query, "fmt": "json", "limit": limit}
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    _search_throttle.wait()
    logger.debug("MusicBrainz query: %s", query)
    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
        response = _get_with_retry(client, _MB_SEARCH_URL, params=params)
        data = response.json()

    results = data.get("release-groups", [])
    parsed = [(a, r) for a, r in ((_to_album(r), r) for r in results) if a is not None]
    logger.debug("MusicBrainz returned %d release group(s) for %r", len(results), title)

    scored = [(a, _match_score(a, title, artist, r)) for a, r in parsed]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    logger.debug(
        "top candidates for %r: %s",
        title,
        [(a.title, a.artist, round(s, 3)) for a, s in scored[:5]],
    )

    matched = [(a, s) for a, s in scored if s >= MATCH_THRESHOLD]
    if not matched:
        best = scored[0] if scored else None
        logger.warning(
            "no candidate above MATCH_THRESHOLD=%.2f for title=%r artist=%r (best: %s, score=%.3f)",
            MATCH_THRESHOLD,
            title,
            artist,
            best[0].title if best else None,
            best[1] if best else 0.0,
        )

    return [a for a, _ in matched]


def find_album(title: str, artist: str | None = None) -> Album | None:
    """Return the best-match Album for the query, or None."""
    albums = search_albums(title, artist)
    return albums[0] if albums else None


def _nearest_caa_size(size: int) -> int | None:
    """Snap a requested size to Cover Art Archive's fixed thumbnails, or None for full-size."""
    if size > _CAA_SIZES[-1]:
        return None
    return min(_CAA_SIZES, key=lambda s: abs(s - size))


def artwork_url(album: Album, *, size: int = 600) -> str | None:
    """Return album's front-cover URL from Cover Art Archive, or None if it has no art.

    Unlike iTunes' filename-token resize, Cover Art Archive only serves a
    fixed set of thumbnail sizes plus the full-size original, so this is a
    network call (throttled/retried like search_albums) rather than a
    string transform, and ``size`` is snapped to the nearest available.
    """
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    _search_throttle.wait()
    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
        try:
            response = _get_with_retry(client, _CAA_URL + album.release_group_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info("no Cover Art Archive entry for %r (%s)", album.title, album.release_group_id)
                return None
            raise
        data = response.json()

    images = data.get("images", [])
    if not images:
        logger.info("Cover Art Archive entry for %r (%s) has no images", album.title, album.release_group_id)
        return None
    image = next((i for i in images if i.get("front")), images[0])

    nearest = _nearest_caa_size(size)
    url = image["thumbnails"].get(str(nearest)) if nearest else None
    url = url or image.get("image")
    if url is None:
        logger.info("no usable thumbnail/image URL for %r (%s)", album.title, album.release_group_id)
        return None
    # Cover Art Archive links are plain http:// even over an https request.
    url = url.replace("http://", "https://", 1)
    logger.debug("resolved artwork for %r (%s) near %dpx: %s", album.title, album.release_group_id, size, url)
    return url


def download_url(url: str) -> bytes:
    """GET raw bytes from an artwork URL.

    Retries a 429/503 like search_albums does, though the archive.org CDN
    that Cover Art Archive redirects to isn't meaningfully rate-limited in
    practice. Not throttled -- the throttle exists solely to pace
    MusicBrainz/Cover Art Archive API calls. follow_redirects is required:
    Cover Art Archive's own URLs redirect (307) to archive.org.
    """
    headers = {"User-Agent": _USER_AGENT}
    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
        response = _get_with_retry(client, url)
        logger.debug("downloaded %d bytes from %s", len(response.content), url)
        return response.content


def find_cover_url(title: str, artist: str | None = None, *, size: int = 600) -> str | None:
    """Return the best-match album's artwork URL near ``size``px, or None.

    Walks ranked candidates from search_albums (capped at
    _MAX_ARTWORK_LOOKUPS) rather than just the top one, since not every
    release group has art in Cover Art Archive -- the next-best textual
    match often does.
    """
    candidates = search_albums(title, artist)[:_MAX_ARTWORK_LOOKUPS]
    for album in candidates:
        url = artwork_url(album, size=size)
        if url is not None:
            logger.info(
                "cover found for title=%r artist=%r -> %r by %r (%s)",
                title,
                artist,
                album.title,
                album.artist,
                album.release_group_id,
            )
            return url
        logger.debug("no art for candidate %r (%s), trying next", album.title, album.release_group_id)

    if candidates:
        logger.warning(
            "no artwork found among top %d candidate(s) for title=%r artist=%r",
            len(candidates),
            title,
            artist,
        )
    return None


def download_cover(title: str, artist: str | None = None, *, size: int = 600) -> bytes:
    """Find and download an album's cover art, raising CoverArtNotFound on no match."""
    url = find_cover_url(title, artist, size=size)
    if url is None:
        raise CoverArtNotFound(f"no album found for title={title!r} artist={artist!r}")
    return download_url(url)
