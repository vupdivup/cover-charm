"""MinIO/S3 object storage for cover images, via boto3's S3 client.

boto3 is used rather than the MinIO-specific SDK so this code works
unchanged against real S3 later -- MinIO speaks the same API.
"""

from __future__ import annotations

import json
import logging
import re

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import Settings

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    # Local rather than reused from album_covers._util.slugify -- that
    # module is private to album_covers, and this is a two-line rule.
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "x"


def cover_key(artist: str, title: str) -> str:
    return f"covers/{_slug(artist)}/{_slug(title)}.jpg"


def gif_key(artist: str, title: str) -> str:
    return f"gifs/{_slug(artist)}/{_slug(title)}.gif"


def client(settings: Settings):
    """Build an S3 client pointed at the configured MinIO endpoint."""
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        # botocore's SigV4 signer requires a region even though MinIO
        # ignores it.
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket(s3_client, settings: Settings, bucket: str) -> None:
    """Create bucket (with anonymous read) if it doesn't exist."""
    try:
        s3_client.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status != 404:
            raise

    logger.warning("bucket %r not found, creating it", bucket)
    s3_client.create_bucket(Bucket=bucket)

    # Public read so a stored *_url is a plain fetchable link instead of
    # needing a presigned URL generated on every read. Fine for local
    # dev; a real deployment would front this with a CDN/presigning instead.
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*",
            }
        ],
    }
    s3_client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))


def put_object(s3_client, settings: Settings, bucket: str, key: str, data: bytes, *, content_type: str) -> str:
    """Upload bytes under key in bucket, return its public URL."""
    s3_client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    logger.debug("uploaded %d bytes to %s/%s", len(data), bucket, key)
    return f"{settings.minio_public_endpoint.rstrip('/')}/{bucket}/{key}"


def get_object(s3_client, bucket: str, key: str) -> bytes:
    """Download an object's raw bytes from bucket."""
    data = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
    logger.debug("downloaded %d bytes from %s/%s", len(data), bucket, key)
    return data
