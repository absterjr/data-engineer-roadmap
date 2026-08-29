# How the engine works — a beginner's guide

This page explains, in plain language, what `src/engine.py` and `src/queries.py` are, and how the code answers questions about the dataset. No prior knowledge assumed.

---

## 1. What a table is

A **table** is just a grid of data: **rows** (each row = one transaction) and **columns** (each column = one kind of information).

| InvoiceNo | Quantity | UnitPrice | Country |
|-----------|----------|-----------|---------|
| 536365    | 6        | 2.55      | United Kingdom |
| 536365    | 6        | 3.39      | United Kingdom |
| 536366    | 1        | 3.39      | Netherlands |

A **CSV file** is the same grid written as plain text — one row per line, columns separated by commas. It's the simplest way to store a table, which is why we use it here.

`data/online_retail.csv` is one big table: **541,909 rows** (transactions) × **8 columns** (invoice number, product, quantity, price, date, customer, country…).

---

## 2. What the engine is

`src/engine.py` is a **tiny database written in pure Python**. A real database (PostgreSQL, SQL Server, even the one inside pandas) understands the language **SQL**. Our engine doesn't understand SQL — instead, we implement the *same building blocks* as Python functions:

- `read_csv` → load a CSV into a table
- `project` → SQL's `SELECT` (pick which columns to keep)
- `where` → SQL's `WHERE` (keep only rows that match a condition)
- `extend` → SQL's `SELECT ... AS` (compute a new column)
- `join` → SQL's `JOIN` (glue two tables together)
- `group_by` → SQL's `GROUP BY` (bucket rows and summarize each bucket)
- `order_by` → SQL's `ORDER BY` (sort)
- `limit` → SQL's `LIMIT` (keep only the first N rows)

If you can learn these 8 functions, you have already learned how SQL works under the hood — that's the whole point of this phase.

---

## 3. What queries.py is

`src/queries.py` is a file that **asks the engine questions about the dataset** and prints the answers in neat, aligned tables.

Each function in the file is one question:

| Function | Question it answers |
|----------|---------------------|
| `q1_total_revenue_by_country` | Which countries bring in the most money? |
| `q2_top_products` | Which products sell the most money? |
| `q3_monthly_revenue` | Does revenue change month to month? |
| `q4_revenue_by_region` | What if we group countries into regions? (uses JOIN) |
| `q5_data_quality` | How messy is the data? (missing values, returns, cancellations) |

You run it with:

```bash
python src/queries.py
```

---

## 4. How one question flows through the engine

Let's follow **Q1 — total revenue by country** step by step. In SQL it would look like this:

```sql
SELECT Country, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY Country
ORDER BY Revenue DESC
LIMIT 10;
```

Here's the same question, one engine step at a time:

```python
sales = read_csv(DATA)                      # 1. load the whole table
sales = extend(                              # 2. add a "Revenue" column
    sales,
    lambda r: (r["Quantity"] or 0) * (r["UnitPrice"] or 0),
    "Revenue",
)
by_country = group_by(                       # 3. bucket rows by Country
    sales,
    ["Country"],
    {"Revenue": sum_("Revenue")},            #    and sum Revenue per bucket
)
top = limit(                                 # 5. keep only the first 10
    order_by(by_country, "Revenue", desc=True),  # 4. sort, biggest first
    10,
)
```

1. **Load** the CSV into a table.
2. **Compute** a new `Revenue` column for every row: quantity × price. (`or 0` means "if the value is missing, treat it as zero").
3. **Bucket** all rows by country, and for each bucket add up the revenue — like `SUM(...) GROUP BY Country`.
4. **Sort** the buckets from biggest revenue to smallest.
5. **Keep** only the top 10.

The result is the table you see printed — 10 countries with their total revenue.

---

## 5. SQL ↔ engine cheat sheet

| SQL | Engine function |
|-----|-----------------|
| `SELECT a, b FROM t` | `project(table, ["a", "b"])` |
| `WHERE x > 5` | `where(table, lambda r: r["x"] > 5)` |
| `SELECT a*b AS c` | `extend(table, lambda r: r["a"]*r["b"], "c")` |
| `GROUP BY k` + `SUM(v)` | `group_by(table, ["k"], {"s": sum_("v")})` |
| `COUNT(*)` | `count` |
| `AVG(v)` | `mean("v")` |
| `ORDER BY k DESC` | `order_by(table, "k", desc=True)` |
| `LIMIT 10` | `limit(table, 10)` |
| `INNER JOIN ... ON a.k = b.k` | `join(a, b, "k", "k")` |

---

## 6. Glossary

- **Table / dataset** — a grid of rows and columns.
- **Row** — one record (here: one product line on one invoice).
- **Column** — one field of every record (here: quantity, price, country…).
- **CSV** — a text file that stores a table (comma-separated values).
- **`lambda r: ...`** — a tiny inline function that takes a row `r` and returns a value. E.g. `lambda r: r["Quantity"]` means "give me the Quantity of this row".
- **Aggregate** — a function that summarizes many rows into one number: `SUM`, `COUNT`, `AVG`, `MIN`, `MAX`.
- **NULL / missing** — an empty value. Real data is full of them; the engine turns blank cells into `None`.
- **Coerce** — converting a text value into a number (e.g. turning the string `"6"` into the number `6`).
- **JOIN key** — the column two tables share, used to glue them together (here: `Country` in both tables).
- **Predicate** — a condition that is either true or false for a row; `where` keeps rows where it's true.

---

*Confused by something? Open an issue on GitHub — this guide is for you.*