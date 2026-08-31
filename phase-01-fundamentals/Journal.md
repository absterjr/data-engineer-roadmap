# Phase 1 — Journal

Personal notes on what I did, what I learned, and what's next. This is the log for this phase's journey — the README stays project-facing, this is mine.

Each entry links the commit(s) it covers, so anyone can see exactly what changed and when.

---

## Entry 1 — Dataset loaded, engine runs

**Date:** 2026-08-25

**Commit(s):** [`a0bca26`](https://github.com/absterjr/data-engineer-roadmap/commit/a0bca26) — "Phase 1.1" · [`4ed40c1`](https://github.com/absterjr/data-engineer-roadmap/commit/4ed40c1) — "Update Readme.MD"

**What I did**

- Converted `data/Online Retail.xlsx` → `data/online_retail.csv` (541,909 rows × 8 cols) using pandas + openpyxl.
- Ran the engine: `python src/engine.py data/online_retail.csv` — it loaded the full table and printed a preview.
- Columns: `InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country`.

**What I learned**

- The engine reads the whole dataset into memory — fine here, but costly at scale. Noted for Phase 5.
- `CustomerID` came through as `17850.0` — the xlsx encoded it as a float. This is a real-world data quality issue: types matter, and I'll need to cast/clean values in the engine.
- Output:
  ```
  Table('online_retail', cols=[...8 cols...], rows=541909)
  ```

**Questions / blockers**

- Should `read_csv` coerce numeric columns automatically, or keep values as strings and let the caller decide?
- How should missing `CustomerID` values be handled?

**Next steps**

- Implement `WHERE` / `GROUP BY` / `JOIN` workouts on this dataset (e.g. total revenue by country, top products).
- Start the rebuild task: fix poorly-written SQL that does the same analysis.

---

## Entry 2 — First analytics queries through the engine

**Date:** 2026-08-26

**Commit(s):** [`d14c71e`](https://github.com/absterjr/data-engineer-roadmap/commit/d14c71e) — "feat(phase-1): day 2 - query workouts through the engine"

**What I did**

- Upgraded the engine: `read_csv` now coerces types (int / float / None), added `extend` (computed columns), `order_by`, `limit`, and aggregates (`count`, `sum_`, `mean`, `min_`, `max_`). `join` now dedupes shared column names.
- Fixed the CustomerID problem from Entry 1: `'17850.0'` now loads as the int `17850`, not a float.
- Added `data/country_region.csv` (38 countries → 8 regions) as a second table for the JOIN workout.
- Wrote `src/queries.py` — five analytical questions answered with engine ops only:
  1. Total revenue by country → UK $8.19M (82% of everything), then Netherlands, EIRE, Germany.
  2. Top products by revenue → `DOTCOM POSTAGE` ($206k) — literally the postage line item, not a product.
  3. Monthly revenue → seasonal: peaks Nov 2011 ($1.46M), troughs Jan–Feb.
  4. Revenue by region → JOIN with the region table: Europe (ex-UK) $1.34M, then Asia-Pacific.
  5. Data quality → 135,080 rows (25%) missing CustomerID, 10,624 negative Quantity (returns), 9,288 on cancelled invoices.
- Added `scripts/fetch_online_retail.py` — the dataset is gitignored, so this makes the repo reproducible for others.
- Pretty-printed results as aligned columns so output is readable in the terminal and the README.

**What I learned**

- **Type coercion is a decision, not a fact.** Auto-casting ints/floats is what real engines do, but `'17850.0'` → float, not int, unless you handle integral floats. I now convert `17850.0` → `17850`. Note: leading-zero IDs (e.g. `00123`) would be destroyed by int() — a reason production schemas declare types explicitly.
- **Float arithmetic is noisy.** `36595.909999999996` — summed revenue drifts. This is why money in real systems is stored as cents (integer) or DECIMAL, and why rounding at the display layer is a band-aid.
- **GROUP BY order is accidental.** My buckets preserve first-seen order, which happened to be near-alphabetical. SQL makes no order guarantee either — that's what ORDER BY is for. Building `order_by` made this concrete.
- **Aggregates as closures.** `sum_("Revenue")` returns a function; SQL's `SUM(x)` maps naturally to this. `count` needs no column — it's `COUNT(*)`.
- **JOIN key columns collide.** Both tables have `Country`; the merged row must keep one. Real engines track this with fully-qualified names (`left.Country` vs `right.Country`) — my `join` dedupes instead, and that's a design decision worth remembering.
- **25% missing CustomerID is normal.** The Online Retail dataset famously drops customer IDs on some transactions. Real analysis must decide: drop, flag, or impute — never silently ignore.
- **Data quality queries are queries.** Q5 used the same `where` op as Q1 — a pipeline isn't a different beast from analytics; it's the same ops applied earlier.

**Questions / blockers**

- Should the engine add `LEFT JOIN` (rows from the left with no match get NULLs)? Region lookup would be safer — a new country shouldn't silently vanish.
- Is `extend` the right abstraction for computed columns, or should it be a full `select(exprs)`?
- Should missing-CustomerID revenue be attributed to "Unknown" in Q1 (like SQL's `COALESCE`)?

**Next steps**

- Rebuild task: fix poorly-written SQL queries that answer Q1–Q3 (write them in `sql/`), then rewrite them cleanly with indexes and explain plans.
- Window functions: implement `ROW_NUMBER()` / running totals in the engine (Phase 1 skill list).
- Add pytest tests for the engine — a tiny engine this core deserves a safety net.

---

## Entry 3 — Beginner guide: how the engine and queries work

**Date:** 2026-08-27

**Commit(s):** [`1318c0e`](https://github.com/absterjr/data-engineer-roadmap/commit/1318c0e) — "docs(phase-1): beginner guide - how the engine and queries work"

**What I did**

- Wrote `HOW-IT-WORKS.md`: a plain-language guide explaining what a table/CSV is, what the engine is (a mini SQL database in pure Python), and what `queries.py` is (five questions asked to the engine).
- Included a step-by-step walkthrough of Q1 (revenue by country) showing the same question in SQL and as engine calls — load → compute Revenue → group by country → sort → top 10.
- Added a SQL ↔ engine cheat sheet table (every engine function mapped to its SQL equivalent).
- Added a glossary: CSV, row, column, aggregate, NULL, coerce, JOIN key, predicate, `lambda`.
- Linked the guide from the top of the phase README with a "New here?" callout.

**What I learned**

- Documentation for beginners is a translation problem: take what I now take for granted (that `group_by` is `GROUP BY`, that a CSV is just a text table) and say it out loud. Writing the SQL↔engine table forced me to check every function signature against its SQL equivalent — a useful self-review of the engine's design.
- A worked example (Q1 end to end) is worth more than a dozen definitions — it shows the *flow*, not just the pieces.

**Questions / blockers**

- Should each engine function get a mini worked example too, or is the Q1 walkthrough + cheat sheet enough for now?

**Next steps**

- Rebuild task: poorly-written SQL for Q1–Q3 in `sql/`, then rewrite cleanly with indexes and explain plans.
- Window functions in the engine.
- pytest tests for the engine.

---

## Entry 4 — Rebuild task: bad SQL vs fixed SQL, explained

**Date:** 2026-08-28

**Commit(s):** [`33db0bf`](https://github.com/absterjr/data-engineer-roadmap/commit/33db0bf) — "feat(phase-1): day 4 - rebuild task: bad vs fixed SQL with detailed explanations" · [`479f244`](https://github.com/absterjr/data-engineer-roadmap/commit/479f244) — "fix(gitignore): untrack sqlite db, properly track country_region.csv"

**What I did**

- Rebuild task complete: `sql/bad_queries.sql` (Q1–Q3 + a bonus query that errors) and `sql/good_queries.sql` (the fixes + the index).
- `sql/README.md` — the detailed write-up: SQL's order of operations (FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT), every problem explained with **real** `EXPLAIN QUERY PLAN` output, and alternative correct ways to write each query (HAVING, CTEs, window functions, `strftime`, partial-month handling).
- `scripts/setup_sqlite.py` loads the CSV into SQLite (541,909 rows, no indexes on purpose) and `scripts/run_sql.py` runs a `.sql` file without needing the sqlite3 CLI.
- Cross-checked: the SQL answers match the engine's answers (Q1, Q3 identical numbers) — two independent implementations agreeing is a free test.

**What I learned**

- **The order of operations is the whole game.** Every "bad" query violated it: `WHERE SUM(...)` (aggregates don't exist before grouping), `DISTINCT` after `GROUP BY` (redundant second pass — visible in the plan as `USE TEMP B-TREE FOR DISTINCT`).
- **Non-sargable predicates beat indexes.** `LIKE '%2011%'` and `substr(InvoiceDate,1,4)='2011'` both still `SCAN online_retail` *after* I created the index; only the range predicate (`>= '2011-01-01' AND < '2012-01-01'`) became `SEARCH ... USING INDEX`. Proven with plans, not vibes.
- **SQLite hides bugs by being helpful.** A bare column in `SELECT` that's not in `GROUP BY` runs in SQLite (arbitrary value) but errors in PostgreSQL. Real proof in the data: 85123A has four descriptions (`?`, CREAM, WHITE, "wrongly marked carton 22804") — the bad query lumps $97,894 under the first label and hides $178.51 of real sales.
- **Ordinals are fragile promises** (`ORDER BY 2`, `GROUP BY 1`) — silently wrong the day a column moves. Name columns.
- **Partial months are an analytics trap, not a SQL error.** `2011-12 | 433k` looks like a crash; the data just ends Dec 9. Queries can be perfect and the answer still wrong.
- **`.gitignore` mistakes are silent until a 64MB file lands.** My `data/*` edit anchored the pattern to the repo root, un-ignoring `phase-01-fundamentals/data/` entirely — the 64.5MB SQLite DB got committed (GitHub warned) and, worse, `country_region.csv` had silently never been tracked (Q4 would crash for anyone cloning). Fix: `**/data/*` + `!**/data/country_region.csv` + `git rm --cached`. A pattern with a slash in the middle is anchored to the .gitignore's directory — that nuance cost a full commit.

**Questions / blockers**

- The 64.5MB DB blob now lives in git history forever (a fresh clone is ~64MB heavier). Rewrite history (filter-repo) to purge it, or accept it for a small learning repo?
- Does the engine need `LEFT JOIN` next, or should the SQL side learn `LEFT JOIN` first?

**Next steps**

- Window functions: implement `ROW_NUMBER()` / running totals in the engine (Phase 1 skill list).
- pytest tests for the engine.
- LinkedIn post draft for Phase 1 (ship publicly).

---

## Entry 5 — Docs pass: all markdown synced with progress

**Date:** 2026-08-29

**Commit(s):** [`28c3ffc`](https://github.com/absterjr/data-engineer-roadmap/commit/28c3ffc) — "docs: sync all markdown with current progress"

**What I did**

- Audited all five `.md` files against the actual repo state and fixed every mismatch:
  - **Root README** — Phase 1 status now links to the folder; added a "What's built so far" block under Phase 1 details; project layout updated to match reality (`Journal.md`, `HOW-IT-WORKS.md`, no phantom `notebooks/`); documented the journal-with-commit-links workflow in "How to use" and a new "How this repo is maintained" section.
  - **Phase-01 README** — added a "What's in this folder" tree so newcomers see the whole shape at once; every command now states which directory to run it from.
  - **HOW-IT-WORKS.md** — added "fetch the data first" note (file is gitignored) and the working-directory note.
  - **sql/README.md** — clarified that the commands work from anywhere.
- Small code fix to make that true: `run_sql.py` now falls back to the phase folder when a `.sql` path isn't found relative to the current directory.

**What I learned**

- **Docs rot fast.** Five days in, the layout section still described a `notebooks/` folder that never existed, commands assumed a working directory readers wouldn't be in, and the root README didn't point to anything actually built. The audit surfaced a real usability bug (the sql commands broke from the repo root).
- **A tiny script change fixed five docs.** Instead of documenting "run from phase-01-fundamentals, except these two", one fallback in `run_sql.py` made every command work from anywhere — code beats prose.

**Questions / blockers**

- None — the repo now reads consistently from a first-time visitor's perspective.

**Next steps**

- Window functions: implement `ROW_NUMBER()` / running totals in the engine.
- pytest tests for the engine.
- LinkedIn post draft for Phase 1 (ship publicly).

---

## Entry 6 — LinkedIn post draft + profile feature

**Date:** 2026-08-30

**Commit(s):** (no commit — the post draft was shared directly with the author for publishing on LinkedIn, not stored in the repo)

**What I did**

- Drafted the Phase 1 launch post: the "AI rot" angle (rebuild SQL to understand it, not to write it faster), five concrete lessons from the build (order of operations, accidental GROUP BY order, defeating indexes, messy data, WHERE vs HAVING), repo link, and a publish checklist. Delivered to the author in chat for publishing.
- Tried to feature the repo on my GitHub profile via the API — the `updateUserPinnedItems` GraphQL mutation no longer exists on GitHub's schema, so featuring must be done from the profile UI ("Customize your pins").

**What I learned**

- **GitHub removed the pinning API.** Only the profile UI can pin/feature repos now. Also: gh on Windows mangles GraphQL arguments with quotes — `--input` with a JSON body file is the reliable path.
- **Writing the post is a second audit.** Every number in the post had to be verified against the repo (541,909 rows, 25% missing CustomerID, four descriptions for 85123A, EXPLAIN output) — the same facts the docs already claim. Two sources agreeing is the pattern this whole project runs on.

**Questions / blockers**

- Post timing: publish now (Phase 1 shipped) or after window functions + tests land?

**Next steps**

- Window functions: implement `ROW_NUMBER()` / running totals in the engine.
- pytest tests for the engine.
- Publish the LinkedIn post (link in comments), then add the repo feature to the profile.

---

## Entry 7 — Window functions, LEFT JOIN, error handling: engine and SQL gaps closed

**Date:** 2026-08-31

**Commit(s):** [`64164d5`](https://github.com/absterjr/data-engineer-roadmap/commit/64164d5) — "feat(phase-1): day 7 - window functions, LEFT JOIN, error handling"

**What I did**

- **Engine window functions**: `row_number`, `rank`, `dense_rank`, `running_sum`, `partition_sum` — SQL's `OVER (PARTITION BY ... ORDER BY ...)` implemented by hand. Rows keep their position (window functions add a column, they don't collapse or reorder — that's the whole conceptual difference from GROUP BY). NULLs sort last.
- **`join(..., how="left")`** with a hash index — O(n+m) instead of the nested loop's O(n*m), same trick real databases use. Verified: dropping UK from the region table keeps all left rows with `Region = None`.
- **Error handling**: missing columns raise a clear `KeyError` (with the available columns listed), missing files raise `FileNotFoundError` with a "run scripts/fetch_online_retail.py" hint, bad join types raise `ValueError`.
- **queries.py Q6–Q8**: top-3 products per country/month (`ROW_NUMBER`), cumulative monthly revenue (`running_sum`), revenue share by country (`partition_sum` with no key = grand total).
- **sql/window_functions.sql**: the same Q6–Q8 in SQL plus a RANK vs DENSE_RANK tie demo (products 22113 and 23207 both round to $12,701 — ROW_NUMBER splits them 1,2; RANK/DENSE_RANK tie them 1,1) and the "WHERE can't use windows" trap.

**What I learned**

- **Cross-validation caught a real bug.** My first engine Q6 ranked individual invoice lines, not products — UK came out $441,845 vs SQL's $551,976. The engine and SQL sides were written independently; the mismatch surfaced instantly. This is why the "same numbers from two implementations" rule is worth its weight: it's a test suite in disguise.
- **Window semantics are subtle where you least expect it.** Without an ORDER BY, `SUM() OVER (PARTITION BY k)` is the whole partition; with one, it's a running total. That one difference is a whole class of bugs in real dashboards.
- **Hash join is a performance cliff a beginner can actually feel** — 541k rows × 38 region rows was fine with nested loops, but left joins on big tables would crawl. The index-building step is the same "sorted lookup" idea as SQLite's B-tree, one level simpler.

**Questions / blockers**

- None — engine and SQL now cover the full Phase 1 skill list (joins, window functions, CTEs via the workout, query optimization via EXPLAIN).

**Next steps**

- pytest test suite for the engine (the journal's oldest open item).
- Phase 1 wrap-up: mark statuses complete, publish the LinkedIn post.
- Optional: purge the 64.5MB DB blob from git history with filter-repo.

---