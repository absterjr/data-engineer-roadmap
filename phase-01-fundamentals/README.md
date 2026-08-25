# Phase 1 — Fundamentals

SQL + Python, from the ground up.

> **Status:** 🔜 in progress

## What this phase covers

- **SQL:** joins, window functions, CTEs, query optimization
- **Python:** data structures, OOP, error handling, file I/O

## First-principles project

Build a tiny relational engine in pure Python that reads CSVs and implements `SELECT`, `WHERE`, `JOIN`, `GROUP BY` and basic aggregation — **no SQL libraries**. This teaches how SQL actually works under the hood.

## The dataset

**Online Retail** — transactional e-commerce records from a UK retailer ([UCI: Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)). ~541k rows, 8 columns:

`InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`

- Source workbook: `data/Online Retail.xlsx`
- Converted for the engine: `data/online_retail.csv`

Run the engine against it:

```bash
python src/engine.py data/online_retail.csv
```

If you'd rather try another dataset: [NYC Taxi trip data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), [Titanic on Kaggle](https://www.kaggle.com/c/titanic/data), or anything else from [UCI](https://archive.ics.uci.edu/). Any CSV works — the engine just reads rows and columns.

## Rebuild task

Fix a set of poorly-optimized SQL queries, then rewrite them as clean, indexed, explainable queries.

## Resources

- [SQLBolt](https://sqlbolt.com) — interactive SQL exercises
- [Real Python](https://realpython.com/python-basics/) — Python fundamentals