"""Command-line interface for wubwub.studio: the `studio` group, init/upload/render/serve/deploy subcommands."""

from __future__ import annotations

import argparse
import sys

from ..covers import CoverArtNotFound
from .batch import render_albums
from .config import Settings
from .db import connect, ensure_schema
from .deploy import deploy_assets
from .objects import client as s3_client
from .objects import ensure_bucket
from .publish import PublishError
from .serve import DEFAULT_PORT, serve_site
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
        colors=args.colors,
        dither=args.dither,
        settings=settings,
    )
    for outcome in outcomes:
        print(outcome.gif_url)
    if failures:
        print(f"{failures} album(s) failed to render, see log", file=sys.stderr)
        return 1
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        serve_site(
            dev=args.dev,
            port=args.port,
            publish=not args.no_publish,
            site=args.site,
            remote=args.remote,
            branch=args.branch,
            # stdout gets the URL as soon as the socket is bound, not
            # after the (blocking) serve loop finally exits.
            on_start=lambda url: print(url, flush=True),
        )
    except (PublishError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _cmd_deploy(args: argparse.Namespace) -> int:
    try:
        result = deploy_assets(
            limit=args.limit,
            remote=args.remote,
            branch=args.branch,
            dry_run=args.dry_run,
            out_dir=args.output,
            no_pr=args.no_pr,
        )
    except (PublishError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if result is None:
        print("released assets already up to date", file=sys.stderr)
        return 0
    if args.dry_run:
        print(result.tree_dir)
    else:
        print(result.pr_url or result.base_url)
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
    render_p.add_argument("--colors", type=int, default=128, help="GIF palette size; lower is smaller (default: 128)")
    render_p.add_argument(
        "--dither", action="store_true", help="dither the palette mapping (larger file, smoother gradients)"
    )
    render_p.set_defaults(func=_cmd_render)

    serve_p = studio_sub.add_parser(
        "serve",
        help="serve the site/ showcase locally (prod assets by default; --dev publishes to assets-dev first)",
        parents=[logging_parent],
    )
    serve_p.add_argument(
        "--dev",
        action="store_true",
        help="force-push current assets to assets-dev and serve that channel",
    )
    serve_p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default: {DEFAULT_PORT})")
    serve_p.add_argument(
        "--no-publish", action="store_true", help="with --dev, serve assets-dev as-is without pushing"
    )
    serve_p.add_argument("--site", default=None, help="path to the site directory (default: repo's site/)")
    serve_p.add_argument("--remote", default="origin", help="git remote to push to (default: origin)")
    serve_p.add_argument(
        "--branch", default="assets-dev", help="dev branch to force-push the asset tree to (default: assets-dev)"
    )
    serve_p.set_defaults(func=_cmd_serve)

    deploy_p = studio_sub.add_parser(
        "deploy",
        help="cut a prod asset release: push a release branch off `assets` and open its PR",
        parents=[logging_parent],
    )
    deploy_p.add_argument("--limit", type=int, default=None, help="release at most N albums")
    deploy_p.add_argument("--remote", default="origin", help="git remote to push to (default: origin)")
    deploy_p.add_argument("--branch", default="assets", help="prod asset branch (default: assets)")
    deploy_p.add_argument(
        "--dry-run", action="store_true", help="write the asset tree locally, don't push or open a PR"
    )
    deploy_p.add_argument(
        "-o", "--output", default=None, help="directory to write the asset tree to (default: a temp dir)"
    )
    deploy_p.add_argument(
        "--no-pr", action="store_true", help="push the release branch but leave the PR to you"
    )
    deploy_p.set_defaults(func=_cmd_deploy)
