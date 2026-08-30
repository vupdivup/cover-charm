"""album_covers: fetch album cover art via MusicBrainz + Cover Art Archive."""

import logging

from .fetch import (
    Album,
    CoverArtNotFound,
    artwork_url,
    download_cover,
    download_url,
    find_album,
    find_cover_url,
    search_albums,
)

__all__ = [
    "Album",
    "CoverArtNotFound",
    "search_albums",
    "find_album",
    "artwork_url",
    "download_url",
    "find_cover_url",
    "download_cover",
]

# Library convention: emit records but stay silent unless a host app
# configures logging. Without this, the stdlib prints a "no handlers
# found" warning to stderr the first time this package logs anything.
logging.getLogger(__name__).addHandler(logging.NullHandler())
