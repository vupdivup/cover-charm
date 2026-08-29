"""Module 4: tie download, select, and export together into one call.

Only module in this package that imports the other three -- download,
select, and export stay independent of each other, same rule as
cover_art's own pipeline.py.
"""

from __future__ import annotations

from pathlib import Path

from .download import DATASET, DEFAULT_CSV_NAME, dataset_csv
from .export import to_albums
from .select import load_rows, top_by_reviews


def top_albums(
    limit: int = 100,
    *,
    dataset: str = DATASET,
    csv_name: str | None = DEFAULT_CSV_NAME,
    path: str | Path | None = None,
    force: bool = False,
) -> list[dict]:
    """Download the RYM dataset, take the top ``limit`` albums by review count.

    ``path``, when given, skips the download and reads that CSV
    instead -- lets an already-downloaded dataset be used offline.
    Returns a list of ``{"title", "artist", "year"}`` dicts, ready for
    ``cover_art.pipeline.publish_covers``.
    """
    csv_path = Path(path) if path is not None else dataset_csv(dataset, force=force, name=csv_name)
    rows = load_rows(csv_path)
    top = top_by_reviews(rows, limit)
    return to_albums(top)
