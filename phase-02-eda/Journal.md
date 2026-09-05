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

## Entry 3 — Side-by-side fixes + four unconventional charts

**Date:** 2026-09-05

**Commit(s):** [`b69cc0a`](https://github.com/absterjr/data-engineer-roadmap/commit/b69cc0a) — "feat(phase-2): side-by-side fixed EDA + four unconventional chart types"

**What I did**

- Added `broken/broken_eda_fixed.py` — the corrected twin with identical functions and report, every fix carrying a `BUG n FIX` comment. Verified its numbers match `src/analysis.py` (£10.7M, 84.6%, month 11, 4,372 customers, 1,336 write-offs).
- Added four unconventional chart types to vizz, fully commented:
  - `calendar_heatmap` — GitHub-style day grid; discovered my first draft had a dead lambda and sloppy week math — the comment pass caught it before commit
  - `slope` — before/after lines, mint-up/coral-down, one shared y-scale
  - `ridgeline` — shared-bin joyplot; draw order (back-to-front) IS the whole trick
  - `waffle` — 100 squares with largest-remainder rounding (naive rounding gives 99 or 101 squares — verified 100)
- Wired all four to the dataset in `analysis.py`.

**What I learned**

- **Side-by-side is a teaching format, not a convenience.** Same function names, same report lines — the diff IS the lesson.
- **The unconventional charts earned their keep immediately**: the slope chart exposed a story the Pareto view hid (Australia shrank 29% into H2 while UK grew 50%); the ridgeline showed order-value *shape* barely moves while volume grows.
- **Largest-remainder rounding** is the kind of unglamorous math every chart library hides — 6 categories sharing 100 squares doesn't survive naive rounding.

**Questions / blockers**

- Should the waffle legend shrink-wrap for many categories, or is "fold the rest into Rest" the right guidance?

**Next steps**

- Learner exercise: fix the 8 bugs in `broken_eda.py`, compare with `broken_eda_fixed.py`.
- Written EDA report (the phase's final deliverable) — possibly as the Phase 2 LinkedIn post source.

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
