# Rebuild task — bad SQL, fixed SQL, and why

This folder contains the phase's **rebuild task**: the same analytical questions from `src/queries.py` (revenue by country, top products, monthly revenue), written first as **bad SQL**, then as **clean, indexed, explainable SQL**.

The point is not "memorize the right syntax". It's to learn the **why** — the mental model that tells you a query is bad before you even run it.

```bash
# 1. load the CSV into SQLite (takes a minute, 541k rows)
python scripts/setup_sqlite.py

# 2. run the bad queries, then the good ones
python scripts/run_sql.py sql/bad_queries.sql
python scripts/run_sql.py sql/good_queries.sql
```

These work from the repo root or from `phase-01-fundamentals/` — the scripts find their paths either way.

> The engine (`src/engine.py`) and these SQL queries answer the same questions and get the **same numbers**. Running both is a free cross-check: when two independent implementations agree, you can trust the answer.

---

## The one mental model that explains everything

SQL does **not** run your query top-to-bottom. It runs it in a fixed order:

```
FROM        pick the table(s) and join them
WHERE       throw away rows that don't match          <- rows, not groups
GROUP BY    pack the remaining rows into buckets
HAVING      throw away buckets that don't match       <- groups, not rows
SELECT      compute the output columns (aggregates happen here)
ORDER BY    sort the output
LIMIT       keep only the first N rows
```

Every bad query below violates this order somewhere. Keep it in your head and you'll spot the bugs before they reach production.

---

## Q1 — Total revenue by country (year 2011)

### The bad version

```sql
SELECT DISTINCT Country, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
WHERE InvoiceDate LIKE '%2011%'
GROUP BY Country
ORDER BY 2 DESC;
```

It runs. The numbers are even correct (37 countries, UK at $7.51M). Three problems:

**1. `LIKE '%2011%'` — the index-killing filter.** `LIKE` matches a *pattern*; a leading `%` means "anything before 2011". To decide whether a row matches, the database must read that row's value. It cannot jump ahead — so it reads **all 541,909 rows**. This is called a **non-sargable predicate** (not index-usable). The query plan proves it:

```
BEFORE index — bad Q1:
    SCAN online_retail                          <- reads every row
    USE TEMP B-TREE FOR GROUP BY
    USE TEMP B-TREE FOR DISTINCT                <- extra pass, see #2
    USE TEMP B-TREE FOR ORDER BY

AFTER index — bad Q1 (index on InvoiceDate exists!):
    SCAN online_retail                          <- STILL a full scan
    USE TEMP B-TREE FOR GROUP BY
    USE TEMP B-TREE FOR DISTINCT
    USE TEMP B-TREE FOR ORDER BY
```

Adding an index changed nothing — because a `%`-pattern can't use one. The fix is a **range predicate** on the actual date:

```sql
WHERE InvoiceDate >= '2011-01-01'
  AND InvoiceDate <  '2012-01-01'
```

`>= start AND < end` is the canonical "everything in the year" pattern (half-open interval: includes Jan 1 2011, excludes Jan 1 2012). With an index this becomes:

```
AFTER index — good Q1:
    SEARCH online_retail USING INDEX idx_online_retail_invoice_date (InvoiceDate>? AND InvoiceDate<?)
    USE TEMP B-TREE FOR GROUP BY
    USE TEMP B-TREE FOR ORDER BY
```

Three steps instead of four, and the scan became a *search* — SQLite jumps straight to the matching range. On 541k rows the difference is milliseconds here; on 500 million rows it's the difference between a query and an incident.

**2. `DISTINCT` after `GROUP BY` — asking for work twice.** Group keys are already unique — `DISTINCT` can't remove anything, but SQLite still builds a temporary B-tree to check (`USE TEMP B-TREE FOR DISTINCT`). Delete it. If a query has both, one of them is wrong.

**3. `ORDER BY 2` — the ordinal trap.** "Sort by the second column" is a promise about *position*. Add one column to the `SELECT` list and the query silently sorts by the wrong column. Name what you mean: `ORDER BY Revenue DESC`.

### The fixed version

```sql
SELECT Country,
       SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
WHERE InvoiceDate >= '2011-01-01'
  AND InvoiceDate <  '2012-01-01'
GROUP BY Country
ORDER BY Revenue DESC;
```

Same answer. Different plan. Every word names something real.

### Alternatives (all correct, different trade-offs)

