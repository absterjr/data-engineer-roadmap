# Phase 3 — Journal

Day-by-day log for the databases & data modeling phase. Every entry links the commit(s) it covers.

---

## Entry 1 — Phase 3 scaffolded: StarMart, three models, one dataset

**Date:** 2026-09-07

**Commit(s):** [`9f21bf6`](https://github.com/absterjr/data-engineer-roadmap/commit/9f21bf6) — "feat(phase-3): StarMart - three models, one dataset"

**What I did**

- Created StarMart: a fictional e-commerce company (1,200 customers, 300 products, 25,000 orders, 64,789 order lines over 2024–2025, deterministic seed) loaded three ways — legacy flat table, 3NF schema, star schema.
- Wrote the SQL suite: legacy anti-pattern DDL, 3NF DDL with real constraints, star schema DDL, ETL (3NF → star, including a recursive CTE to generate the 731-row date dimension), and six analytical queries.
- Wrote the Python tooling: generator, warehouse builder with cent-level reconciliation, anomaly demo (all changes rolled back), and a same-question/three-schemas comparison.
- Wrote `docs/MODELING.md` with the real outputs, mermaid ERDs, and every lesson — including two I hit while building:
  - reconciliation failed by exactly £0.50 → per-line rounding vs sum-then-round
  - the delete-anomaly demo initially "deleted" a NULL email → in SQL, NULL never equals NULL

**What I learned so far**

- **The grain decision is the whole warehouse.** "One row per order line" must be chosen before anything else; every query and every dimension hangs off it.
- **Normalization and star schemas are not rivals** — they solve different problems (correct writes vs fast, simple reads). The same data wants both, at different layers.
- **Correctness is the real comparison axis:** the legacy schema ran the fastest (8.3 ms) and was the only wrong answer (5.7% overstated) — because it cannot exclude cancellations at all.

**Next steps**

- Read `docs/MODELING.md` end to end, then the six analytical queries.
- Optional stretch: slowly changing dimension for customer addresses; a `fact_returns` table.

---

