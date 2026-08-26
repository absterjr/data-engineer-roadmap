# Phase 1 — Fundamentals

SQL + Python, from the ground up.

> **Status:** 🔨 in progress

## What this phase covers

- **SQL:** joins, window functions, CTEs, query optimization
- **Python:** data structures, OOP, error handling, file I/O

## First-principles project

Build a tiny relational engine in pure Python that reads CSVs and implements `SELECT`, `WHERE`, `JOIN`, `GROUP BY` and basic aggregation — **no SQL libraries**. This teaches how SQL actually works under the hood.

## The dataset

**Online Retail** — transactional e-commerce records from a UK retailer ([UCI: Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)). ~541k rows, 8 columns:

`InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`

The dataset is **not committed** to the repo (it's large). Get it with:

```bash
python scripts/fetch_online_retail.py   # downloads xlsx + converts to data/online_retail.csv
```

Run the engine against it:

```bash
python src/engine.py data/online_retail.csv
```

If you'd rather try another dataset: [NYC Taxi trip data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), [Titanic on Kaggle](https://www.kaggle.com/c/titanic/data), or anything else from [UCI](https://archive.ics.uci.edu/). Any CSV works — the engine just reads rows and columns.

## Query workouts (Day 2)

`src/queries.py` answers five analytical questions using **only engine operations** (WHERE, GROUP BY, JOIN, ORDER BY, LIMIT, aggregates) — no SQL libraries:

```bash
python src/queries.py
```

1. **Total revenue by country** — UK leads at $8.19M (82% of all revenue); Netherlands, Ireland (EIRE), Germany follow.
2. **Top products by revenue** — `DOTCOM POSTAGE` (postage charges!) tops the list at $206k.
3. **Monthly revenue** — clear seasonality: peaks in Nov 2011 ($1.46M), dips Jan–Feb.
4. **Revenue by region** — JOIN against `data/country_region.csv` (38 countries → 8 regions).
5. **Data quality** — 135,080 rows (25%) have no `CustomerID`, 10,624 have negative `Quantity` (returns), 9,288 are on cancelled invoices (`C...`).

The engine supports: `read_csv` (with type coercion), `project` (SELECT), `where` (WHERE), `extend` (computed columns), `join` (INNER JOIN), `group_by` + aggregates (`count`, `sum_`, `mean`, `min_`, `max_`), `order_by`, `limit`.

## Rebuild task

Fix a set of poorly-optimized SQL queries, then rewrite them as clean, indexed, explainable queries.

## Resources

- [SQLBolt](https://sqlbolt.com) — interactive SQL exercises
- [Real Python](https://realpython.com/python-basics/) — Python fundamentals