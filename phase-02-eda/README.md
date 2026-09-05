# Phase 2 — EDA

Exploratory data analysis on the same Online Retail dataset — from basic charts to a visualization library built from scratch.

> **Status:** 🔨 in progress

> **New here?** The dataset and its quirks are documented in [phase-01-fundamentals](../phase-01-fundamentals/README.md) — start with [HOW-IT-WORKS.md](../phase-01-fundamentals/HOW-IT-WORKS.md) if the engine and dataset are new to you.

## What this phase covers

- **pandas / numpy:** cleaning, groupby, resampling, cumulative statistics
- **EDA method:** univariate → bivariate → business questions, with documented cleaning decisions
- **Visualization:** basic charts → a pure-Python chart library built from scratch (zero third-party imports)

## The three deliverables

### 1. Fix the broken EDA first (`broken/`)

`broken/broken_eda.py` runs end-to-end and prints confident, authoritative — and wrong — conclusions. Seven bugs are hiding in it: silent data loss, wrong math, mislabeled results, a pandas chained-assignment trap, and a crash. Find and fix them all **before** looking at `src/` (the rebuilt version). See [broken/README.md](broken/README.md).

### 2. `vizz` — a chart library from scratch (`src/vizz/`)

No matplotlib, no PIL, no third-party anything — stdlib only. SVG is just text, so pure Python can draw:

- `Figure` — axes with nice 1-2-5 ticks, gridlines, titles, palette
- Standard: `barh` / `bar` / `line` / `histogram` / `scatter`
- Unconventional: `calendar_heatmap` (GitHub-style day grid), `slope` (before/after), `ridgeline` (joyplot distributions), `waffle` (100 countable squares)
- `vizz.ascii` — terminal charts: `barh`, `histogram`, and `sparkline` (▁▂▃▄▅▆▇█)

```python
from vizz import Figure
fig = Figure(900, 500, "Monthly revenue")
fig.line(months, revenue)
fig.save("charts/monthly_revenue.svg")
```

### 3. Three business questions (`src/analysis.py`)

| # | Question | Charts | Answer |
|---|----------|--------|--------|
| Q1 | How concentrated is revenue across customers? | `pareto_customers.svg` | **Top 10% of customers drive 61% of revenue; just 212 customers (4.9%) cover 50%.** Retention of that tier > broad acquisition. |
| Q2 | When do people buy? | `monthly_revenue.svg`, `revenue_by_dow.svg`, `revenue_by_hour.svg` | **November peak** (holiday gifting), Thursday is the best weekday (20.7% of weekly revenue), peak hours 10:00–15:00. Staff and stock *before* Nov. |
| Q3 | What comes back — money or stock? | `top_written_off_products.svg` | **Two different problems hiding under one label:** cancellations refund **£897k (8.4% of gross)** — a commercial question; write-offs (1,336 rows at zero price — "printing smudges/thrown away") are damaged stock — an operations question. |

Bonus: order-value distribution (`order_value_histogram.svg`) — mean £534 vs median £304: a few huge wholesale orders pull the average up.

Run it:

```bash
python src/analysis.py        # prints the report, writes charts/*.svg
```

The dataset is reused from Phase 1 — get it with `python scripts/fetch_online_retail.py` from the repo root if you don't have it.

> **The headliner finding:** the dataset's "returns" are two completely different phenomena wearing one label. Cancellations (C-invoices) refund **£897k — 8.4% of gross sales**. The negative-quantity rows on normal invoices all have **UnitPrice = 0** — they're damaged-stock write-offs ("printing smudges/thrown away"), costing *nothing* in revenue. Most analyses of this dataset conflate the two.

## What's in this folder

```
phase-02-eda/
├── README.md              # you are here
├── Journal.md             # day-by-day log with commit links
├── broken/                # fix-it-first exercise (do this BEFORE reading src/)
│   ├── broken_eda.py      #   the buggy script - find the 8 bugs
│   ├── broken_eda_fixed.py#   the corrected twin - compare side by side
│   └── README.md          #   rules, hints, answers
├── src/vizz/              # the from-scratch chart library (SVG + ASCII)
├── src/clean.py           # documented cleaning pipeline
├── src/analysis.py        # business questions answered with EDA
└── charts/                # generated SVG charts (committed — they're just text)
```

## The unconventional charts

Standard charts answer "how much per category". These four answer questions bars can't:

| Chart | File | Question it answers |
|-------|------|---------------------|
| Calendar heatmap | `calendar_nov2011.svg` | What did *every single day* of the peak month look like? (weekly cycle, end-of-month push, dead weekends — as texture) |
| Slope | `slope_countries.svg` | How did each top market move H1 → H2 2011? (UK +50%, EIRE +56%, Australia −29% — direction is the message) |
| Ridgeline | `ridgeline_order_values.svg` | How does the *shape* of order values differ per quarter? (medians barely move; the volume grows) |
| Waffle | `waffle_regions.svg` | Revenue share in 100 countable squares — 85 of them are the UK |

## Resources

- [pandas docs](https://pandas.pydata.org/docs/) · [seaborn tutorials](https://seaborn.pydata.org/tutorial.html) (for comparison — what vizz is NOT)
- [MDN: SVG tutorial](https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial) — what vizz generates under the hood
