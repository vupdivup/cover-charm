"""Runs inside Blender's own Python interpreter -- never imported by render.

Invoked as ``blender --background <blend> --python _script.py -- --image
... --texture ... --out ...``. Swaps the named image datablock's source
file and renders the scene's animation as one PNG per frame.
"""

import argparse
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

parser = argparse.ArgumentParser()
parser.add_argument("--image", required=True)
parser.add_argument("--texture", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args(argv)

img = bpy.data.images.get(args.texture)
if img is None:
    names = [i.name for i in bpy.data.images]
    print(f"no image datablock named {args.texture!r}; found: {names}", file=sys.stderr)
    sys.exit(1)

# A packed image ignores a new filepath until unpacked -- otherwise this
# is a silent no-op and the render comes out with the original texture.
if img.packed_file:
    img.unpack(method="REMOVE")

img.filepath = args.image
img.source = "FILE"
img.reload()

scene = bpy.context.scene

if scene.render.engine == "CYCLES":
    # --factory-startup (passed by blender.py) discards the user's Cycles
    # device preferences, so the compute device has to be re-selected
    # explicitly here or the render silently falls back to CPU.
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue  # backend not compiled into this build
        prefs.get_devices()
        if any(d.type != "CPU" for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type != "CPU"
            scene.cycles.device = "GPU"
            break

# media_type gates which file_format values are legal -- a .blend authored
# for video output (media_type == "VIDEO") restricts file_format to movie
# codecs only, so PNG has to be unlocked by switching to "IMAGE" first.
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"
# Trailing "frame_" prefix is what makes Blender emit frame_0001.png etc.
# rather than treating --out as a bare directory.
scene.render.filepath = args.out.rstrip("/\\") + "/frame_"

bpy.ops.render.render(animation=True)
