"""Command-line interface for album_seed: download, select, export, top subcommands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .download import DATASET, DEFAULT_CSV_NAME, DatasetError, dataset_csv
from .export import to_albums, to_json, write_json
from .pipeline import top_albums
from .select import ColumnNotFound, load_rows, top_by_count


def _cmd_download(args: argparse.Namespace) -> int:
    try:
        path = dataset_csv(args.dataset, force=args.force, name=args.csv_name)
    except DatasetError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(path)
    return 0


def _cmd_select(args: argparse.Namespace) -> int:
    try:
        rows = load_rows(args.input)
        top = top_by_count(rows, args.limit)
    except ColumnNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    text = json.dumps(top, indent=2)
    if args.output:
        Path(args.output).write_text(text)
        print(args.output)
    else:
        print(text)
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    try:
        if args.input == "-":
            rows = json.load(sys.stdin)
        else:
            rows = load_rows(args.input)
        albums = to_albums(rows)
    except ColumnNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.output:
        write_json(albums, args.output)
        print(args.output)
    else:
        print(to_json(albums))
    return 0


def _cmd_top(args: argparse.Namespace) -> int:
    try:
        albums = top_albums(
            args.limit, dataset=args.dataset, csv_name=args.csv_name, path=args.input, force=args.force
        )
    except (DatasetError, ColumnNotFound) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"{len(albums)} albums", file=sys.stderr)
    if args.output:
        write_json(albums, args.output)
        print(args.output)
    else:
        print(to_json(albums))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="album-seed", description="Download an album-ratings dataset and export the top-rated albums."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    download_p = sub.add_parser("download", help="download (or reuse the cached copy of) the dataset")
    download_p.add_argument("--dataset", default=DATASET, help=f"Kaggle dataset slug (default: {DATASET})")
    download_p.add_argument(
        "--csv-name", default=DEFAULT_CSV_NAME, help=f"CSV filename to pick when the dataset ships more than one (default: {DEFAULT_CSV_NAME})"
    )
    download_p.add_argument("--force", action="store_true", help="re-download even if a cached copy exists")
    download_p.set_defaults(func=_cmd_download)

    select_p = sub.add_parser("select", help="rank dataset rows by popularity count and take the top N")
    select_p.add_argument("--input", required=True, help="path to the dataset CSV")
    select_p.add_argument("-n", "--limit", type=int, default=100, help="number of rows to keep (default: 100)")
    select_p.add_argument("-o", "--output", default=None, help="write JSON to this file instead of stdout")
    select_p.set_defaults(func=_cmd_select)

    export_p = sub.add_parser("export", help="map dataset rows to cover_art's album shape")
    export_p.add_argument("--input", required=True, help="path to a dataset CSV, or '-' for a JSON row array on stdin")
    export_p.add_argument("-o", "--output", default=None, help="write JSON to this file instead of stdout")
    export_p.set_defaults(func=_cmd_export)

    top_p = sub.add_parser("top", help="download, rank, and export the top N albums in one call")
    top_p.add_argument("-n", "--limit", type=int, default=100, help="number of albums to keep (default: 100)")
    top_p.add_argument("--dataset", default=DATASET, help=f"Kaggle dataset slug (default: {DATASET})")
    top_p.add_argument(
        "--csv-name", default=DEFAULT_CSV_NAME, help=f"CSV filename to pick when the dataset ships more than one (default: {DEFAULT_CSV_NAME})"
    )
    top_p.add_argument("--input", default=None, help="use this CSV instead of downloading")
    top_p.add_argument("--force", action="store_true", help="re-download even if a cached copy exists")
    top_p.add_argument("-o", "--output", default=None, help="write JSON to this file instead of stdout")
    top_p.set_defaults(func=_cmd_top)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
