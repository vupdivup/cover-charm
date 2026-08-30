"""Runs inside Blender's own Python interpreter -- never imported by render.

Invoked as ``blender --background <blend> --python _script.py -- --image
... --material ... --out ...``. Swaps the image on the named material's
image texture node and renders the scene's animation as one PNG per
frame.
"""

import argparse
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

parser = argparse.ArgumentParser()
parser.add_argument("--image", required=True)
parser.add_argument("--material", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args(argv)

# A material name is what a user can actually find in Blender's UI (top of
# the Properties > Material tab, and the Outliner) without digging into the
# Shader Editor to read off an image datablock's name.
mat = bpy.data.materials.get(args.material)
if mat is None or not mat.use_nodes:
    names = [m.name for m in bpy.data.materials if m.use_nodes]
    print(f"no material named {args.material!r}; found: {names}", file=sys.stderr)
    sys.exit(1)

tex_nodes = [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
if not tex_nodes:
    print(f"material {args.material!r} has no image texture node", file=sys.stderr)
    sys.exit(1)
if len(tex_nodes) > 1:
    names = [n.name for n in tex_nodes]
    print(f"material {args.material!r} has multiple image texture nodes: {names}", file=sys.stderr)
    sys.exit(1)

img = tex_nodes[0].image

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
