# Phase 3 — Journal

Day-by-day log for the databases & data modeling phase. Every entry links the commit(s) it covers.

---

## Entry 1 — Phase 3 scaffolded: StarMart, three models, one dataset

**Date:** 2026-09-07

**Commit(s):** (this entry)

**What I did**

- Created StarMart: a fictional e-commerce company with ~25k orders over two years, loaded three ways — legacy flat table, 3NF schema, star schema.
- Wrote the SQL suite: legacy anti-pattern DDL, 3NF DDL with real constraints, star schema DDL, ETL (3NF → star, including a recursive CTE to generate the date dimension), and six analytical queries.
- Wrote the Python tooling: deterministic data generator, warehouse builder, anomaly demo, and a same-question/three-schemas comparison with timings.

**What I learned so far**

- **The grain decision is the whole warehouse.** "One row per order line" must be chosen before anything else; every query and every dimension hangs off it.
- **Normalization and star schemas are not rivals** — they solve different problems (correct writes vs fast, simple reads). The same data wants both, at different layers.

**Next steps**

- Read the anomaly outputs, study the join-count comparison, then read `docs/MODELING.md` end to end.

---
