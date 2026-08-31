"""Command-line interface for render: blend + image -> GIF."""

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
        )
    except (BlenderError, GifError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.preview:
        print("1 frame (preview)", file=sys.stderr)
    else:
        print(f"{len(result.frames)} frames at {result.fps} fps", file=sys.stderr)
    print(result.gif)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render", description="Render a Blender animation with a swapped-in image texture, and assemble it into a GIF."
    )
    parser.add_argument("blend", help="path to the .blend file")
    parser.add_argument("--image", required=True, help="image to swap into the texture")
    parser.add_argument("--material", required=True, help="name of the material whose image texture to replace")
    parser.add_argument("-o", "--output", default=None, help="output GIF path (default: <blend stem>.gif)")
    parser.add_argument("--fps", type=float, default=24.0, help="GIF frame rate (default: 24)")
    parser.add_argument("--keep-frames", action="store_true", help="keep the rendered PNG frames next to the GIF")
    parser.add_argument("--blender", default=None, help="path to the Blender executable (default: auto-detected)")
    parser.add_argument("--preview", action="store_true", help="write only the first frame as a single-frame GIF")
    parser.set_defaults(func=_cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
