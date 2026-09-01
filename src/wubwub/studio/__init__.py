"""wubwub.studio: persist album covers (Postgres metadata + MinIO/S3 objects)."""

import logging

from .batch import RenderOutcome, render_albums
from .config import Settings
from .db import StoredAlbum
from .deploy import DeployResult, deploy_assets
from .publish import PublishResult, publish_assets
from .serve import serve_site
from .upload import upload_album

__all__ = [
    "Settings",
    "StoredAlbum",
    "upload_album",
    "RenderOutcome",
    "render_albums",
    "PublishResult",
    "publish_assets",
    "DeployResult",
    "deploy_assets",
    "serve_site",
]

# Library convention: emit records but stay silent unless a host app
# configures logging. Without this, the stdlib prints a "no handlers
# found" warning to stderr the first time this package logs anything.
logging.getLogger(__name__).addHandler(logging.NullHandler())
