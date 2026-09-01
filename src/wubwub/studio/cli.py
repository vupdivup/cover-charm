"""Command-line interface for wubwub.studio: the `studio` group, init/upload/render/publish subcommands."""

from __future__ import annotations

import argparse
import sys

from ..covers import CoverArtNotFound
from .batch import render_albums
from .config import Settings
from .db import connect, ensure_schema
from .objects import client as s3_client
from .objects import ensure_bucket
from .publish import PublishError, publish_assets
from .upload import upload_album


def _cmd_init(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    with connect(settings) as conn:
        ensure_schema(conn)
    ensure_bucket(s3_client(settings), settings, settings.minio_bucket)
    ensure_bucket(s3_client(settings), settings, settings.minio_gif_bucket)
    print("ready")
    return 0


def _cmd_upload(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    try:
        stored = upload_album(args.title, args.artist, size=args.size, settings=settings)
    except CoverArtNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(stored.cover_url)
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    outcomes, failures = render_albums(
        blend=args.blend,
        material=args.material,
        all=args.all,
        fps=args.fps,
        limit=args.limit,
        blender=args.blender,
        settings=settings,
    )
    for outcome in outcomes:
        print(outcome.gif_url)
    if failures:
        print(f"{failures} album(s) failed to render, see log", file=sys.stderr)
        return 1
    return 0


def _cmd_publish(args: argparse.Namespace) -> int:
    try:
        result = publish_assets(
            limit=args.limit,
            remote=args.remote,
            branch=args.branch,
            dry_run=args.dry_run,
            out_dir=args.output,
        )
    except (PublishError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(result.tree_dir if args.dry_run else result.base_url)
    return 0


def register(sub: argparse._SubParsersAction, logging_parent: argparse.ArgumentParser) -> None:
    """Attach the `studio` command group to the top-level parser."""
    studio_p = sub.add_parser(
        "studio",
        help="fetch album cover art and persist it (Postgres metadata + MinIO/S3 objects)",
        parents=[logging_parent],
    )
    studio_sub = studio_p.add_subparsers(dest="command", required=True)

    init_p = studio_sub.add_parser(
        "init",
        help="create the albums table and object bucket if they don't exist",
        parents=[logging_parent],
    )
    init_p.set_defaults(func=_cmd_init)

    upload_p = studio_sub.add_parser(
        "upload",
        help="fetch an album's cover and store it (idempotent on artist+title)",
        parents=[logging_parent],
    )
    upload_p.add_argument("title", help="album title")
    upload_p.add_argument("--artist", default=None, help="artist name, narrows the match")
    upload_p.add_argument(
        "--size",
        type=int,
        default=600,
        help="artwork size in pixels, snapped to the nearest available (250/500/1200) (default: 600)",
    )
    upload_p.set_defaults(func=_cmd_upload)

    render_p = studio_sub.add_parser(
        "render",
        help="render stored covers into GIFs and store them (batch; skips albums already rendered)",
        parents=[logging_parent],
    )
    render_p.add_argument("--blend", required=True, help="path to the Blender animation file")
    render_p.add_argument("--material", required=True, help="material whose image texture gets swapped")
    render_p.add_argument(
        "--all", action="store_true", help="re-render every album, not just ones missing a GIF"
    )
    render_p.add_argument("--fps", type=float, default=24.0, help="GIF frame rate (default: 24.0)")
    render_p.add_argument("--limit", type=int, default=None, help="render at most N albums")
    render_p.add_argument("--blender", default=None, help="path to the Blender executable")
    render_p.set_defaults(func=_cmd_render)

    publish_p = studio_sub.add_parser(
        "publish",
        help="push rendered GIFs to a git branch for jsDelivr CDN serving",
        parents=[logging_parent],
    )
    publish_p.add_argument("--limit", type=int, default=None, help="publish at most N albums")
    publish_p.add_argument("--remote", default="origin", help="git remote to push to (default: origin)")
    publish_p.add_argument(
        "--branch", default="assets-dev", help="branch to force-push the asset tree to (default: assets-dev)"
    )
    publish_p.add_argument(
        "--dry-run", action="store_true", help="write the asset tree locally, don't push or purge"
    )
    publish_p.add_argument(
        "-o", "--output", default=None, help="directory to write the asset tree to (default: a temp dir)"
    )
    publish_p.set_defaults(func=_cmd_publish)
