"""run_pipeline — the weather pipeline as a DAG, with a CLI.

    python src/run_pipeline.py --start 2026-10-01 --end 2026-10-14
    python src/run_pipeline.py --status        # run history
    python src/run_pipeline.py --reset         # wipe history + data

The DAG (see the >> wires below):

    extract ──> transform ──> load ──> audit
         └──> manifest ──────┘

Every task is idempotent at its own layer (bronze files = cache key,
silver = regenerable, gold = UPSERT), so re-running the same range is a
no-op and any past range is a backfill. The run_id is the date range —
that's what makes "re-run yesterday" and "backfill October" the same
operation.

The audit task is the pipeline's conscience: it verifies the warehouse
against the source counts and FAILS the run if they disagree — a
pipeline that prints "Done" without checking is the broken_pipeline.py
exercise in one line.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from extract import CITIES, extract_all
from load import load_all
from orchestrator import DAG
from transform import transform_all

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BRONZE = DATA / "bronze"
SILVER = DATA / "silver"
GOLD_DB = DATA / "weather_gold.sqlite"
META_DB = DATA / "pipeline_meta.sqlite"
SCHEMA = ROOT / "sql" / "gold_schema.sql"


def task_manifest(ctx: dict) -> None:
    """Write a run manifest: what this run claimed to cover."""
    run_key = f"__{ctx['start']}__{ctx['end']}.json"
    manifest = {
        "run_id": ctx["run_id"],
        "cities": ctx["cities"],
        "start": ctx["start"],
        "end": ctx["end"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bronze_files": sorted(p.name for p in BRONZE.glob("*.json")
                               if p.name.endswith(run_key)),
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                        encoding="utf-8")


def task_audit(ctx: dict) -> dict:
    """Verify THIS RUN's slice of the warehouse agrees with its silver.

    Gold accumulates across backfills, so the audit checks the run's own
    date range (not the whole warehouse):
      1. fact rows inside [start, end] == silver rows      (load dropped?)
      2. every city covered within the range               (partial data?)
      3. every day of the range present for every city     (gaps?)
    Any mismatch RAISES — the run is marked failed, which is the
    alerting. Silent success is how pipelines rot.
    """
    silver_rows = sum(1 for _ in csv.DictReader(
        (SILVER / "weather.csv").open(newline="", encoding="utf-8")))

    con = sqlite3.connect(GOLD_DB)
    fact_rows = con.execute(
        "SELECT COUNT(*) FROM fact_daily_weather "
        "WHERE date_key BETWEEN ? AND ?",
        (int(ctx["start"].replace("-", "")), int(ctx["end"].replace("-", ""))),
    ).fetchone()[0]
    cities_in_range = con.execute(
        "SELECT COUNT(DISTINCT city_key) FROM fact_daily_weather "
        "WHERE date_key BETWEEN ? AND ?",
        (int(ctx["start"].replace("-", "")), int(ctx["end"].replace("-", ""))),
    ).fetchone()[0]
    distinct_dates = con.execute(
        "SELECT COUNT(DISTINCT date_key) FROM fact_daily_weather "
        "WHERE date_key BETWEEN ? AND ?",
        (int(ctx["start"].replace("-", "")), int(ctx["end"].replace("-", ""))),
    ).fetchone()[0]
    total_rows = con.execute("SELECT COUNT(*) FROM fact_daily_weather").fetchone()[0]
    con.close()

    days = (datetime.strptime(ctx["end"], "%Y-%m-%d")
            - datetime.strptime(ctx["start"], "%Y-%m-%d")).days + 1

    problems = []
    if fact_rows != silver_rows:
        problems.append(f"fact rows in range {fact_rows} != silver rows {silver_rows}")
    if cities_in_range != len(ctx["cities"]):
        problems.append(f"cities in range {cities_in_range} != {len(ctx['cities'])}")
    if distinct_dates != days:
        problems.append(f"dates in range {distinct_dates} != {days} expected")
    if fact_rows != days * len(ctx["cities"]):
        problems.append(f"expected {days * len(ctx['cities'])} rows, found {fact_rows}")

    summary = {
        "range_rows": fact_rows,
        "silver_rows": silver_rows,
        "cities": cities_in_range,
        "days": distinct_dates,
        "warehouse_total": total_rows,
    }
    ctx["audit"] = summary

    print("    audit summary (this run's range):")
    for k, v in summary.items():
        print(f"      {k:<14} {v}")
    if problems:
        raise RuntimeError("audit failed: " + "; ".join(problems))
    print("    audit passed: this range's slice is complete and consistent")
    return summary


def build_dag() -> DAG:
    dag = DAG("weather_pipeline", META_DB)

    @dag.task("extract", retries=2, backoff=1.5)
    def extract(ctx):
        return extract_all(ctx)

    @dag.task("manifest", retries=0)
    def manifest(ctx):
        return task_manifest(ctx)

    @dag.task("transform", retries=1)
    def transform(ctx):
        return transform_all(ctx)

    @dag.task("load", retries=1)
    def load(ctx):
        return load_all(ctx)

    @dag.task("audit", retries=0)
    def audit(ctx):
        return task_audit(ctx)

    # the wiring: extract feeds transform AND manifest; load needs both
    # transform and manifest; audit runs last
    extract >> transform
    extract >> manifest
    transform >> load
    manifest >> load
    load >> audit
    return dag


def make_ctx(start: str, end: str, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "start": start,
        "end": end,
        "cities": list(CITIES),
        "bronze_dir": BRONZE,
        "silver_dir": SILVER,
        "gold_db": GOLD_DB,
        "schema_file": SCHEMA,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="StarMart weather pipeline")
    parser.add_argument("--start", help="YYYY-MM-DD (default: 14 days ago)")
    parser.add_argument("--end", help="YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--force", action="store_true",
                        help="re-run tasks even if they succeeded before")
    parser.add_argument("--status", action="store_true", help="show run history")
    parser.add_argument("--reset", action="store_true", help="wipe history + data")
    args = parser.parse_args()

    dag = build_dag()

    if args.status:
        dag.status()
        return

    if args.reset:
        dag.reset()
        for p in [BRONZE, SILVER, GOLD_DB, DATA / "manifest.json"]:
            if p.is_dir():
                for f in p.glob("*"):
                    f.unlink()
                p.rmdir()
            elif p.exists():
                p.unlink()
        print("reset: data dirs cleared")
        return

    today = datetime.now(timezone.utc).date()
    end = args.end or (today - timedelta(days=1)).isoformat()
    start = args.start or (today - timedelta(days=14)).isoformat()

    run_id = f"{start}__{end}"
    ctx = make_ctx(start, end, run_id)
    ok = dag.run(ctx, run_id)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()