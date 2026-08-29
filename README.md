# cover-art

Fetch album cover art, normalize it to a fixed square size, and upload
it to Cloudflare R2. Three independent modules (fetch, normalize,
upload), each with a CLI subcommand and a Python API, plus a fourth
`publish` module that chains all three into one call.

## Install

From within this directory:

```
uv sync
```

Or as a dependency of another `uv` project:

```
uv add --editable /path/to/cover-art
```

Or with pip:

```
pip install /path/to/cover-art
```

## fetch

Look up an album by title (plus optional artist and year) and get its
cover art, via the [iTunes Search
API](https://performance-partners.apple.com/search-api). Free, no API
key, no signup. iTunes returns artwork URLs that embed the resolution
in the filename (e.g. `...100x100bb.jpg`), so any size can be requested
by swapping that segment — no extra request needed. Catalog coverage is
Apple Music's, so very obscure or regional releases may not turn up.

**CLI:**

```
cover-art fetch "Kind of Blue" --artist "Miles Davis" --year 1959 -o cover.jpg
cover-art fetch "Kind of Blue" --artist "Miles Davis" --url-only
```

Options: `--artist`, `--year` (both narrow the match), `--size`
(artwork pixel size, default 600), `--country` (iTunes storefront,
default `US`), `-o/--output` (default: slugified title + `.jpg`),
`--url-only` (print the resolved artwork URL instead of downloading).

**Python API:**

```python
from cover_art import download_cover, search_albums, find_cover_url

data = download_cover("Kind of Blue", artist="Miles Davis", year=1959)

# or inspect matches / get just the URL before downloading
albums = search_albums("Kind of Blue", artist="Miles Davis")
url = find_cover_url("Kind of Blue", artist="Miles Davis", size=1200)
```

Exports: `Album`, `CoverArtNotFound`, `search_albums`, `find_cover_url`,
`download_cover`.

## normalize

Resize any image to `size x size` (default 600x600), in one of three
modes:

| mode      | behavior                                                            | trade-off                     |
|-----------|----------------------------------------------------------------------|--------------------------------|
| `stretch` | scale X and Y independently to fill the square (default)             | distorts non-square sources    |
| `crop`    | center-crop to a square, then scale                                  | loses the cropped-off edges    |
| `pad`     | scale to fit inside the square, then letterbox with a background color | adds borders, no loss/distortion |

**CLI:**

```
cover-art normalize input.png -o out.jpg
cover-art normalize input.png -o out.jpg --size 800 --mode crop
```

Options: `-o/--output` (required), `--size` (default 600), `--mode`
(`stretch` | `crop` | `pad`, default `stretch`).

**Python API:**

```python
from cover_art import normalize_image, normalize_file

square = normalize_image(data, size=600, mode="stretch")

normalize_file("raw_cover.png", "cover_600.jpg", mode="pad")
```

Exports: `normalize_image`, `normalize_file`, `MODES`.

## upload

Upload any image to Cloudflare R2. Standalone: it takes bytes or a file
path and an object key, nothing album-specific — doesn't import from
`fetch` or `normalize`.

Reads four environment variables:

```
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
```

It talks to R2's S3-compatible endpoint
(`https://<account_id>.r2.cloudflarestorage.com`) with `region_name="auto"`,
as required by R2.

**CLI:**

```
cover-art upload cover.jpg --key covers/kind-of-blue.jpg
```

Options: `--key` (default: input file's basename), `--bucket`
(overrides `R2_BUCKET`), `--content-type` (default: guessed from key).
Credentials are env-only, never a flag.

**Python API:**

```python
from cover_art import upload_bytes, upload_file

key = upload_bytes(data, "covers/kind-of-blue.jpg")
key = upload_file("cover.jpg")  # key defaults to the file's basename
```

Exports: `R2Config`, `R2ConfigError`, `upload_bytes`, `upload_file`.

## publish

The only module that depends on the other three — fetch, normalize,
and upload stay independent of each other and of this one. `publish`
looks up an album, normalizes its cover, and uploads it, all in memory:
nothing touches disk unless `--save`/`save=` is given.

The object key defaults to a slug built from the *matched* album (not
your typed query), e.g. `miles-davis-kind-of-blue.jpg`; pass `--key`/
`key=` to override, or `--prefix`/`prefix=` to namespace it (e.g.
`covers/`). R2 credentials/bucket are resolved right before the upload
step, so `--save` still gets you a normalized file even without R2 set
up.

**CLI:**

```
cover-art publish "Kind of Blue" --artist "Miles Davis" --year 1959 --prefix covers/
```

Options: `--artist`, `--year`, `--country` (all narrow the iTunes
match), `--size`, `--mode` (same as `normalize`), `--key`, `--prefix`,
`--save` (also write the normalized image locally), `--bucket`
(overrides `R2_BUCKET`). Prints the matched album to stderr and the
uploaded key to stdout.

**Python API:**

```python
from cover_art import publish_cover

result = publish_cover("Kind of Blue", artist="Miles Davis", prefix="covers/")
print(result.key, result.album)
```

Exports: `publish_cover`, `PublishResult`, `default_key`.
