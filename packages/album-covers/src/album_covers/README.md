# album-covers

Fetch album cover art by title (plus optional artist), via
the [iTunes Search
API](https://performance-partners.apple.com/search-api). Free, no API
key, no signup. iTunes returns artwork URLs that embed the resolution
in the filename (e.g. `...100x100bb.jpg`), so any size can be requested
by swapping that segment — no extra request needed. Catalog coverage is
Apple Music's, so very obscure or regional releases may not turn up.

## Install

From within this directory:

```
uv sync
```

Or as a dependency of another `uv` project:

```
uv add --editable /path/to/album-covers
```

Or with pip:

```
pip install /path/to/album-covers
```

## Usage

**CLI:**

```
album-covers fetch "Kind of Blue" --artist "Miles Davis" -o cover.jpg
album-covers fetch "Kind of Blue" --artist "Miles Davis" --url-only
```

Options: `--artist` (narrows the match), `--size` (artwork pixel size,
default 600), `--country` (iTunes storefront, default `US`),
`-o/--output` (default: slugified title + `.jpg`), `--url-only` (print
the resolved artwork URL instead of downloading).

Matches are scored client-side by fuzzy title/artist similarity (there's
no server-side relevance parameter for either); anything under
`MATCH_THRESHOLD` (default 0.75, in `fetch.py`) is rejected as not the
requested album rather than returned as a wrong guess. If a real match
gets rejected, lower the threshold. Release year is not used for
matching -- iTunes' release date reflects the storefront edition
(remaster, reissue, region), not necessarily the original release.

**Python API:**

```python
from album_covers import download_cover, search_albums, find_cover_url

data = download_cover("Kind of Blue", artist="Miles Davis")

# or inspect matches / get just the URL before downloading
albums = search_albums("Kind of Blue", artist="Miles Davis")
url = find_cover_url("Kind of Blue", artist="Miles Davis", size=1200)
```

Exports: `Album`, `CoverArtNotFound`, `search_albums`, `find_album`,
`artwork_url`, `download_url`, `find_cover_url`, `download_cover`.

## Rate limiting

Throttling and retry against the iTunes Search API's rate limit
(~20 requests/minute uncredentialed) live in `fetch.py` and apply to
every caller. Tune via `album_covers.fetch.SEARCH_INTERVAL` (default
3.0s, one search per call), `MAX_RETRIES` (default 5), and
`INITIAL_BACKOFF` (default 5.0s, doubled per retry) if you hit
403/429 anyway.
