# wubwub.covers

Fetch album cover art by title (plus optional artist), via
[MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_API) (search) and the
[Cover Art Archive](https://musicbrainz.org/doc/Cover_Art_Archive/API)
(artwork). Free, no API key, no signup. A title/artist query resolves to a
MusicBrainz release-group ID, then that ID is looked up in Cover Art
Archive for the actual image -- two requests per fetch. Catalog and
artwork coverage is community-maintained rather than a commercial store's,
so it's generally broader for older/obscure releases (and occasionally
missing art for something niche enough that no one's uploaded it yet).

## Install

From the repo root:

```
uv sync
```

## Usage

**CLI:**

```
wubwub covers fetch "Kind of Blue" --artist "Miles Davis" -o cover.jpg
wubwub covers fetch "Kind of Blue" --artist "Miles Davis" --url-only
```

Options: `--artist` (narrows the match), `--size` (artwork pixel size,
snapped to the nearest Cover Art Archive thumbnail: 250/500/1200,
default 600), `-o/--output` (default: slugified title + `.jpg`),
`--url-only` (print the resolved artwork URL instead of downloading).

Matches are scored client-side by fuzzy title/artist similarity (on top of
MusicBrainz's own relevance ranking, which still places tributes, demos,
and remixes close to a correct match); anything under `MATCH_THRESHOLD`
(default 0.75, in `fetch.py`) is rejected as not the requested album
rather than returned as a wrong guess. If a real match gets rejected,
lower the threshold. Release year is not used for matching -- a release
group's first-release-date can reflect a reissue's catalog entry rather
than the queried edition. Not every matched album has art in Cover Art
Archive, so a few of the top-ranked candidates are tried in order
(`_MAX_ARTWORK_LOOKUPS` in `fetch.py`) before giving up.

**Python API:**

```python
from wubwub.covers import download_cover, search_albums, find_cover_url

data = download_cover("Kind of Blue", artist="Miles Davis")

# or inspect matches / get just the URL before downloading
albums = search_albums("Kind of Blue", artist="Miles Davis")
url = find_cover_url("Kind of Blue", artist="Miles Davis", size=1200)
```

Exports: `Album`, `CoverArtNotFound`, `search_albums`, `find_album`,
`artwork_url`, `download_url`, `find_cover_url`, `download_cover`.

## Logging

The library logs via the stdlib `logging` module under the `wubwub.covers`
name (`NullHandler`ed by default, so importing it is silent). One line
per resolved cover (INFO), per skipped/no-art candidate (DEBUG/INFO), and
per rejected match or rate-limit retry (WARNING); query strings and
candidate scores at DEBUG.

**CLI:** `-v` for INFO, `-vv` for DEBUG, `-q` to drop to errors-only.
Logs go to stderr; stdout stays just the resolved URL / written path.

```
wubwub covers fetch "Kind of Blue" --artist "Miles Davis" -v
```

**As a library:** nothing extra is needed if the host app already
configures `logging`; to see just this subpackage's records:

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("wubwub.covers").setLevel(logging.INFO)
```

## Rate limiting

Throttling and retry against MusicBrainz/Cover Art Archive's shared rate
limit (~1 request/second uncredentialed) live in `fetch.py` and apply to
every caller. Tune via `wubwub.covers.fetch.SEARCH_INTERVAL` (default 1.1s,
one request per call), `MAX_RETRIES` (default 5), and `INITIAL_BACKOFF`
(default 2.0s, doubled per retry) if you hit 429/503 anyway.
