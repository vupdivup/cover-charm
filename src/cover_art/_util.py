"""Small internal helpers shared across cover_art modules."""

from __future__ import annotations

import re


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "cover"
