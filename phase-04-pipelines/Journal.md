# Phase 4 — Journal

Day-by-day log for the pipelines phase. Every entry links the commit(s) it covers.

---

## Entry 1 — Phase 4 scaffolded: medallion pipeline + mini-Airflow

**Date:** 2026-11-03

**Commit(s):** [`17b67f9`](https://github.com/absterjr/data-engineer-roadmap/commit/17b67f9) — "feat(phase-4): weather pipeline - medallion architecture + mini-Airflow"

**What I did**

- Chose a free keyless public API (Open-Meteo archive) feeding a weather pipeline for StarMart's top cities.
- Built `src/orchestrator.py` — Airflow's three ideas in ~150 lines: tasks with retries/backoff, `>>` dependencies, Kahn topological sort, and a persistent `pipeline_runs` history (which makes re-runs idempotent via task caching).
- Built the medallion layers: bronze (raw immutable JSON keyed by range), silver (validated CSV, atomic write), gold (SQLite warehouse, UPSERT load) — plus an audit task with veto power and a CLI that treats any date range as a backfill.
- Built the broken/fixed pair (8 seeded bugs, 7 silent) and the full write-up in docs/PIPELINE-NOTES.md.

**What I learned**

- **Monitoring earns its keep immediately.** Within hours, the audit task caught a real design bug — my transform processed ALL bronze files, so a September backfill silently pulled in October's data. A pipeline needs a task whose entire job is to distrust the other tasks.
- **Three idempotency strategies, one per layer:** bronze = cache-by-filename (immutable), silver = regenerate wholesale (atomic), gold = UPSERT (keyed). Each is the right tool for its layer's immutability.
- **Schemas must not drop themselves.** The first draft's DDL dropped the tables on every load — every run destroyed the previous one. Accumulate by default; wipe explicitly.
- **The broken/fixed numbers tell the story better than prose:** 2 runs of the broken script → 84 rows with only 21 distinct pairs (63 duplicates); 2 runs of the fixed → 49 stable.

**Next steps**

- Read `docs/PIPELINE-NOTES.md` end to end; run the broken exercise.
- Optional stretch: retry backpressure (per-request sleep on rate-limit responses), a `freshness` alert (fail if the newest date in gold is older than N days).

---
