"""Postgres access, plain psycopg3 + SQL -- no ORM for one table."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import resources

import psycopg

from .config import Settings

logger = logging.getLogger(__name__)

_UPSERT_SQL = """
INSERT INTO albums (artist, title, year, cover_key, cover_url)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (lower(artist), lower(title)) DO UPDATE SET
    year = EXCLUDED.year,
    cover_key = EXCLUDED.cover_key,
    cover_url = EXCLUDED.cover_url,
    updated_at = now()
RETURNING id, artist, title, year, cover_key, cover_url;
"""


@dataclass(frozen=True)
class StoredAlbum:
    id: int
    artist: str
    title: str
    year: int | None
    cover_key: str
    cover_url: str


def connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(settings.database_url)


def ensure_schema(conn: psycopg.Connection) -> None:
    """Create the albums table/index if they don't exist yet.

    Lets `album-store init` (or first library use) work against a bare
    Postgres instance that wasn't bootstrapped from sql/init.sql.
    """
    schema_sql = resources.files(__package__).joinpath("schema.sql").read_text()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    logger.info("schema ensured")


def upsert_album(
    conn: psycopg.Connection,
    *,
    artist: str,
    title: str,
    year: int | None,
    cover_key: str,
    cover_url: str,
) -> StoredAlbum:
    with conn.cursor() as cur:
        cur.execute(_UPSERT_SQL, (artist, title, year, cover_key, cover_url))
        row = cur.fetchone()
    conn.commit()
    logger.debug("upserted album id=%s artist=%r title=%r", row[0], row[1], row[2])
    return StoredAlbum(*row)