```sql
-- Only countries above a threshold -> HAVING, not WHERE (see the bonus)
SELECT Country, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
WHERE InvoiceDate >= '2011-01-01' AND InvoiceDate < '2012-01-01'
GROUP BY Country
HAVING SUM(Quantity * UnitPrice) > 100000;

-- CTE: name the revenue formula once; keeps the query readable as it grows
WITH sales AS (
    SELECT Country, Quantity * UnitPrice AS Revenue
    FROM online_retail
    WHERE InvoiceDate >= '2011-01-01' AND InvoiceDate < '2012-01-01'
)
SELECT Country, SUM(Revenue) AS Revenue
FROM sales
GROUP BY Country
ORDER BY Revenue DESC;

-- Window function: country total shown next to every row (share-of-revenue later).
-- Overkill for a plain rollup, but this is the tool when you need BOTH
-- row-level detail AND the group total.
SELECT DISTINCT Country,
       SUM(Quantity * UnitPrice) OVER (PARTITION BY Country) AS CountryRevenue
FROM online_retail
WHERE InvoiceDate >= '2011-01-01' AND InvoiceDate < '2012-01-01';
```

---

## Q2 — Top 10 products by revenue

### The bad version

```sql
SELECT StockCode, Description, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY StockCode
ORDER BY Revenue DESC;
```

Two problems, and the first one is a *correctness* bug that looks fine.

**1. `Description` is not in `GROUP BY` — you asked SQL to invent a value.** You grouped by `StockCode`, but you also selected `Description`. Which description? SQLite picks *an arbitrary row's* value from each bucket. In stricter databases (PostgreSQL) this query doesn't even run; SQLite is "helpful" and silently hides the bug.

The dataset proves how dangerous this is. The same stock code can carry **several different descriptions** — 1,324 codes do:

```
StockCode  Description                        rows   Revenue
85123A     ?                                          1      0.00
85123A     CREAM HANGING HEART T-LIGHT HOLDER         9    178.51
85123A     WHITE HANGING HEART T-LIGHT HOLDER      2,302 97,715.99
85123A     wrongly marked carton 22804                1      0.00
```

The bad query lumps all four into one row, slaps the first-seen label on them ($97,894.50 "as" WHITE HANGING…), and hides $178.51 of real CREAM sales plus two junk rows. Grouping by `StockCode, Description` instead splits them — 5,752 groups vs 4,070 — and each variant gets its honest revenue.

**2. No `LIMIT 10`.** The question says "top 10"; the query returns **all 4,070 rows**. `ORDER BY ... LIMIT n` isn't cosmetic — it tells the engine it only needs to track the top n candidates.

### The fixed version

```sql
SELECT StockCode,
       Description,
       SUM(Quantity * UnitPrice) AS Revenue,
       SUM(Quantity)             AS Units,
       COUNT(*)                  AS Orders
FROM online_retail
GROUP BY StockCode, Description
ORDER BY Revenue DESC
LIMIT 10;
```

Two extra aggregates while we're here: `Units` and `Orders` — revenue alone hides whether a row is 1,000 sales of $1 or 1 sale of $1,000.

### Alternatives (all correct, different trade-offs)

```sql
-- One description per code, guaranteed deterministic: MAX() it.
-- Trade-off: alphabetically-last wins; variant granularity is lost.
SELECT StockCode, MAX(Description) AS Description, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY StockCode;

-- Rank instead of truncate: gives each product its rank in the output.
-- (This is a window function — Phase 1 skill list — see Q1's alternative.)
SELECT * FROM (
    SELECT StockCode, Description,
           SUM(Quantity * UnitPrice) AS Revenue,
           ROW_NUMBER() OVER (ORDER BY SUM(Quantity * UnitPrice) DESC) AS rn
    FROM online_retail
    GROUP BY StockCode, Description
)
WHERE rn <= 10;
```

---

## Q3 — Monthly revenue

### The bad version

```sql
SELECT substr(InvoiceDate, 1, 7) AS Month, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY 1
ORDER BY 1;
```

Three problems:

**1. `substr()` slices text instead of parsing a date.** `substr(InvoiceDate, 1, 7)` chops the first 7 characters — `'2010-12-01 08:26:00'` → `'2010-12'`. It works **only because this CSV stores dates in ISO format**. The day the format changes (say `12/1/2010`), the same query silently produces garbage: `'12/1/20'`. Dates are not strings. Parse them:

```sql
strftime('%Y-%m', InvoiceDate)
```

`strftime` understands the date and formats it — it survives format changes in a way text-slicing cannot.

**2. `GROUP BY 1` — the ordinal trap again** (same as `ORDER BY 2` in Q1). Group by the expression, not the position. Note we group by the full `strftime(...)` expression rather than the alias `Month` — some databases forbid aliases in `GROUP BY`, so the expression version is portable.

**3. Text sorting works here by accident.** `'2010-12' < '2011-01'` sorts correctly only because ISO text is chronological. Any other display format (`'12/2010'`) sorts wrong. Sort by something chronological — which ISO text is, by design.

### The fixed version

