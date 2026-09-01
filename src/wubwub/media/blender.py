"""Locate a Blender install and drive it in background mode.

Runs Blender as a subprocess rather than importing ``bpy`` directly --
``bpy`` wheels are pinned to one exact Python version and are ~300MB,
while a background Blender install is something most users already
have. The in-Blender side of this lives in ``_script.py``, which runs
under Blender's own bundled Python (currently 3.13), not this venv.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from pathlib import Path

BLENDER_TIMEOUT = 3600  # seconds; tunable, read at call time

_SCRIPT = Path(__file__).with_name("_script.py")

# Tried in order, absolute and platform-specific; a pattern for the wrong OS
# just matches nothing, so there's no need to branch on platform.system()
# first -- glob.glob() is already a no-op on paths that don't exist.
_INSTALL_GLOBS = (
    "/mnt/*/Program Files/Blender Foundation/*/blender.exe",  # WSL
    "/mnt/*/Program Files (x86)/Blender Foundation/*/blender.exe",
    "C:/Program Files/Blender Foundation/*/blender.exe",  # Windows
    "C:/Program Files (x86)/Blender Foundation/*/blender.exe",
    "/Applications/Blender.app/Contents/MacOS/Blender",  # macOS
    "/opt/blender*/blender",  # Linux
    "/usr/share/blender/*/blender",
)


class BlenderError(Exception):
    """Raised when Blender cannot be located or exits with an error."""


def _version_key(path: str) -> tuple[int, ...]:
    """Parse a version out of a Blender install path, for newest-last sorting."""
    match = re.search(r"(\d+)\.(\d+)", str(path))
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def find_blender(explicit: str | Path | None = None) -> Path:
    """Locate a Blender executable.

    Checked in order: ``explicit``, the ``BLENDER`` env var, ``blender``
    / ``blender.exe`` on ``PATH``, then the default install locations for
    Windows, WSL, macOS, and Linux (newest version wins). Raises
    BlenderError listing everywhere it looked if nothing is found.
    """
    checked = []

    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        checked.append(str(path))

    env = os.environ.get("BLENDER")
    if env:
        path = Path(env)
        if path.is_file():
            return path
        checked.append(path.as_posix())

    for name in ("blender", "blender.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
        checked.append(f"{name!r} on PATH")

    candidates = [match for pattern in _INSTALL_GLOBS for match in glob.glob(pattern)]
    if candidates:
        return Path(max(candidates, key=_version_key))
    checked.extend(_INSTALL_GLOBS)

    raise BlenderError("could not find a Blender install; checked: " + ", ".join(checked))


def needs_wslpath(blender: Path) -> bool:
    """Whether paths must be translated before being handed to Blender.

    Only WSL mixes a POSIX host with a Windows Blender binary -- native
    Windows and native Linux/macOS Blender both take paths already
    spelled the way they expect.
    """
    return os.name != "nt" and blender.suffix.lower() == ".exe"


def to_blender_path(path: str | Path, *, translate: bool) -> str:
    """Respell a path for Blender's consumption, translating only under WSL."""
    if not translate:
        return str(path)
    result = subprocess.run(
        ["wslpath", "-w", str(path)], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def render_frames(
    blend: str | Path,
    image: str | Path,
    *,
    material: str,
    out_dir: str | Path,
    blender: str | Path | None = None,
) -> list[Path]:
    """Open ``blend`` in Blender, swap in ``image`` for ``material``'s image texture node, and render every frame as a PNG into ``out_dir``.

    Runs Blender with ``--background``, so nothing is displayed and the
    ``.blend`` on disk is never written back to.
    """
    exe = find_blender(blender)
    translate = needs_wslpath(exe)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    argv = [
        str(exe),
        "--background",
        # Ignores the user's local Blender preferences/add-ons -- besides
        # making a headless batch render reproducible, loading a real
        # profile has been observed to crash this codepath outright on at
        # least one install.
        "--factory-startup",
        to_blender_path(blend, translate=translate),
        "--python",
        to_blender_path(_SCRIPT, translate=translate),
        "--",
        "--image",
        to_blender_path(image, translate=translate),
        "--material",
        material,
        "--out",
        to_blender_path(out_dir, translate=translate),
    ]

    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=BLENDER_TIMEOUT
        )
    except FileNotFoundError as exc:
        raise BlenderError(f"failed to run Blender at {exe}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BlenderError(f"Blender timed out after {BLENDER_TIMEOUT}s rendering {blend}") from exc

    if result.returncode != 0:
        # Blender's stderr is noisy (startup banners, driver warnings); the
        # actionable error is almost always in the last few lines.
        tail = "\n".join(result.stderr.strip().splitlines()[-20:])
        raise BlenderError(f"Blender exited {result.returncode} rendering {blend}:\n{tail}")

    frames = sorted(out_dir.glob("*.png"))
    if not frames:
        # Blender exits 0 having rendered nothing when the frame range is
        # degenerate (e.g. start > end), so an empty result is still an error.
        raise BlenderError(f"Blender produced no frames in {out_dir}")

    return frames
