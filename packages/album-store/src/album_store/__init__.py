"""album_store: persist album covers (Postgres metadata + MinIO/S3 objects)."""

import logging

from .config import Settings
from .db import StoredAlbum
from .render import RenderOutcome, render_albums
from .upload import upload_album

__all__ = [
    "Settings",
    "StoredAlbum",
    "upload_album",
    "RenderOutcome",
    "render_albums",
]

# Library convention: emit records but stay silent unless a host app
# configures logging. Without this, the stdlib prints a "no handlers
# found" warning to stderr the first time this package logs anything.
logging.getLogger(__name__).addHandler(logging.NullHandler())
