# rym_albums

Download the RateYourMusic top-albums dataset from Kaggle, take the
most-reviewed *N* albums, and export them in the shape
`cover_art.pipeline.publish_covers` expects. Three independent modules
(download, select, export), each with a CLI subcommand and a Python
API, plus a fourth `top` (pipeline) module that chains all three.

## Install

From within the repo root (shared `pyproject.toml` with `cover_art`):

```
uv sync
```

## download

Fetch the dataset via [kagglehub](https://github.com/Kaggle/kagglehub),
which handles local caching -- a repeat call for the same slug is free.
Requires Kaggle credentials: `KAGGLE_API_TOKEN` env var (current
single-token scheme), or `KAGGLE_USERNAME`/`KAGGLE_KEY` env vars
(legacy). Env vars only, no credentials file, and never a flag.

**CLI:**

```
rym-albums download
rym-albums download --dataset tobennao/rym-top-5000 --force
```

Options: `--dataset` (Kaggle slug, default `tobennao/rym-top-5000`),
`--force` (re-download even if cached).

**Python API:**

```python
from rym_albums import dataset_csv, download_dataset, find_csv

path = dataset_csv()               # download (or reuse cache) + locate the CSV
directory = download_dataset()     # just the cached dataset directory
csv_path = find_csv(directory)     # locate the CSV within it
```

Exports: `DATASET`, `DatasetError`, `download_dataset`, `find_csv`, `dataset_csv`.

## select

Rank the dataset's rows by review count and keep the top *N*. Uses the
stdlib `csv` module, not pandas -- the job is one sort and one slice
over ~5,000 rows. Column headers vary across dataset revisions, so
they're matched loosely by alias rather than hard-coded (see
`resolve_column`); an unrecognized header raises `ColumnNotFound`
naming what it did find.

**CLI:**

```
rym-albums select --input rym_top_5000.csv -n 100
```

Options: `--input` (required, path to the dataset CSV), `-n/--limit`
(default 100), `-o/--output` (default: stdout).

**Python API:**

```python
from rym_albums import load_rows, top_by_reviews

rows = load_rows("rym_top_5000.csv")
top = top_by_reviews(rows, limit=100)
```

Exports: `ColumnNotFound`, `load_rows`, `resolve_column`, `top_by_reviews`.

## export

Map raw dataset rows to `cover_art`'s album shape: a list of
`{"title", "artist", "year"}` dicts, matching
`cover_art.pipeline._normalize_item`'s dict form (`title` required,
`artist`/`year` optional). Standalone -- doesn't import `cover_art`.

**CLI:**

```
rym-albums export --input rym_top_5000.csv -o albums.json
echo '[{"Album": "OK Computer", "Artist Name": "Radiohead", "Release Date": "1997"}]' \
  | rym-albums export --input -
```

Options: `--input` (required, a dataset CSV path or `-` for a JSON row
array on stdin), `-o/--output` (default: stdout).

**Python API:**

```python
from rym_albums import to_albums, load_rows

rows = load_rows("rym_top_5000.csv")
albums = to_albums(rows)
# [{"title": "OK Computer", "artist": "Radiohead", "year": 1997}, ...]
```

Exports: `AlbumRecord`, `to_albums`, `to_json`, `write_json`.

## top

The only module that depends on the other three. Downloads the
dataset (or reads `path`/`--input` if given, skipping the network),
ranks it, and exports the top *N* albums, all in one call.

**CLI:**

```
rym-albums top -n 50
rym-albums top -n 50 -o albums.json
rym-albums top -n 50 --input rym_top_5000.csv   # reuse an already-downloaded CSV
```

Options: `-n/--limit` (default 100), `--dataset` (default
`tobennao/rym-top-5000`), `--input` (use this CSV instead of
downloading), `--force` (re-download), `-o/--output` (default:
stdout). Prints an album count to stderr and the JSON array to stdout
(or the output path, if `-o` is given).

**Python API:**

```python
from rym_albums import top_albums

albums = top_albums(limit=100)
```

Exports: `top_albums`.

## Handoff to cover_art

`top_albums`'s return value is exactly what
`cover_art.pipeline.publish_covers` accepts as `items`:

```python
from cover_art.pipeline import publish_covers
from rym_albums import top_albums

outcomes = publish_covers(top_albums(limit=50), prefix="covers/")
for outcome in outcomes:
    if outcome.ok:
        print(outcome.title, "->", outcome.result.key)
    else:
        print(outcome.title, "failed:", outcome.error)
```

Same on the CLI side, piping `top`'s JSON into a shell loop, or via any
tool that reads `cover-art publish`'s title/artist/year positionally
from the JSON.
