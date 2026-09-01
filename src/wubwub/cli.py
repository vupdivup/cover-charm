"""Top-level command-line interface for wubwub: covers, render, studio groups."""

from __future__ import annotations

import argparse
import logging
import sys

from .covers import cli as covers_cli
from .render import cli as render_cli
from .studio import cli as studio_cli


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
    # logging_parent added to the top-level parser AND every subparser --
    # lets -v/-q land anywhere in the command line, regardless of how
    # deep the subcommand nesting goes.
    logging_parent = argparse.ArgumentParser(add_help=False)
    _add_logging_args(logging_parent)

    parser = argparse.ArgumentParser(
        prog="wubwub",
        description="Fetch album cover art, render it through a Blender animation, and publish the results.",
        parents=[logging_parent],
    )
    sub = parser.add_subparsers(dest="group", required=True)

    covers_cli.register(sub, logging_parent)
    render_cli.register(sub, logging_parent)
    studio_cli.register(sub, logging_parent)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
