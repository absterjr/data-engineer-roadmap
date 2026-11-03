# Fix-it-first: broken pipeline

`broken_pipeline.py` runs. It fetches weather, writes a CSV, loads a
database, prints **"pipeline done!"** — and is wrong in 8 different ways.

## Rules

1. Run it twice: `python broken/broken_pipeline.py` (from `phase-04-pipelines/`)
2. For each behavior below, find the bug behind it — classify each as
   **CRASH** or **SILENT** (7 of 8 are silent):
   - you cannot ask it for a date range — try backfilling March
   - a transient network blip kills the whole run
   - re-running DUPLICATES rows in the database
   - one bad city silently drops every city after it
   - it prints "Done!" even when the API failed
   - a crash mid-load leaves a half-loaded database that looks complete
   - outputs are keyed by TODAY's date, not the data's dates
3. Fix them without opening `src/` (the rebuilt version).
4. Done when: re-runs don't duplicate rows, failures are loud, any date
   range is a backfill, and the database row count stays put.

**Measured evidence** (why these bugs matter):

```
broken:  2 runs -> 84 rows in the DB, only 21 distinct (city, date) pairs
fixed :  2 runs -> 49 rows, 49 distinct — stable forever
```

## Compare side by side

`broken_pipeline_fixed.py` is the corrected twin — same shape, every fix
carrying a `BUG n FIX` comment.

```bash
git diff --no-index broken/broken_pipeline.py broken/broken_pipeline_fixed.py
# or VS Code: select both files -> right-click -> "Compare Selected"
```

## Hints (one per bug, mild spoilers)

1. Where do the start/end dates come from? Can the script fetch March 2025?
2. What happens to `urlopen` when the network hiccups? Is there a second try?
3. What if the API returns `{"error": true, ...}` — does anything check?
4. Run it twice and count the rows. Where did the duplicates come from?
5. What does that `except: break` do to the cities AFTER the one that failed?
6. Read the last line of `main()`. Would it print even if the API was down?
7. What does a crash between two INSERTs leave behind?
8. What is the CSV named after — the data's dates, or the run's?

<details>
<summary><b>Answers — full spoilers, open only after trying</b></summary>

| # | Bug | Type | Fix |
|---|-----|------|-----|
| 1 | Dates hard-coded as "yesterday minus 3 days" — no CLI args, so no backfills, no replays | silent | `--start`/`--end` arguments; the date range is an input, not a constant |
| 2 | One `urlopen`, zero retries — a transient network blip fails the whole run | crash | retry loop with backoff (3 attempts, sleep between) |
| 3 | Payload never validated — an API error envelope crashes the script mid-run (or feeds garbage downstream) | crash | check for the `daily` block before using it, with a clear error |
| 4 | Plain `INSERT`, no key — every re-run duplicates rows; averages drift | silent | `PRIMARY KEY (city, date)` + `ON CONFLICT DO UPDATE` (UPSERT) |
| 5 | `except: break` — one bad city silently drops every city after it, and the run still says "done" | silent | collect failures, process all cities, fail loudly if any failed |
| 6 | Unconditional `print("Done!")` — success is claimed, never checked | silent | verify the result (rows in == rows out), exit non-zero on failure |
| 7 | Row-by-row commits — a crash mid-load leaves a half-loaded table that looks complete | silent | one transaction: all rows land, or none do |
| 8 | Output keyed by today's date — backfilling October then November overwrites the same file | silent | name outputs by the DATA's range; the run date is metadata, not the filename |

Meta-lesson: **7 of 8 are silent.** A broken pipeline doesn't error —
it prints "done!" and moves on. Monitoring (§ docs/PIPELINE-NOTES.md) is
what turns those silent lies into loud failures.
</details>