-- Local-dev bootstrap: mounted into postgres:/docker-entrypoint-initdb.d/
-- by compose.yaml, so a fresh `docker compose up` already has the table.
-- Identical to packages/album-store/src/album_store/schema.sql, which is
-- the source of truth applied by `album-store init` against any DB.

CREATE TABLE IF NOT EXISTS albums (
    id          BIGSERIAL PRIMARY KEY,
    artist      TEXT NOT NULL,
    title       TEXT NOT NULL,
    year        INT,
    cover_key   TEXT NOT NULL,
    cover_url   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Case-insensitive identity: the casing a lookup returns varies, so
-- "Kid A"/"kid a" must be one row for the upsert to work.
CREATE UNIQUE INDEX IF NOT EXISTS albums_artist_title_key
    ON albums (lower(artist), lower(title));
