# Phase 4 — Journal

Day-by-day log for the pipelines phase. Every entry links the commit(s) it covers.

---

## Entry 1 — Phase 4 scaffolded: medallion pipeline + mini-Airflow

**Date:** 2026-11-03

**Commit(s):** (this entry)

**What I did**

- Chose a free keyless public API (Open-Meteo archive) and verified it returns daily temperature/precipitation/wind per city.
- Scaffolded `phase-04-pipelines/` around four deliverables: the broken pipeline (fix-it-first), a from-scratch orchestrator, the medallion pipeline itself, and the run-history/monitoring layer.

**What I learned so far**

- **Bronze must be immutable.** The raw API response is the only artifact that can be replayed; anything that overwrites it makes backfills impossible.

**Next steps**

- Build `src/orchestrator.py` (tasks, `>>` deps, retries, run history), then extract/transform/load, then the broken pair.

---
