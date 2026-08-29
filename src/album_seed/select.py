"""Module 2: read the dataset CSV and rank albums by a popularity count.

Uses the stdlib ``csv`` module rather than pandas -- the job is one
sort and one slice over ~5,000 rows, and pandas would be the heaviest
dependency in the whole repo for that.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from pathlib import Path

# Kaggle album datasets vary in exact header spelling across sources and
# revisions; match loosely instead of hard-coding one column name per
# kind. "count" covers both rating-count and review-count datasets --
# whichever popularity metric a given source exposes.
_COLUMN_ALIASES = {
    "count": (
        "rating_count", "rating count", "ratings", "number of ratings", "num_ratings",
        "review_count", "review count", "reviews", "number of reviews", "num_reviews",
        "votes",
    ),
    "title": ("title", "album", "album name", "release name"),
    "artist": ("artist", "artist name", "artists"),
    "year": ("release_date", "release date", "year", "released"),
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


_COUNT_RE = re.compile(r"[\d,]+")


def _to_int(value: str) -> int | None:
    """Parse a popularity-count cell, or None if it isn't a number.

    Cells aren't always a bare number -- e.g. AOTY's rating_count reads
    "28,594 ratings" -- so pull the leading digit run rather than
    parsing the whole cell. Rows with no parseable count are dropped
    rather than treated as zero -- a zero would silently sort to the
    bottom, but wouldn't be a real ranking, and could still pad out the
    tail of a small top-N.
    """
    if not value:
        return None
    match = _COUNT_RE.search(value)
    if not match:
        return None
    try:
        return int(match.group().replace(",", ""))
    except ValueError:
        return None


def top_by_count(
    rows: list[dict[str, str]], limit: int = 100, *, column: str | None = None
) -> list[dict[str, str]]:
    """Return the ``limit`` rows with the highest popularity count, descending."""
    if not rows:
        return []

    column = column or resolve_column(rows[0].keys(), "count")

    counted = [(row, _to_int(row.get(column, ""))) for row in rows]
    counted = [(row, count) for row, count in counted if count is not None]
    counted.sort(key=lambda pair: pair[1], reverse=True)

    return [row for row, _ in counted[:limit]]
