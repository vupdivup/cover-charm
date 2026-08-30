"""Command-line interface for album_store: init and upload subcommands."""

from __future__ import annotations

import argparse
import logging
import sys

from album_covers import CoverArtNotFound

from .config import Settings
from .db import connect, ensure_schema
from .objects import client as s3_client
from .objects import ensure_bucket
from .upload import upload_album


def _cmd_init(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    with connect(settings) as conn:
        ensure_schema(conn)
    ensure_bucket(s3_client(settings), settings)
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


def _configure_logging(args: argparse.Namespace) -> None:
    """Set up the root handler once, level driven by -v/-q. Library code never does this itself."""
    if args.quiet:
        level = logging.ERROR
    elif args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(stream=sys.stderr, level=level, format="%(levelname)s: %(message)s")


def _add_logging_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="increase logging detail (-v info, -vv debug)"
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only log errors")


def build_parser() -> argparse.ArgumentParser:
    # logging_parent added to top-level AND each subparser -- lets -v/-q
    # land either before or after the subcommand.
    logging_parent = argparse.ArgumentParser(add_help=False)
    _add_logging_args(logging_parent)

    parser = argparse.ArgumentParser(
        prog="album-store",
        description="Fetch album cover art and persist it (Postgres metadata + MinIO/S3 objects).",
        parents=[logging_parent],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser(
        "init",
        help="create the albums table and object bucket if they don't exist",
        parents=[logging_parent],
    )
    init_p.set_defaults(func=_cmd_init)

    upload_p = sub.add_parser(
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