```sql
SELECT strftime('%Y-%m', InvoiceDate) AS Month,
       SUM(Quantity * UnitPrice)      AS Revenue
FROM online_retail
GROUP BY strftime('%Y-%m', InvoiceDate)
ORDER BY Month;
```

Same 13 rows, same numbers as the engine's Q3 (`2010-12` → `2011-12`). Two independent implementations agree — that's the cross-check.

### Know your data: the partial-month trap

Look at the last row: `2011-12 | 433,668.01`. A naive reading: "December crashed 70%!" No — **the dataset ends on 2011-12-09**. December has nine days of data, not thirty-one. A query can be syntactically perfect and analytically wrong.

```sql
-- Compare only complete months (trade-off: you drop the latest month)
SELECT strftime('%Y-%m', InvoiceDate) AS Month,
       SUM(Quantity * UnitPrice)      AS Revenue
FROM online_retail
WHERE InvoiceDate < '2011-12-01'
GROUP BY strftime('%Y-%m', InvoiceDate)
ORDER BY Month;
```

There's no SQL syntax for "except the partial month" — you have to *know* your data's boundaries. That's the part no index can fix.

---

## Bonus — the one that doesn't even run

```sql
SELECT Country, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
WHERE SUM(Quantity * UnitPrice) > 100000   -- ERROR: misuse of aggregate: SUM()
GROUP BY Country;
```

The most common beginner mistake, in one line. It fails because of the order of operations at the top of this page: **`WHERE` runs before `GROUP BY`** — at that point, groups don't exist yet, so `SUM()` has nothing to sum. Aggregates live in `HAVING` (filter groups) or `SELECT` (compute values):

```sql
SELECT Country, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY Country
HAVING SUM(Quantity * UnitPrice) > 100000
ORDER BY Revenue DESC;
```

Result: 6 countries above $100k. Remember it as: **`WHERE` filters rows, `HAVING` filters groups.**

---

## Indexing: what the index actually did

An **index** is like the index at the back of a book: a sorted list that says "2011 — see rows 400,000–530,000", so the engine doesn't read every page. SQLite's index is a B-tree — a sorted structure that makes range lookups (`>=`, `<`, `BETWEEN`, equality) near-instant.

```sql
CREATE INDEX IF NOT EXISTS idx_online_retail_invoice_date
    ON online_retail(InvoiceDate);
```

The plan difference, measured on the same 541,909 rows:

| Query | Plan before index | Plan after index |
|-------|-------------------|------------------|
| `LIKE '%2011%'` | `SCAN online_retail` | `SCAN online_retail` — **no change** |
| `substr(InvoiceDate,1,4) = '2011'` | `SCAN online_retail` | `SCAN online_retail` — **no change** |
| `InvoiceDate >= ... AND < ...` | `SCAN online_retail` | `SEARCH ... USING INDEX idx_...` |

The table says it all: **an index only helps if the predicate lets it help.** A leading wildcard (`LIKE '%…'`) or a function wrapped around the column (`substr(InvoiceDate, …)`) hides the value from the index — both still full-scan. This is the "sargable" idea from Q1: the predicate must be *searchable*.

And indexes are not free. Every `INSERT`/`UPDATE`/`DELETE` must also maintain the index, and it costs disk space. The rule of thumb: **index the columns your queries actually filter on** — not every column you can think of. One index on `InvoiceDate` is enough here; `Country` gets grouped but rarely range-filtered.

---

## Cheat sheet: bad habit → fix

| Bad habit | Why it's bad | The fix |
|-----------|--------------|---------|
| `LIKE '%2011%'` | Leading wildcard can't use an index | `>= '2011-01-01' AND < '2012-01-01'` |
| Function on a column in `WHERE` | Index sees the raw value, not the result | Compute the range instead (`strftime`-free predicates) |
| `SELECT DISTINCT` + `GROUP BY` | One of them is doing nothing | Keep `GROUP BY`, drop `DISTINCT` |
| `ORDER BY 2` / `GROUP BY 1` | Sorts/groups by position — silently breaks when columns change | Name the column or alias |
| Column in `SELECT` but not in `GROUP BY` | Database invents an arbitrary value | Group by it, or aggregate it (`MAX()`) |
| No `LIMIT` on a "top N" question | Returns everything | `ORDER BY ... LIMIT N` |
| `substr()` on a date | Slices text instead of parsing a date | `strftime('%Y-%m', ...)` |
| `WHERE SUM(...) > x` | Aggregates don't exist before grouping | `HAVING SUM(...) > x` |
| No index on filtered column | Every query reads all 541k rows | `CREATE INDEX` on the filtered column |

*The engine and these SQL files answer the same questions with the same numbers — that is the point. If you find a discrepancy, it's a bug in one of them. Open an issue.*