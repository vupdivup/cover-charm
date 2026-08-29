"""Module 3: map raw dataset rows to the album shape cover_art expects.

Standalone, like cover_art's own ``upload.py`` -- this module knows the
target *shape* (``{"title", "artist", "year"}``), not the ``cover_art``
package itself, and does not import from it. Those keys match
``cover_art.pipeline._normalize_item``'s dict form exactly: ``title``
required, ``artist``/``year`` optional.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .select import resolve_column

_YEAR_RE = re.compile(r"\d{4}")


@dataclass(frozen=True)
class AlbumRecord:
    """One album in cover_art's input shape."""

    title: str
    artist: str | None
    year: int | None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _parse_year(value: str | None) -> int | None:
    # RYM release-date cells come through as e.g. "17 August 1959" or a
    # bare "1959" -- pull the first 4-digit run rather than parsing a
    # full date format. None (rather than 0) so publish_covers treats a
    # missing year as "don't filter" instead of a real mismatch.
    if not value:
        return None
    match = _YEAR_RE.search(value)
    return int(match.group()) if match else None


def to_albums(
    rows: Iterable[Mapping[str, str]], *, columns: Mapping[str, str] | None = None
) -> list[dict]:
    """Map raw CSV rows to a list of ``{"title", "artist", "year"}`` dicts."""
    rows = list(rows)
    if not rows:
        return []

    columns = dict(columns) if columns else {}
    title_col = columns.get("title") or resolve_column(rows[0].keys(), "title")
    artist_col = columns.get("artist") or resolve_column(rows[0].keys(), "artist")
    year_col = columns.get("year") or resolve_column(rows[0].keys(), "year")

    records = [
        AlbumRecord(
            title=row[title_col],
            artist=row.get(artist_col) or None,
            year=_parse_year(row.get(year_col)),
        )
        for row in rows
    ]
    return [r.to_dict() for r in records]


def to_json(albums: Sequence[Mapping], *, indent: int = 2) -> str:
    """Serialize a list of album dicts to a JSON string."""
    return json.dumps(list(albums), indent=indent)


def write_json(albums: Sequence[Mapping], path: str | Path, *, indent: int = 2) -> Path:
    """Write a list of album dicts to ``path`` as JSON. Returns ``path``."""
    path = Path(path)
    path.write_text(to_json(albums, indent=indent))
    return path
