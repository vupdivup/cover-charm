# cover-art

Fetch album cover art, normalize it to a fixed square size, and upload
it to Cloudflare R2. Three independent modules, each with a CLI
subcommand and a Python API.

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

## Composing modules

The modules don't call each other, so wire them together by hand:

```python
from cover_art import download_cover, normalize_image, upload_bytes

data = normalize_image(download_cover("Kind of Blue", artist="Miles Davis"))
key = upload_bytes(data, "covers/kind-of-blue.jpg")
```
