# Phase 4 — Pipelines (ETL / ELT + orchestration)

An end-to-end pipeline with a real public API source, a medallion architecture, and an orchestrator built from scratch — plus the fix-it-first broken pipeline.

> **Status:** 🔨 in progress

## What this phase covers

- **Extract:** hitting a public API (Open-Meteo, no key needed) with retries and backoff
- **Medallion architecture:** bronze (raw, immutable) → silver (cleaned) → gold (warehouse)
- **Orchestration:** a mini-DAG engine written by hand — tasks, dependencies, retries, run history (the same concepts Airflow/Prefect package)
- **Idempotency & backfills:** re-running is safe, and history is reconstructable for any date range
- **Monitoring:** a run-history table + an audit task that fails loudly instead of "Done" lying to you

## The project: a weather pipeline for StarMart's cities

StarMart's warehouse (Phase 3) would love to know whether weather moves sales. This pipeline feeds it: daily weather (temperature, precipitation, wind) for the top store cities, from the [Open-Meteo archive API](https://open-meteo.com/) (free, no API key):

```
bronze/  raw API responses, one JSON file per city, immutable
silver/  clean rows: city, date, temp_c, precip_mm, wind_kph (CSV)
gold/    SQLite warehouse: dim_city + dim_date + fact_daily_weather
```

The pipeline itself is defined as a DAG in `src/run_pipeline.py`:

```
extract ──> transform ──> load ──> audit
     └──> manifest ──────┘
```

Run it:

```bash
python src/run_pipeline.py --start 2026-10-01 --end 2026-10-14   # backfill any range
python src/run_pipeline.py --status                              # run history from the meta DB
python src/run_pipeline.py --reset                               # wipe state for a clean demo
```

The orchestrator (`src/orchestrator.py`) is ~150 lines of pure Python: tasks with `>>` dependencies, topological execution (Kahn's algorithm), retries with backoff, and a persistent run-history table — a miniature Airflow, with every concept named and commented.

## The rebuild task

`broken/broken_pipeline.py` is the one-off script someone left behind: hard-coded dates, no retries, non-idempotent loads (re-runs duplicate rows), no validation, and it prints "Done" even when the API failed. Find the 8 bugs, fix them, then compare with `broken/broken_pipeline_fixed.py` — the corrected twin — and with the rebuilt production version in `src/`.

See [broken/README.md](broken/README.md).

## What's in this folder

```
phase-04-pipelines/
├── README.md              # you are here
├── Journal.md             # day-by-day log with commit links
├── broken/                # fix-it-first exercise (8 seeded bugs)
├── src/
│   ├── orchestrator.py    # the mini-Airflow: Task, DAG, retries, run history
│   ├── extract.py         # API -> bronze (retry/backoff, immutable files)
│   ├── transform.py       # bronze -> silver (parse + validate)
│   ├── load.py            # silver -> gold (SQLite, UPSERT = idempotent)
│   └── run_pipeline.py    # the DAG definition + CLI
├── sql/gold_schema.sql    # dim_city + dim_date + fact_daily_weather
├── docs/PIPELINE-NOTES.md # the write-up
└── data/                  # bronze/, silver/, gold + meta DBs (all gitignored)
```

## Resources

- [Airflow docs](https://airflow.apache.org/docs/) — compare our mini-DAG against the real thing
- [Open-Meteo archive API](https://open-meteo.com/en/docs/historical-weather-api) — the free source used here
- [The medallion architecture (Databricks)](https://www.databricks.com/glossary/medallion-architecture) — bronze/silver/gold explained
