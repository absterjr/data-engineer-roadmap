# Modeling Notes — one dataset, three models

This is the written half of Phase 3: the same StarMart data modeled three ways, with the actual outputs from the scripts. Read this after running the pipeline once.

```bash
python scripts/seed.py             # 1,200 customers · 300 products · 25,000 orders · 64,789 lines
python scripts/build_warehouse.py  # star DDL + ETL + indexes (reconciles to the cent)
python scripts/anomalies.py        # watch the legacy schema rot (all rolled back)
python scripts/compare.py          # same question, three schemas
```

The data is deterministic (`random.seed(42)`), so every number below reproduces exactly.

---

## 1. The legacy flat table — the anti-pattern

`legacy_orders`: one wide table, one row per order line, with the customer's name/email/city/country **and** the product's name/category copied into every row. It has no primary key, no foreign keys, no CHECK constraints — and **no status column at all**.

It reads fine. Here is what it does under pressure, from `scripts/anomalies.py`:

```
1. UPDATE ANOMALY — one customer, two cities
  customer            : aarav.barnes879@proton.me
  cities before       : ['Paris']
  cities after        : ['Paris', 'Newtown']   <-- the anomaly
  3NF equivalent      : 1 row updated — consistent by design

2. INSERT ANOMALY — the catalog cannot grow without a sale
  inserted with order_id=None, customer=None
  -> a catalog entry pretending to be an order line
  3NF equivalent      : INSERT INTO products — works standalone

3. DELETE ANOMALY — the customer exists only inside their order
  deleted all 8 line(s) for hugo.hughes898@gmail.com
  legacy rows left    : 0   <-- the customer is gone
  3NF equivalent      : customer_id 898 still exists in customers
```

The mechanism in all three: **one fact, stored many times**.

- The city `Paris` lived in 8 rows, so "update the customer's city" has 8 chances to fail partially. It did.
- A product is only representable as part of an order, so a new catalog item becomes a fake order with `NULL` customer.
- A customer is only representable through their orders, so deleting the orders deletes the customer.

No amount of careful SQL fixes this. It's the model.

---

## 2. Normalization: 1NF → 2NF → 3NF

The fix (`sql/02_normalized_3nf.sql`) splits "what a row is ABOUT" into one table per thing:

| Form | Rule | In this schema |
|------|------|----------------|
| **1NF** | every cell holds one atomic value | no comma-separated lists, no repeating groups |
| **2NF** | 1NF + no partial dependency | composite key `order_items(order_id, line_no)`: every column needs both halves |
| **3NF** | 2NF + no transitive dependency | city/country depend on the *customer*, not the order → `addresses`; category depends on the *product* → `categories` |

```mermaid
erDiagram
    customers ||--o{ addresses : has
    customers ||--o{ orders : places
    orders ||--o{ order_items : contains
    products ||--o{ order_items : "sold as"
    categories ||--o{ products : classifies
```

**What normalization buys:** every fact lives in exactly one place, so an update is atomic, an insert can't invent context, a delete can't orphan anything. The constraints do the enforcing: `CHECK (quantity > 0)`, `UNIQUE(email)`, `REFERENCES ...` — a typo like a 10% discount stored as `10` is rejected at write time.

**What it costs:** joins. A question about revenue-by-category-for-German-customers has to walk **six tables** (see §6).

---

## 3. Dimensional modeling: the star schema

Normalization optimizes for correct *writes*. Analytics optimizes for fast, simple *reads*. A star schema (`sql/03_star_schema.sql`) is built for the second job:

```mermaid
erDiagram
    fact_sales }o--|| dim_date : "date_key"
    fact_sales }o--|| dim_customer : "customer_key"
    fact_sales }o--|| dim_product : "product_key"
    fact_sales {
        int sales_key PK
        int order_id "degenerate dim"
        int line_no
        int date_key FK
        int customer_key FK
        int product_key FK
        int quantity "measure"
        real unit_price "measure"
        real discount_pct "measure"
        real gross_amount "measure"
        real discount_amount "measure"
        real net_revenue "measure"
        text order_status
    }
    dim_date {
        int date_key PK
        int year
        int quarter
        int month
        int day_of_week
        int is_weekend
    }
    dim_customer {
        int customer_key PK "surrogate"
        int customer_id "natural"
        text city
        text country
    }
    dim_product {
        int product_key PK "surrogate"
        int product_id "natural"
        text category "flattened"
        real list_price
    }
```

Four decisions, in order:

1. **Grain:** one row = one order line. Declared first; dimensions must describe exactly that.
2. **Facts = measures:** the five numeric columns you sum/divide. **Dimensions = context:** who/what/when, plus attributes to filter and group by.
3. **Surrogate keys:** `customer_key`/`product_key` are dense integers owned by the warehouse — independent of source IDs, which stay as ordinary columns for lineage. Integer joins are the cheapest joins.
4. **Star, not snowflake:** `category` is flattened into `dim_product` instead of joining `categories`. One less join on the hot path. Snowflaking reintroduces the hierarchy when you genuinely need it.

Two honest caveats (the kind of thing models are judged on):

