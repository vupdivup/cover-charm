"""Command-line interface for album_covers: fetch subcommand."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ._util import slugify as _slug
from .fetch import CoverArtNotFound, download_cover, find_cover_url


def _cmd_fetch(args: argparse.Namespace) -> int:
    if args.url_only:
        url = find_cover_url(args.title, args.artist, size=args.size)
        if url is None:
            print(f"no album found for title={args.title!r} artist={args.artist!r}", file=sys.stderr)
            return 1
        print(url)
        return 0

    try:
        data = download_cover(args.title, args.artist, size=args.size)
    except CoverArtNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out = args.output or f"{_slug(args.title)}.jpg"
    Path(out).write_bytes(data)
    print(out)
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
        prog="album-covers",
        description="Fetch album cover art from MusicBrainz + Cover Art Archive.",
        parents=[logging_parent],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser(
        "fetch",
        help="find and download an album's cover art via MusicBrainz + Cover Art Archive",
        parents=[logging_parent],
    )
    fetch_p.add_argument("title", help="album title")
    fetch_p.add_argument("--artist", default=None, help="artist name, narrows the match")
    fetch_p.add_argument(
        "--size",
        type=int,
        default=600,
        help="artwork size in pixels, snapped to the nearest available (250/500/1200) (default: 600)",
    )
    fetch_p.add_argument("-o", "--output", default=None, help="output file path (default: <slugified title>.jpg)")
    fetch_p.add_argument("--url-only", action="store_true", help="print the resolved artwork URL instead of downloading")
    fetch_p.set_defaults(func=_cmd_fetch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
