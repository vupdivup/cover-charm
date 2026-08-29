"""Module 1: download an album-ratings dataset from Kaggle.

``kagglehub`` handles auth -- the ``KAGGLE_API_TOKEN`` env var (current
single-token scheme) or the legacy ``KAGGLE_USERNAME``/``KAGGLE_KEY``
env vars -- and local caching, so a second ``dataset_download`` call
for the same slug is free: it just returns the same cache directory
without re-fetching.

Env vars only, no credentials file, matching the R2_* rule in
CLAUDE.md -- so nothing here ever writes a secret to disk.
"""

from __future__ import annotations

from pathlib import Path

import kagglehub

# Public tunables, like fetch.SEARCH_INTERVAL -- override by reassignment
# or via the CLI's --dataset/--csv-name flags. Column names aren't
# documented, so they're resolved at runtime; see select.py's
# _COLUMN_ALIASES. The default dataset ships exactly one CSV, so there's
# nothing to disambiguate; DEFAULT_CSV_NAME stays available for a
# --dataset override that ships more than one (see find_csv).
DATASET = "tabibyte/aoty-5000-highest-user-rated-albums"
DEFAULT_CSV_NAME = None


class DatasetError(Exception):
    """Raised when the dataset can't be downloaded or its CSV can't be located."""


def download_dataset(dataset: str = DATASET, *, force: bool = False) -> Path:
    """Download (or reuse the cached copy of) a Kaggle dataset. Returns its local directory."""
    try:
        path = kagglehub.dataset_download(dataset, force_download=force)
    except Exception as exc:
        # "no credentials" is the failure users will actually hit here --
        # kagglehub's own error rarely says so plainly.
        raise DatasetError(
            f"couldn't download dataset {dataset!r}: {exc}. Check Kaggle credentials -- "
            "KAGGLE_API_TOKEN env var, or KAGGLE_USERNAME/KAGGLE_KEY env vars (legacy)."
        ) from exc
    return Path(path)


def find_csv(directory: str | Path, *, name: str | None = None) -> Path:
    """Locate the dataset's CSV file within ``directory``.

    A lone CSV is always used regardless of ``name``. With more than
    one, ``name`` picks which; without it (or if ``name`` doesn't match
    any of them), the ambiguity is an error listing what's there.
    """
    directory = Path(directory)

    csvs = sorted(directory.glob("*.csv"))
    if not csvs:
        raise DatasetError(f"no CSV files found in {directory}")
    if len(csvs) == 1:
        return csvs[0]

    if name is not None:
        for path in csvs:
            if path.name == name:
                return path

    found = ", ".join(p.name for p in csvs)
    raise DatasetError(f"multiple CSV files in {directory}: {found} -- pass name= to pick one")


def dataset_csv(dataset: str = DATASET, *, force: bool = False, name: str | None = DEFAULT_CSV_NAME) -> Path:
    """Download ``dataset`` and return the path to its CSV file."""
    directory = download_dataset(dataset, force=force)
    return find_csv(directory, name=name)
