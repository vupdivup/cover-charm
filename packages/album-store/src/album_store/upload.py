"""Orchestrates one album: fetch cover -> object store -> DB row."""

from __future__ import annotations

import logging

from album_covers import CoverArtNotFound, artwork_url, download_url, find_album

from .config import Settings
from .db import StoredAlbum, connect, upsert_album
from .objects import client as s3_client
from .objects import cover_key, ensure_bucket, put_cover

logger = logging.getLogger(__name__)

__all__ = ["StoredAlbum", "upload_album"]


def upload_album(
    title: str,
    artist: str | None = None,
    *,
    size: int = 600,
    settings: Settings | None = None,
) -> StoredAlbum:
    """Find an album's cover, store it in MinIO, upsert its row in Postgres.

    Raises album_covers.CoverArtNotFound if no matching album/cover exists.
    Idempotent on (artist, title) case-insensitively: re-uploading the same
    album overwrites the existing object and row rather than duplicating.
    """
    settings = settings or Settings.from_env()

    album = find_album(title, artist)
    if album is None:
        raise CoverArtNotFound(f"no album found for title={title!r} artist={artist!r}")

    url = artwork_url(album, size=size)
    if url is None:
        raise CoverArtNotFound(f"no cover art for {album.title!r} by {album.artist!r}")
    data = download_url(url)
    logger.debug("fetched %d bytes for %r by %r", len(data), album.title, album.artist)

    key = cover_key(album.artist, album.title)
    s3 = s3_client(settings)
    # A row must never point at an object that doesn't exist, so the
    # upload happens before the DB write. The reverse failure (orphan
    # object, no row) is harmless -- the next upload overwrites the key.
    ensure_bucket(s3, settings)
    cover_url = put_cover(s3, settings, key, data)

    with connect(settings) as conn:
        stored = upsert_album(
            conn,
            artist=album.artist,
            title=album.title,
            year=album.year,
            cover_key=key,
            cover_url=cover_url,
        )

    logger.info("stored album id=%s %r by %r -> %s", stored.id, stored.title, stored.artist, stored.cover_url)
    return stored
