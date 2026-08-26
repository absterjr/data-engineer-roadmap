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