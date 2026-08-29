"""rym_albums: download the RateYourMusic top-albums Kaggle dataset and
export the most-reviewed albums in cover_art's input shape."""

from .download import DATASET, DEFAULT_CSV_NAME, DatasetError, dataset_csv, download_dataset, find_csv
from .export import AlbumRecord, to_albums, to_json, write_json
from .pipeline import top_albums
from .select import ColumnNotFound, load_rows, resolve_column, top_by_reviews

__all__ = [
    "DATASET",
    "DEFAULT_CSV_NAME",
    "DatasetError",
    "download_dataset",
    "find_csv",
    "dataset_csv",
    "ColumnNotFound",
    "load_rows",
    "resolve_column",
    "top_by_reviews",
    "AlbumRecord",
    "to_albums",
    "to_json",
    "write_json",
    "top_albums",
]
