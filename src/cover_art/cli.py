"""Command-line interface for cover_art: fetch, normalize, upload, publish subcommands."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from ._util import slugify as _slug
from .fetch import CoverArtNotFound, download_cover, find_cover_url
from .normalize import MODES, normalize_file
from .pipeline import publish_cover
from .upload import R2Config, R2ConfigError, upload_file


def _cmd_fetch(args: argparse.Namespace) -> int:
    if args.url_only:
        url = find_cover_url(args.title, args.artist, args.year, size=args.size, country=args.country)
        if url is None:
            print(f"no album found for title={args.title!r} artist={args.artist!r} year={args.year!r}", file=sys.stderr)
            return 1
        print(url)
        return 0

    try:
        data = download_cover(args.title, args.artist, args.year, size=args.size, country=args.country)
    except CoverArtNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out = args.output or f"{_slug(args.title)}.jpg"
    Path(out).write_bytes(data)
    print(out)
    return 0


def _cmd_normalize(args: argparse.Namespace) -> int:
    try:
        dst = normalize_file(args.input, args.output, size=args.size, mode=args.mode)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(dst)
    return 0


def _cmd_upload(args: argparse.Namespace) -> int:
    try:
        config = R2Config.from_env()
    except R2ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.bucket:
        config = dataclasses.replace(config, bucket=args.bucket)

    try:
        key = upload_file(args.input, args.key, content_type=args.content_type, config=config)
    except (ClientError, BotoCoreError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(key)
    return 0


def _cmd_publish(args: argparse.Namespace) -> int:
    try:
        result = publish_cover(
            args.title,
            args.artist,
            args.year,
            size=args.size,
            mode=args.mode,
            key=args.key,
            prefix=args.prefix,
            country=args.country,
            save=args.save,
            bucket=args.bucket,
        )
    except CoverArtNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except R2ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (ClientError, BotoCoreError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    album = result.album
    year = f" ({album.year})" if album.year else ""
    print(f"{album.artist} — {album.title}{year}", file=sys.stderr)
    print(result.key)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cover-art", description="Fetch, normalize, and upload album cover art."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="find and download an album's cover art via iTunes Search")
    fetch_p.add_argument("title", help="album title")
    fetch_p.add_argument("--artist", default=None, help="artist name, narrows the match")
    fetch_p.add_argument("--year", type=int, default=None, help="release year, narrows the match")
    fetch_p.add_argument("--size", type=int, default=600, help="artwork size in pixels (default: 600)")
    fetch_p.add_argument("--country", default="US", help="iTunes storefront country code (default: US)")
    fetch_p.add_argument("-o", "--output", default=None, help="output file path (default: <slugified title>.jpg)")
    fetch_p.add_argument("--url-only", action="store_true", help="print the resolved artwork URL instead of downloading")
    fetch_p.set_defaults(func=_cmd_fetch)

    norm_p = sub.add_parser("normalize", help="normalize an image to a fixed square size")
    norm_p.add_argument("input", help="input image path")
    norm_p.add_argument("-o", "--output", required=True, help="output image path")
    norm_p.add_argument("--size", type=int, default=600, help="output size in pixels (default: 600)")
    norm_p.add_argument("--mode", choices=MODES, default="stretch", help="resize strategy (default: stretch)")
    norm_p.set_defaults(func=_cmd_normalize)

    upload_p = sub.add_parser("upload", help="upload an image to Cloudflare R2")
    upload_p.add_argument("input", help="input image path")
    upload_p.add_argument("--key", default=None, help="object key (default: input file's basename)")
    upload_p.add_argument("--bucket", default=None, help="bucket name (default: R2_BUCKET env var)")
    upload_p.add_argument("--content-type", default=None, help="MIME type (default: guessed from key)")
    upload_p.set_defaults(func=_cmd_upload)

    publish_p = sub.add_parser("publish", help="fetch, normalize, and upload an album's cover art in one call")
    publish_p.add_argument("title", help="album title")
    publish_p.add_argument("--artist", default=None, help="artist name, narrows the match")
    publish_p.add_argument("--year", type=int, default=None, help="release year, narrows the match")
    publish_p.add_argument("--country", default="US", help="iTunes storefront country code (default: US)")
    publish_p.add_argument("--size", type=int, default=600, help="output size in pixels (default: 600)")
    publish_p.add_argument("--mode", choices=MODES, default="stretch", help="resize strategy (default: stretch)")
    publish_p.add_argument("--key", default=None, help="object key (default: derived from the matched album)")
    publish_p.add_argument("--prefix", default="", help="prefix prepended to a derived key, e.g. covers/")
    publish_p.add_argument("--save", default=None, help="also write the normalized image to this local path")
    publish_p.add_argument("--bucket", default=None, help="bucket name (default: R2_BUCKET env var)")
    publish_p.set_defaults(func=_cmd_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
