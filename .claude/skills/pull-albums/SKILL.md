---
name: pull-albums
description: >
  Pull a JSON album list for any time period — a year, a month, a range
  of years, a decade — split between mainstream-popular and
  critically-acclaimed albums (60/40 by default). Use when the user
  asks to pull albums for a period, wants a best-of list for a span of
  time, needs a seed list for an era, or invokes /pull-albums.
  Args: <period> [count] [mainstream%].
---

Build a JSON album list for `<period>`, split between mainstream hits
and critics' picks.

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

**An album belongs to the period if its original release date falls
inside it — never a reissue or anniversary-edition date.** This governs
both membership and the `release_year` field, and it is the rule most
easily lost when a source reports chart dates instead.

## 2. Parse count and split

Count optional, default 20. Split optional, default 60 (percent
mainstream, remainder critics) — e.g. `2015 40 50` means count 40, an
even split. Compute `mainstream = round(count * split / 100)`,
`critics = count - mainstream`, so mainstream takes the remainder slot
on a non-integer split.

## 3. Search, by period length

Fetch source pages — don't trust search snippets alone. Every WebFetch
prompt must ask for only `title | artist | year` rows, capped at
roughly 2x the needed count, and nothing else — a ranked page's full
prose is expensive to carry and unnecessary once reduced to that.

Fire candidate sources **in parallel, in one message**, rather than
probing one at a time. Dead sources are common (paywalls, 403s, pages
that truncate) and a failed fetch costs almost nothing, so batching
several candidates and keeping whichever responds is much faster than
a serial chain of retries.

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
  dry. State the carryover drop count in the report (step 7).

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
- **Multiple years / a decade** — **default to one span-wide aggregate
  per half**: a published best-of-decade or best-of-era ranking
  (Pitchfork, Rolling Stone, Metacritic) for critics, a
  best-selling/most-streamed-of-the-span ranking for mainstream — one
  page per half, not one per year. Only fall back to per-year lists
  when no span-wide aggregate exists for that window, applying the
  carryover filter and critic ladder above to each constituent year.
  Either way, **spread picks across the constituent years** rather than
  letting one year dominate. State which method was used.

## 4. Dedupe

An album appearing on both lists counts once — keep it in the
mainstream half, and let the critics half backfill from its next
ranked entry, so the total still equals `count`.

## 5. Normalize fields

- `title` — album title only. Strip "(Deluxe)", "(Anniversary
  Edition)", and other parenthetical reissue tags.
- `artist` — primary credited artist, exactly as billed.
- `release_year` — original release year (int), per step 1.

## 6. Write the file

Recount both halves first — they drift during dedupe, so don't trust
the running total. Assert `mainstream + critics == count` and that the
halves match step 2's targets.

Write `albums-<period-slug>.json` in the working directory unless the
user names a path (slug mirrors the normalized period:
`albums-2015.json`, `albums-2015-06.json`, `albums-2010-2014.json`,
`albums-1990s.json`).

A JSON array, 2-space indent, **title, artist, release_year only** — no
rank, no source, no wrapper object:

```json
[
  { "title": "To Pimp a Butterfly", "artist": "Kendrick Lamar", "release_year": 2015 },
  { "title": "1989", "artist": "Taylor Swift", "release_year": 2014 }
]
```

## 7. Report

Re-read the written file and confirm the array length equals `count`
and every object has exactly `title`, `artist`, `release_year`. Report
the verified number, not the intended one.

Print the resolved period, the file path, the verified count, the split
used (mainstream% and the two half-counts), and one line naming the
sources actually used for each half — including the carryover drop
count and any source substitution. Note any album the search couldn't
confirm rather than inventing one.

## Constraints

- Never fabricate an album to reach `count` — if sources yield fewer,
  say so and stop short.
- Titles/artists must come from a fetched source, never from recall.
- The output file is data only — put commentary in the chat reply.

## Running several chunks

A single pull runs in one context and spawns nothing. To cover several
periods, delegate each to its own subagent with a self-contained
prompt, a few concurrent — the chunks are independent.

Use `model: sonnet`; a subagent otherwise inherits the caller's model,
which is usually larger than fetch-and-extract work needs. Haiku
handles the mechanics but tends to pick whichever source makes the
carryover filter unnecessary.

Never `subagent_type: "fork"` — a fork inherits the caller's context,
including these orchestration instructions, and re-spawns its own fleet.