- `dim_customer` stores the **current default address only**. Customer history (slowly changing dimensions) is deliberately out of scope — the trade-off is documented, not accidental.
- `order_status` in the fact is a **current-state attribute**, not a history. A cancelled order overwrites its status; true status history needs an SCD or a separate factless fact table.

---

## 4. The ETL

`sql/04_etl_3nf_to_star.sql` — dimensions first, then the fact.

| Star table | Source | Transformation |
|------------|--------|----------------|
| `dim_date` | generated | recursive CTE walks every date between MIN and MAX order dates → 731 rows |
| `dim_customer` | `customers` + default `addresses` | flatten; surrogate key via `ROW_NUMBER()` |
| `dim_product` | `products` + `categories` | flatten category name; surrogate key |
| `fact_sales` | `order_items` + `orders` | map to dimension keys; compute measures once |

Measures are computed **in the ETL**, not in every query — that's how every report agrees with every other report.

**Reconciliation** (`build_warehouse.py`) recomputes revenue independently on the source and compares:

```
star net revenue   : 11,410,030.36
3NF source revenue : 11,410,030.36
match              : YES
```

A first version of that check failed by exactly **£0.50** — because the star rounds money **per line** while the check summed unrounded values. Aggregating rounded values ≠ rounding the aggregate. That's the classic reason two dashboards disagree, and the check now compares like with like.

---

## 5. Same question, three schemas

The question: *"Revenue by category, for German customers, in 2025, excluding cancelled and returned orders."* From `scripts/compare.py`:

| Schema | Joins | Tables touched | Result | Median time |
|--------|-------|----------------|--------|-------------|
| Legacy flat | 0 | 1 | **£489,293.69** — wrong | 8.3 ms |
| 3NF | 5 | 6 | £462,873.27 | 15.4 ms |
| Star | 3 | 4 | £462,873.31 | 6.2 ms |

Three lessons in one table:

1. **The simplest query is wrong.** The flat table has no status column, so cancelled and returned lines cannot be excluded — it overstates revenue by **£26,420.38 (5.7%)**. It cannot even *ask* the question. Fewest joins, wrong answer: the most dangerous kind of simple.
2. **3NF and star agree to 4 pence** — the gap is line-level rounding, not a modeling difference. Correct models reconcile.
3. **The star is the fastest correct option**: 3 joins instead of 5, and measures pre-computed in the ETL. (Timings at 64k rows are illustrative; the structural argument — fewer joins, no re-deriving measures — is what scales.)

---

## 6. Indexing the fact table

The fact table's foreign keys are the join paths every query walks. `build_warehouse.py` indexes all three.

Date-range plan **with** `idx_fact_date`:

```
SEARCH fact_sales USING INDEX idx_fact_date (date_key>? AND date_key<?)
```

**Without** it:

```
SCAN fact_sales
```

Same story as Phase 1's `InvoiceDate` index — except here it's not one query, it's the join path of *every* analytical query. The monthly-grouping query shows the payoff directly:

```
SCAN d
SEARCH f USING INDEX idx_fact_date (date_key=?)
USE TEMP B-TREE FOR GROUP BY
```

`dim_date` is tiny (731 rows), so scanning it is free; the fact table (64,789 rows) is *searched*.

---

## 7. Transactions

From `scripts/anomalies.py`, the atomicity demo:

```
4. TRANSACTIONS — atomicity in 6 lines
  a two-step update failed mid-way -> rolled back
  discount total before: 3472.75
  discount total after : 3472.75
  unchanged            : YES
```

A transaction is all-or-nothing. Half-applied multi-step changes are how databases end up in states that "nobody could have caused". `BEGIN ... ROLLBACK` is the undo button — and it's also why the anomaly demos above can be safely re-run forever.

---

## 8. What the warehouse answers

Sample results from `sql/05_analytical_queries.sql`:

- **Monthly revenue:** seasonal by construction — 2024 November peaks at **£699,250.69** across 1,489 orders.
- **Weekend share:** weekdays **£9.97M (87.4%)** vs weekends **£1.44M (12.6%)** — a B2B-shaped business, same signature as Phase 1's retail dataset.
- **Discount leakage:** surprisingly flat — **5.4–5.6%** of gross across every category (Home & Living highest at 5.57%). No category is discount-addicted; the policy is uniform.
- **Top customer:** Isla Brooks (UK), **£41,667.96** across 83 orders.
- **Status mix 2025:** delivered 83.3%, shipped 9.3%, cancelled 3.3%, returned 2.1%, placed 1.9%.
- **QoQ growth by category:** available from the window-function query (`LAG` over quarterly totals) — the star's simplicity is what makes adding window functions trivial.

---

## 9. Takeaways

1. **Normalize for writes, star for reads.** They are layers, not rivals: 3NF protects the source of truth; the star serves analytics.
2. **The grain decides everything.** Declare it before designing anything else.
3. **A simple query on a broken model is still a wrong answer** — legacy was the fastest and the only wrong one.
4. **Reconcile your ETL to the cent** — and compare like with like (per-line rounding).
5. **Constraints are the model.** Types don't stop a `10` where `0.10` belongs; `CHECK` does.
