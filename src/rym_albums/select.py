"""Module 2: read the dataset CSV and rank albums by review count.

Uses the stdlib ``csv`` module rather than pandas -- the job is one
sort and one slice over ~5,000 rows, and pandas would be the heaviest
dependency in the whole repo for that.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

# Kaggle RYM datasets vary in exact header spelling across uploads/revisions;
# match loosely instead of hard-coding one column name per kind.
_COLUMN_ALIASES = {
    "reviews": ("number of reviews", "reviews", "review_count", "num_reviews"),
    "title": ("album", "album name", "title", "release name"),
    "artist": ("artist name", "artist", "artists"),
    "year": ("release date", "year", "release_date", "released"),
}


class ColumnNotFound(Exception):
    """Raised when no header in the CSV matches a required column kind."""


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", " ")


def load_rows(path: str | Path) -> list[dict[str, str]]:
    """Read the dataset CSV into a list of row dicts, keyed by its own headers."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resolve_column(fieldnames: Sequence[str], kind: str) -> str:
    """Find the actual header in ``fieldnames`` matching ``kind`` (e.g. 'reviews')."""
    aliases = _COLUMN_ALIASES.get(kind)
    if aliases is None:
        raise ValueError(f"unknown column kind {kind!r}, expected one of {tuple(_COLUMN_ALIASES)}")

    normalized = {_normalize(f): f for f in fieldnames}
    for alias in aliases:
        if _normalize(alias) in normalized:
            return normalized[_normalize(alias)]

    raise ColumnNotFound(f"no column for {kind!r} among headers: {list(fieldnames)}")


def _to_int(value: str) -> int | None:
    """Parse a review-count cell, or None if it isn't a number.

    Rows with an unparseable count are dropped rather than treated as
    zero -- a zero would silently sort to the bottom, but wouldn't be a
    real ranking, and could still pad out the tail of a small top-N.
    """
    try:
        return int(value.replace(",", "").strip())
    except (AttributeError, ValueError):
        return None


def top_by_reviews(
    rows: list[dict[str, str]], limit: int = 100, *, column: str | None = None
) -> list[dict[str, str]]:
    """Return the ``limit`` rows with the highest review count, descending."""
    if not rows:
        return []

    column = column or resolve_column(rows[0].keys(), "reviews")

    counted = [(row, _to_int(row.get(column, ""))) for row in rows]
    counted = [(row, count) for row, count in counted if count is not None]
    counted.sort(key=lambda pair: pair[1], reverse=True)

    return [row for row, _ in counted[:limit]]
