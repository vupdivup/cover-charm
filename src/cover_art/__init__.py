"""cover_art: fetch album cover art from iTunes and normalize it to a square size."""

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
from .normalize import MODES, normalize_file, normalize_image
from .pipeline import PublishResult, default_key, publish_cover
from .upload import R2Config, R2ConfigError, upload_bytes, upload_file

__all__ = [
    "Album",
    "CoverArtNotFound",
    "search_albums",
    "find_album",
    "artwork_url",
    "download_url",
    "find_cover_url",
    "download_cover",
    "normalize_image",
    "normalize_file",
    "MODES",
    "R2Config",
    "R2ConfigError",
    "upload_bytes",
    "upload_file",
    "publish_cover",
    "PublishResult",
    "default_key",
]
