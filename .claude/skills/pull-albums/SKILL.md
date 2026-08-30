---
name: pull-albums
description: >
  Pull a JSON album list for any time period — a year, a month, a range
  of years, a decade — split evenly between mainstream-popular and
  critically-acclaimed albums. Use when the user asks to pull albums for
  a period, wants a best-of list for a span of time, needs a seed list
  for an era, or invokes /pull-albums.
  Args: <period> [count].
---

Build a JSON album list for `<period>`, split evenly between mainstream
hits and critics' picks.

## 1. Parse the period

Accept and normalize any of:

- single year — `2015`
- month — `2015-06`, `June 2015`
- year range — `2010-2014`, `2010..2014`
- decade / era — `1990s`, `the 90s`, `late 80s`
- quarter or season — `summer 2015`, `Q1 2020`

Resolve to an explicit start/end date and **echo the resolution back to
the user** before searching (e.g. "late 80s → 1986-01-01 to
1989-12-31") — a loose phrase must never silently mean something else.
If the phrase is genuinely ambiguous (e.g. a bare `05`), ask instead of
guessing.

An album belongs to the period if its **original release date** falls
inside it — never a reissue/anniversary-edition date.

## 2. Parse count

Optional, default 20. Half mainstream, half critics. If odd, mainstream
gets the extra slot.

## 3. Search, by period length

Fetch source pages — don't trust search snippets alone.

- **Month or shorter** — mainstream: weekly Billboard 200 / official
  chart entries within the window. Critics: individual reviews and
  Metacritic/AOTY scores for releases dated in the window. Year-end
  lists don't exist at this granularity — don't use them.
- **A year (or a season/quarter within one)** — mainstream: Billboard
  year-end albums chart. A year-end chart ranks *chart performance
  during* the year, not releases *from* it — albums released late in
  the prior year routinely dominate it (e.g. a 1992 year-end chart is
  often majority 1991 releases). So: pull the chart, then **filter
  every entry by original release date** and discard the carryovers
  before ranking anything. Expect to lose a large fraction — for a
  strong prior-year Q4, half or more is normal, not a bug. Backfill
  down the chart until the mainstream half is full, and supplement with
  that year's Billboard 200 #1s and other big sellers if the chart runs
  dry. State the carryover drop count in the report (step 8).

  Critics: try, in order, until one yields enough entries —
  1. Metacritic / AOTY aggregate year-end ranking, filtered to the
     sub-window if narrower than the full year.
  2. A major publication's own year-end or retrospective list —
     Pitchfork, Rolling Stone, The Guardian, NME, Slant.
  3. A user-vote aggregate (besteveralbums.com, RYM) — acceptable, but
     **label it as such in the report**, since it measures long-run
     listener consensus, not contemporary critical reception.

  If a source is unreachable (403, dead link, etc.), say so in the
  report and name the substitute used — don't swap tiers silently.
- **Multiple years / a decade** — prefer a published best-of-decade or
  best-of-era ranking where one exists (Pitchfork, Rolling Stone,
  Metacritic) for critics; best-selling/most-streamed-of-the-decade
  rankings for mainstream. If no aggregate exists, fall back to
  per-year lists — applying the same year-end carryover filter and
  critic-source ladder above to each constituent year — and **spread
  picks across the constituent years** rather than letting one year
  dominate. State which method was used.

## 4. Dedupe

An album appearing on both lists counts once — keep it in the
mainstream half, and let the critics half backfill from its next
ranked entry, so the total still equals `count`.

## 5. Normalize fields

- `title` — album title only. Strip "(Deluxe)", "(Anniversary
  Edition)", and other parenthetical reissue tags.
- `artist` — primary credited artist, exactly as billed.

## 6. Verify the count

Before writing anything, count each half. Assert
`mainstream + critics == count`, and that the split matches step 2
(mainstream takes the extra slot on an odd count). Halves drift easily
during dedupe — don't trust the running total, recount.

## 7. Write the file

`albums-<period-slug>.json` in the working directory unless the user
names a path (slug mirrors the normalized period: `albums-2015.json`,
`albums-2015-06.json`, `albums-2010-2014.json`, `albums-1990s.json`).

A JSON array, 2-space indent, **title and artist only** — no year, no
rank, no source, no wrapper object:

```json
[
  { "title": "To Pimp a Butterfly", "artist": "Kendrick Lamar" },
  { "title": "1989", "artist": "Taylor Swift" }
]
```

## 8. Report

Re-read the written file first: confirm the array length equals `count`
and every object has exactly `title` and `artist`. Report the verified
number, not the intended one.

Print the resolved period, the file path, the verified count, and one
line naming the sources actually used for each half — including any
year-end carryover drop count (step 3) and any source substitution
(step 3). Note any album the search couldn't confirm rather than
inventing one.

## Constraints

- Never fabricate an album to reach `count` — if sources yield fewer,
  say so and stop short.
- Titles/artists must come from a fetched source, never from recall.
- Membership is by original release date, not reissue date.
- The output file is data only — put commentary in the chat reply.
