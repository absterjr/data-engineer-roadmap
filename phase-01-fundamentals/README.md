# Phase 1 — Fundamentals

SQL + Python, from the ground up.

> **Status:** ✅ complete — shipped with a published LinkedIn post; the repo is featured on the profile.

> **New here?** Read [HOW-IT-WORKS.md](HOW-IT-WORKS.md) first — it explains what the engine and the queries file are, in plain language, with a SQL-to-engine cheat sheet and a glossary.

> **Follow along:** [Journal.md](Journal.md) logs each day's work, and every entry links the commit(s) it covers.

## What's in this folder

```
phase-01-fundamentals/
├── README.md          # you are here
├── HOW-IT-WORKS.md    # beginner's guide to the engine and queries
├── Journal.md         # day-by-day log with commit links
├── src/engine.py      # the mini relational engine (pure Python, no SQL libs)
├── src/queries.py     # eight analytical questions answered with the engine
├── sql/bad_queries.sql    # rebuild task: the poorly-written versions
├── sql/good_queries.sql   # rebuild task: the fixed, indexed versions
├── sql/README.md          # rebuild task: detailed explanations + alternatives
├── sql/window_functions.sql # window-functions workout (Q6-Q8, RANK vs DENSE_RANK)
└── data/              # gitignored: online_retail.csv, online_retail.db
                       # (regenerate with scripts/fetch_online_retail.py and
                       #  scripts/setup_sqlite.py); country_region.csv is tracked
```

## What this phase covers

- **SQL:** joins, window functions, CTEs, query optimization
- **Python:** data structures, OOP, error handling, file I/O

## First-principles project

Build a tiny relational engine in pure Python that reads CSVs and implements `SELECT`, `WHERE`, `JOIN`, `GROUP BY` and basic aggregation — **no SQL libraries**. This teaches how SQL actually works under the hood.

## The dataset

**Online Retail** — transactional e-commerce records from a UK retailer ([UCI: Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)). ~541k rows, 8 columns:

`InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`

The dataset is **not committed** to the repo (it's large). Get it with — from the repo root:

```bash
python scripts/fetch_online_retail.py   # downloads xlsx + converts to data/online_retail.csv
```

Run the engine against it — from inside this folder (`phase-01-fundamentals/`):

```bash
python src/engine.py data/online_retail.csv
```

If you'd rather try another dataset: [NYC Taxi trip data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), [Titanic on Kaggle](https://www.kaggle.com/c/titanic/data), or anything else from [UCI](https://archive.ics.uci.edu/). Any CSV works — the engine just reads rows and columns.

## Query workouts (Day 2)

`src/queries.py` answers eight analytical questions using **only engine operations** — no SQL libraries. Run it from inside this folder:

```bash
python src/queries.py
```

1. **Total revenue by country** — UK leads at $8.19M (84% of all revenue); Netherlands, Ireland (EIRE), Germany follow.
2. **Top products by revenue** — `DOTCOM POSTAGE` (postage charges!) tops the list at $206k.
3. **Monthly revenue** — clear seasonality: peaks in Nov 2011 ($1.46M), dips Jan–Feb.
4. **Revenue by region** — JOIN against `data/country_region.csv` (38 countries → 8 regions).
5. **Data quality** — 135,080 rows (25%) have no `CustomerID`, 10,624 have negative `Quantity` (returns), 9,288 are on cancelled invoices (`C...`).
6. **Top 3 products per country, per month** — `ROW_NUMBER` over a `(Country, Month)` partition.
7. **Cumulative monthly revenue** — running total over months: $9.75M by Dec 2011.
8. **Revenue share by country** — `PARTITION SUM` without a key = grand total; UK holds 84%.

The engine supports: `read_csv` (with type coercion + clear errors), `project` (SELECT), `where` (WHERE), `extend` (computed columns), `join` (INNER + LEFT, hash-based), `group_by` + aggregates (`count`, `sum_`, `mean`, `min_`, `max_`), `order_by`, `limit`, and window functions (`row_number`, `rank`, `dense_rank`, `running_sum`, `partition_sum`).

The same questions are answered in SQL — see [sql/README.md](sql/README.md) and [sql/window_functions.sql](sql/window_functions.sql). Engine and SQL agree on every number; that cross-check is the point.

## Rebuild task

Fix a set of poorly-optimized SQL queries, then rewrite them as clean, indexed, explainable queries.

Done — see [sql/README.md](sql/README.md) for the full breakdown: bad queries, fixed queries, what was wrong in each, real `EXPLAIN QUERY PLAN` output before/after indexing, and the alternative ways each query could be written. Runs from anywhere in the repo:

```bash
python scripts/setup_sqlite.py                # CSV -> SQLite (once)
python scripts/run_sql.py sql/bad_queries.sql # find the problems
python scripts/run_sql.py sql/good_queries.sql # then read why they were fixed
```

## Resources

- [SQLBolt](https://sqlbolt.com) — interactive SQL exercises
- [Real Python](https://realpython.com/python-basics/) — Python fundamentals