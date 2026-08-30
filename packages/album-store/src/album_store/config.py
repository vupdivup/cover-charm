"""Env-driven settings, read the same way packages/render/src/render/blender.py
reads BLENDER: plain os.environ.get with a default, no config framework.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    # The URL boto3 talks to and the URL stored in the DB can differ (e.g.
    # a container-internal host vs. localhost for whoever reads the row
    # later), so this is allowed to diverge from minio_endpoint.
    minio_public_endpoint: str

    @classmethod
    def from_env(cls) -> "Settings":
        minio_endpoint = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL", "postgresql://cover_art:cover_art@localhost:5432/cover_art"
            ),
            minio_endpoint=minio_endpoint,
            minio_access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
            minio_secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
            minio_bucket=os.environ.get("MINIO_BUCKET", "covers"),
            minio_public_endpoint=os.environ.get("MINIO_PUBLIC_ENDPOINT", minio_endpoint),
        )
