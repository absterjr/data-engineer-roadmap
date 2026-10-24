# Phase 3 — Databases & Data Modeling

One dataset, three models: a legacy flat table with every anomaly in the book → a normalized 3NF schema → a dimensional star schema for analytics. Then we measure why the star wins.

> **Status:** 🔨 in progress

> **Prerequisite:** Phase 1's SQL rebuild task ([phase-01-fundamentals/sql/README.md](../phase-01-fundamentals/sql/README.md)) introduces SQLite and EXPLAIN QUERY PLAN — this phase assumes both.

## What this phase covers

- **Normalization:** 1NF → 2NF → 3NF, and the three anomalies it prevents
- **Dimensional modeling:** grain, facts, dimensions, surrogate keys, star vs snowflake
- **ETL:** loading a 3NF source into a star schema (SQL, not Python)
- **Indexing:** fact-table indexes and query plans on a 70k-row fact table
- **Transactions:** atomicity, and what ROLLBACK is for

## The project: StarMart

A fictional e-commerce company ("StarMart") with ~25,000 orders across two years. The same data is loaded three ways:

```
sql/01_legacy_flat.sql     legacy_orders    one wide table — the anti-pattern
sql/02_normalized_3nf.sql  customers, products, orders, ...  — the fix
sql/03_star_schema.sql     fact_sales + dim_* — the warehouse
sql/04_etl_3nf_to_star.sql the ETL: 3NF -> star (recursive CTE for dim_date)
sql/05_analytical_queries.sql   six business questions against the star
```

Run order:

```bash
python scripts/seed.py             # generates data, loads legacy + 3NF
python scripts/build_warehouse.py  # star DDL + ETL + indexes
python scripts/run_sql.py sql/05_analytical_queries.sql
python scripts/anomalies.py        # watch the legacy schema rot in real time
python scripts/compare.py          # same question, three schemas: joins + timings
```

## The rebuild task

Take the schema with redundancy and update anomalies (`01_legacy_flat.sql`), fix it to 3NF (`02`), then rebuild it as a dimensional star schema (`03`). The anomalies aren't hypothetical — `scripts/anomalies.py` demonstrates each one on the legacy table and shows the 3NF equivalents:

| Anomaly | On `legacy_orders` | On 3NF |
|---------|--------------------|--------|
| **Update** | Change one customer's city in half their rows → the same customer now lives in two cities | One `UPDATE addresses` → always consistent |
| **Insert** | A new product can't be recorded until someone buys it | `INSERT INTO products` works standalone |
| **Delete** | Delete a customer's last order → the customer ceases to exist | Deleting orders never touches `customers` |

## What's in this folder

```
phase-03-databases/
├── README.md          # you are here
├── Journal.md         # day-by-day log with commit links
├── docs/MODELING.md   # the write-up: anomalies, normalization, star schema, results
├── sql/               # DDL + ETL + analytical queries
├── scripts/           # seed, warehouse build, anomaly demo, comparison, runner
└── data/              # starmart.db (gitignored, fully regenerable)
```

## Resources

- [PostgreSQL docs](https://www.postgresql.org/docs/) — the DDL here is SQLite-flavored but portable
- [Star schema (Wikipedia)](https://en.wikipedia.org/wiki/Star_schema) — the canonical reference
- [Kimball dimensional modeling techniques](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/) — the source of the gospel
