"""Command-line interface for album_covers: fetch subcommand."""

from __future__ import annotations

import argparse
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="album-covers", description="Fetch album cover art from MusicBrainz + Cover Art Archive."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="find and download an album's cover art via MusicBrainz + Cover Art Archive")
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
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
