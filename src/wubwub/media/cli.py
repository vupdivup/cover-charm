"""Command-line interface for wubwub.media: the `media` group, `render` subcommand."""

from __future__ import annotations

import argparse
import sys

from . import BlenderError, GifError, render_gif


def _cmd_render(args: argparse.Namespace) -> int:
    try:
        result = render_gif(
            args.blend,
            args.image,
            material=args.material,
            output=args.output,
            fps=args.fps,
            keep_frames=args.keep_frames,
            blender=args.blender,
            preview=args.preview,
            preview_output=args.preview_output,
        )
    except (BlenderError, GifError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.preview:
        print("1 frame (preview)", file=sys.stderr)
    else:
        print(f"{len(result.frames)} frames at {result.fps} fps", file=sys.stderr)
    if result.preview is not None:
        print(f"preview: {result.preview}", file=sys.stderr)
    print(result.gif)
    return 0


def register(sub: argparse._SubParsersAction, logging_parent: argparse.ArgumentParser) -> None:
    """Attach the `media` command group to the top-level parser."""
    media_p = sub.add_parser(
        "media",
        help="render a Blender animation with a swapped-in image texture, and assemble it into a GIF",
        parents=[logging_parent],
    )
    media_sub = media_p.add_subparsers(dest="command", required=True)

    render_p = media_sub.add_parser(
        "render",
        help="render a .blend animation with a swapped-in image texture into a GIF",
        parents=[logging_parent],
    )
    render_p.add_argument("blend", help="path to the .blend file")
    render_p.add_argument("--image", required=True, help="image to swap into the texture")
    render_p.add_argument("--material", required=True, help="name of the material whose image texture to replace")
    render_p.add_argument("-o", "--output", default=None, help="output GIF path (default: <blend stem>.gif)")
    render_p.add_argument("--fps", type=float, default=24.0, help="GIF frame rate (default: 24)")
    render_p.add_argument("--keep-frames", action="store_true", help="keep the rendered PNG frames next to the GIF")
    render_p.add_argument("--blender", default=None, help="path to the Blender executable (default: auto-detected)")
    render_p.add_argument("--preview", action="store_true", help="write only the first frame as a single-frame GIF")
    render_p.add_argument("--preview-output", default=None, help="also write a single-frame preview GIF to this path")
    render_p.set_defaults(func=_cmd_render)
