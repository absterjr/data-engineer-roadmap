# Pipeline Notes — medallion architecture, orchestration, idempotency

The written half of Phase 4: how the weather pipeline is built, why each
layer behaves the way it does, and what the measured evidence says.

```bash
python src/run_pipeline.py --start 2026-10-01 --end 2026-10-14   # any range = a backfill
python src/run_pipeline.py --status                              # run history
```

---

## 1. The pipeline, in one picture

```
                 Open-Meteo archive API (free, no key)
                            │
   extract (retries=2) ─────┤──> bronze/  <city>__<start>__<end>.json
        │                   │        raw responses, immutable, one file per city
        ├──> manifest  ─────┘
        │
   transform (retries=1) ───> silver/  weather.csv   (this run's range only)
        │                          clean typed rows, atomically replaced
        │
   load (retries=1) ────────> gold/    weather_gold.sqlite
        │                          dim_city + dim_date + fact_daily_weather
        │                          UPSERT — row count never changes on re-run
        │
   audit (retries=0) ───────> pipeline_runs (meta DB) + exit code
                               verifies the range's slice; fails loudly
```

The DAG wiring (`src/run_pipeline.py`):

```python
extract >> transform
extract >> manifest
transform >> load
manifest >> load
load >> audit
```

`extract` feeds BOTH `transform` and `manifest`; `load` waits for both
branches to merge. That merge is the shape every real orchestrator
exists to express.

## 2. The orchestrator: Airflow's three ideas in ~150 lines

`src/orchestrator.py` implements what Airflow/Prefect package, so each
idea is visible instead of magical:

| Concept | Implementation |
|---------|----------------|
| **Task** | a function + metadata: retries, backoff, upstream dependencies |
| **DAG** | tasks wired with `>>`; `run()` executes them in dependency order |
| **Topological sort** | Kahn's algorithm — repeatedly emit tasks with no pending dependencies; if anything is stuck at the end, it's a cycle, and the DAG refuses to run |
| **Retries** | N extra attempts, exponential backoff (`2s, 4s, ...`) — networks fail at random, not at convenient times |
| **Run history** | `pipeline_runs` table: run_id, task, status, attempts, timestamps, error — the same table Airflow's UI renders |

Idempotency falls out of the run history: a task that already succeeded
for this `run_id` is **cached** unless `--force`:

```
=== DAG weather_pipeline — run 2026-10-01__2026-10-14 (incremental) ===
  [cached] extract (already succeeded for this run)
  [cached] manifest ...
  [cached] transform ...
  [cached] load ...
  [cached] audit ...
=== DAG weather_pipeline: SUCCESS ===
```

`--status` reads the history back:

```
  2026-10-01__2026-10-14  audit      succeeded  attempts=1 13:30:14 -> 13:30:14
  2026-10-01__2026-10-14  load       succeeded  attempts=1 13:30:14 -> 13:30:14
  ...
```

## 3. Idempotency, layer by layer

Every layer is idempotent in a *different* way — the three standard ones:

| Layer | Strategy | Why |
|-------|----------|-----|
| **bronze** | file named `<city>__<start>__<end>.json`; existing file = "already fetched" | raw data is immutable; the filename IS the cache key |
| **silver** | regenerated wholesale each run, written atomically (temp file + rename) | derived data; a crash can't leave a half-written CSV |
| **gold** | `PRIMARY KEY (city_key, date_key)` + `ON CONFLICT DO UPDATE` | the UPSERT: re-loading updates rows instead of duplicating them |

The measured contrast with the broken pipeline (which uses a plain
INSERT and no keys):

```
broken:  2 runs -> 84 rows in the DB, only 21 distinct (city, date) pairs
fixed :  2 runs -> 49 rows, 49 distinct — stable forever
```

63 duplicated rows from two innocent re-runs. Every average computed on
that table quietly drifts. That's what idempotency is FOR.

## 4. Backfills — and the bug the audit caught

Any date range is a backfill: `--start 2026-09-20 --end 2026-09-23` after
October had been loaded, and gold accumulated correctly:

```
gold total rows (both backfills): 126   (= 98 + 28, no overlap lost)
gold date span                  : 2026-09-20 .. 2026-10-14
```

But the first backfill attempt **failed the run** — and that was the
audit doing its job. The original `transform` processed ALL bronze files,
so a September backfill picked up October's files and silver silently
spanned two ranges:

```
attempt 1 failed: audit failed: date range 2026-09-20..2026-10-14 != 2026-09-20..2026-09-23
[FAIL]   audit
=== DAG weather_pipeline: FAILURE ===
```

The fix (filtering bronze by the range embedded in the filename) is in
`transform.py` — and the lesson is the meta-lesson: **a pipeline needs a
task whose entire job is to distrust the other tasks.** The audit caught
a real design bug within hours of the pipeline existing. Monitoring is
not "nice to have when you scale up"; it's how bugs become loud instead
of silent.

The audit's checks, per run:

1. fact rows inside `[start, end]` == silver rows (load dropped/duplicated?)
2. all 7 cities present within the range (partial coverage?)
3. every day of the range present (gaps?)

Any mismatch raises → the task fails → the DAG fails → exit code 1 → a
scheduler (or CI) notices. Compare the broken pipeline's
`print("Done!")`, which prints no matter what happened.

## 5. The gold warehouse

`sql/gold_schema.sql` follows Phase 3's star pattern at a smaller scale —
and one deliberate difference: `CREATE TABLE IF NOT EXISTS`, **no DROPs**.
The warehouse accumulates across runs and backfills; wiping it is an
explicit `--reset`, never a side effect of loading. (The first draft
dropped its own tables on every load — which made every run destroy the
previous one. A schema file that drops its own tables turns loading
into a destructive operation.)

```
fact_daily_weather grain: ONE ROW PER (CITY, DAY) — the composite
primary key is both the dedup key AND the idempotency mechanism.
```

## 6. The rebuild task: broken → fixed → rebuilt

`broken/broken_pipeline.py` has 8 seeded bugs (7 silent, 1 loud) — the
full list, hints, and answers are in `broken/README.md`. The fix stage
is `broken/broken_pipeline_fixed.py` (same shape, `BUG n FIX` comments);
the rebuild stage is `src/` (medallion layers + orchestrator + audit).
Three stages, three different lessons:

- **Fix**: the 8 mistakes, one at a time
- **Rebuild**: the architecture that makes those mistakes *impossible*
  (immutable bronze, UPSERT gold, an audit task with veto power)

## 7. Takeaways

1. **Idempotency is the definition of re-runnable.** "Just run it again"
   must always be safe advice — bronze caching, atomic silver, UPSERT
   gold make it so.
2. **The filename is metadata.** `<city>__<start>__<end>.json` made
   filtering, caching, and backfills all fall out of one decision.
3. **Monitoring is a task, not an afterthought.** The audit failed a
   real bug within hours; the broken pipeline's "Done!" has lied
   forever.
4. **Retries with backoff are table stakes.** Networks fail at random;
   a pipeline without retries is a pipeline that fails at 3am for no
   reason.
5. **A schema that drops its own tables destroys on load.** Accumulate
   by default; wipe explicitly.
