# Phase 1 — Journal

Personal notes on what I did, what I learned, and what's next. This is the log for this phase's journey — the README stays project-facing, this is mine.

---

## Entry 1 — Dataset loaded, engine runs

**Date:** 2026-08-25

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