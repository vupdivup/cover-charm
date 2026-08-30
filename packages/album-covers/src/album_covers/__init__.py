"""album_covers: fetch album cover art from iTunes."""

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
