"""cover_art: fetch album cover art from iTunes and normalize it to a square size."""

from .fetch import Album, CoverArtNotFound, download_cover, find_cover_url, search_albums
from .normalize import MODES, normalize_file, normalize_image
from .upload import R2Config, R2ConfigError, upload_bytes, upload_file

__all__ = [
    "Album",
    "CoverArtNotFound",
    "search_albums",
    "find_cover_url",
    "download_cover",
    "normalize_image",
    "normalize_file",
    "MODES",
    "R2Config",
    "R2ConfigError",
    "upload_bytes",
    "upload_file",
]
