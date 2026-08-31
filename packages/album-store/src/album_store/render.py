"""Batch-render stored covers into GIFs (via the render package) and store them.

Reads cover bytes back out of the covers bucket rather than re-fetching
from Cover Art Archive, so a render run only needs Postgres/MinIO.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from botocore.exceptions import ClientError

# Imported with an explicit alias -- this module is itself named
# `render`, so `import render` alone would be easy to misread as a
# self-import even though absolute imports make it unambiguous.
import render as render_pkg

from .config import Settings
from .db import StoredAlbum, albums_to_render, connect, set_album_gif
from .objects import client as s3_client
from .objects import ensure_bucket, get_object, gif_key, preview_key, put_object

logger = logging.getLogger(__name__)

__all__ = ["RenderOutcome", "render_albums"]

_RENDER_ERRORS = (render_pkg.BlenderError, render_pkg.GifError, ValueError, OSError, ClientError)


@dataclass(frozen=True)
class RenderOutcome:
    album_id: int
    artist: str
    title: str
    gif_url: str
    preview_url: str


def _render_one(
    album: StoredAlbum,
    *,
    s3,
    conn,
    settings: Settings,
    blend: str | Path,
    material: str,
    fps: float,
    blender: str | Path | None,
) -> RenderOutcome:
    with tempfile.TemporaryDirectory(prefix="album-store-render-") as tmp:
        tmp_dir = Path(tmp)
        cover_bytes = get_object(s3, settings.minio_bucket, album.cover_key)
        image_path = tmp_dir / "cover.jpg"
        image_path.write_bytes(cover_bytes)

        # render_gif resolves a relative `output` (and `preview_output`)
        # against the process CWD and returns RenderResult paths
        # unresolved, so both must be absolute.
        gif_path = tmp_dir / "cover.gif"
        preview_path = tmp_dir / "preview.gif"
        result = render_pkg.render_gif(
            blend,
            image_path,
            material=material,
            output=gif_path,
            preview_output=preview_path,
            fps=fps,
            blender=blender,
        )
        gif_data = result.gif.read_bytes()
        preview_data = result.preview.read_bytes()
        logger.debug(
            "rendered %d bytes (+%d preview) for album id=%s (%d frame(s))",
            len(gif_data),
            len(preview_data),
            album.id,
            len(result.frames),
        )

    key = gif_key(album.artist, album.title)
    gif_url = put_object(s3, settings, settings.minio_gif_bucket, key, gif_data, content_type="image/gif")

    prev_key = preview_key(album.artist, album.title)
    preview_url = put_object(
        s3, settings, settings.minio_gif_bucket, prev_key, preview_data, content_type="image/gif"
    )

    set_album_gif(
        conn, album.id, gif_key=key, gif_url=gif_url, preview_key=prev_key, preview_url=preview_url
    )

    logger.info(
        "rendered album id=%s %r by %r -> %s (preview -> %s)",
        album.id,
        album.title,
        album.artist,
        gif_url,
        preview_url,
    )
    return RenderOutcome(
        album_id=album.id, artist=album.artist, title=album.title, gif_url=gif_url, preview_url=preview_url
    )


def render_albums(
    *,
    blend: str | Path,
    material: str,
    all: bool = False,
    fps: float = 24.0,
    limit: int | None = None,
    blender: str | Path | None = None,
    settings: Settings | None = None,
) -> tuple[list[RenderOutcome], int]:
    """Render GIFs for stored albums missing one (or every album if all=True).

    One album failing (bad material name, missing cover object, Blender
    error) is logged and skipped rather than aborting the whole run --
    returns (successes, failure_count).
    """
    settings = settings or Settings.from_env()
    s3 = s3_client(settings)
    ensure_bucket(s3, settings, settings.minio_gif_bucket)

    with connect(settings) as conn:
        albums = albums_to_render(conn, all=all, limit=limit)
        logger.info("%d album(s) to render", len(albums))

        outcomes: list[RenderOutcome] = []
        failures = 0
        for album in albums:
            try:
                outcomes.append(
                    _render_one(
                        album,
                        s3=s3,
                        conn=conn,
                        settings=settings,
                        blend=blend,
                        material=material,
                        fps=fps,
                        blender=blender,
                    )
                )
            except _RENDER_ERRORS as exc:
                failures += 1
                logger.error("failed to render album id=%s %r by %r: %s", album.id, album.title, album.artist, exc)

    logger.info("render run complete: %d rendered, %d failed", len(outcomes), failures)
    return outcomes, failures
