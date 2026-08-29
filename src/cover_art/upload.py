"""Module 3: upload an image to Cloudflare R2 (S3-compatible object storage).

Standalone by design -- this module knows nothing about album art or
image normalization, only bytes and object keys, and does not import
anything from ``fetch`` or ``normalize``.

Requires four environment variables (or an explicit R2Config):
``R2_ACCOUNT_ID``, ``R2_ACCESS_KEY_ID``, ``R2_SECRET_ACCESS_KEY``,
``R2_BUCKET``.
"""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

import boto3

_ENV_VARS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")


class R2ConfigError(Exception):
    """Raised when R2 credentials/config can't be assembled from the environment."""


@dataclass(frozen=True)
class R2Config:
    """Credentials and target bucket for a Cloudflare R2 upload."""

    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str

    @classmethod
    def from_env(cls) -> "R2Config":
        values = {name: os.environ.get(name) for name in _ENV_VARS}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise R2ConfigError(f"missing environment variable(s): {', '.join(missing)}")
        return cls(
            account_id=values["R2_ACCOUNT_ID"],
            access_key_id=values["R2_ACCESS_KEY_ID"],
            secret_access_key=values["R2_SECRET_ACCESS_KEY"],
            bucket=values["R2_BUCKET"],
        )

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"


def _client(config: R2Config):
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name="auto",
    )


def _guess_content_type(key: str) -> str:
    content_type, _ = mimetypes.guess_type(key)
    return content_type or "application/octet-stream"


def upload_bytes(
    data: bytes,
    key: str,
    *,
    content_type: str | None = None,
    config: R2Config | None = None,
) -> str:
    """Upload raw bytes to R2 under ``key``. Returns ``key`` on success."""
    config = config or R2Config.from_env()
    client = _client(config)
    client.put_object(
        Bucket=config.bucket,
        Key=key,
        Body=data,
        ContentType=content_type or _guess_content_type(key),
    )
    return key


def upload_file(
    path: str | Path,
    key: str | None = None,
    *,
    content_type: str | None = None,
    config: R2Config | None = None,
) -> str:
    """Upload a file to R2. ``key`` defaults to the file's basename."""
    path = Path(path)
    key = key or path.name
    return upload_bytes(path.read_bytes(), key, content_type=content_type, config=config)
