-- Source of truth, applied by `wubwub studio init` against any DB.
-- Identical to sql/init.sql, the local-dev bootstrap mounted into
-- postgres:/docker-entrypoint-initdb.d/ by compose.yaml.

CREATE TABLE IF NOT EXISTS albums (
    id          BIGSERIAL PRIMARY KEY,
    artist      TEXT NOT NULL,
    title       TEXT NOT NULL,
    year        INT,
    cover_key   TEXT NOT NULL,
    cover_url   TEXT NOT NULL,
    gif_key     TEXT,
    gif_url     TEXT,
    preview_key TEXT,
    preview_url TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Case-insensitive identity: the casing a lookup returns varies, so
-- "Kid A"/"kid a" must be one row for the upsert to work.
CREATE UNIQUE INDEX IF NOT EXISTS albums_artist_title_key
    ON albums (lower(artist), lower(title));
