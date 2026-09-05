# Phase 2 — Journal

Day-by-day log for the EDA phase. Every entry links the commit(s) it covers.

---

## Entry 1 — Phase 2 scaffolded: vizz library, broken EDA, business questions

**Date:** 2026-09-03

**Commit(s):** [`fda49b4`](https://github.com/absterjr/data-engineer-roadmap/commit/fda49b4) — "feat(phase-2): EDA scaffold - vizz library, broken EDA, business questions"

**What I did**

- Scaffolded `phase-02-eda/` around three deliverables: fix-broken-code-first, a from-scratch chart library, and three business questions.
- Built `src/vizz/` — a pure-Python SVG chart library, zero third-party imports:
  - `Figure` with margins, titles, 1-2-5 "nice" axis ticks, gridlines, and a cycling palette
  - `barh`, `bar`, `line`, `histogram`, `scatter`
  - `vizz.ascii` for the terminal: `barh`, `histogram`, `sparkline` (▁▂▃▄▅▆▇█)
- Built `src/clean.py` — the cleaning pipeline with documented decisions (cancelled invoices, returns, missing CustomerID, zero prices each get an explicit rule).
- Built `src/analysis.py` — answers three business questions with charts:
  1. Revenue concentration across customers (Pareto)
  2. Seasonality (monthly, day-of-week, hour-of-day)
  3. Returns — which products, how much
- Wrote `broken/broken_eda.py` — a script that runs and prints confident wrong answers (7 seeded bugs), plus `broken/README.md` with the rules of the exercise.

**What I learned**

- SVG is just text — a chart library is mostly *scale math*: mapping data values to pixels, and picking axis ticks humans like (1-2-5 pattern). Once the scale is right, every chart type is ~15 lines.
- Writing the broken version first forced me to enumerate the mistakes I'd actually made in Phase 1 (dropna on everything, sum×mean instead of sum of products, chained assignment).

**Questions / blockers**

- Should vizz grow a donut/stacked-bar before Phase 2 ships, or is bar/line/histogram/scatter enough?

**Next steps**

- Fix all seven bugs in `broken/broken_eda.py` without peeking at `src/`, then diff against the rebuilt version.
- Run the analysis, read the charts, write the business answers into the phase README.

---

## Entry 2 — Beginner comment pass (cross-phase)

**Date:** 2026-09-04

**Commit(s):** [`6542722`](https://github.com/absterjr/data-engineer-roadmap/commit/6542722) — "docs: beginner comments across all python code (phases 1 & 2)"

**What I did**

- Re-commented all Phase 2 Python for beginners: `vizz/svg.py` now opens with the four-step "how a chart library works" (reserve space → scale → ticks → emit strings), the 1-2-5 tick algorithm is walked through line by line, and every chart documents its geometry (slots, draw order, the scale formula). `ascii.py`, `clean.py`, and `analysis.py` got the same treatment.
- Removed the bug markers from `broken/broken_eda.py` — they made the exercise trivial. Bugs and output verified unchanged.

**What I learned**

- Comments that explain the SCALE FORMULA once (`pixel = start + value/max * size`) do more for a beginner than any API list — every chart is that formula wearing different geometry.

---
