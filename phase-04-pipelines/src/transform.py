"""transform — the silver layer: raw JSON becomes clean, typed rows.

WHAT SILVER MEANS: one flat table, one row per (city, date, metric set),
validated. Raw JSON stays untouched in bronze; silver is where "clean"
happens, and the validation here is the pipeline's quality gate:

  - a city file with zero usable rows FAILS the task (empty data is a
    data problem, not something to load silently)
  - individual NULL metrics are kept (weather stations do miss values)
    but COUNTED and reported — the audit task will see them
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


def transform_city(bronze_file: Path) -> list[dict]:
    """One bronze JSON file -> clean row dicts.

    The API returns parallel arrays under 'daily' (one list per metric,
    same order). zip() stitches them into rows: each row is one day.
    """
    payload = json.loads(bronze_file.read_text(encoding="utf-8"))
    daily = payload["daily"]
    city = bronze_file.name.split("__")[0]

    rows = []
    for date, temp, precip, wind in zip(
        daily["time"],
        daily["temperature_2m_mean"],
        daily["precipitation_sum"],
        daily["wind_speed_10m_max"],
    ):
        rows.append({
            "city": city,
            "date": date,
            "temp_mean_c": temp,      # may be None — flagged, not dropped
            "precip_mm": precip,
            "wind_max_kph": wind,
        })
    if not rows:
        raise ValueError(f"{bronze_file.name}: no daily rows to transform")
    return rows


def transform_all(ctx: dict) -> dict:
    """Bronze files FOR THIS RUN'S RANGE -> one silver CSV.

    Bronze accumulates files from every backfill; silver is rebuilt per
    run and must contain EXACTLY this run's range — so the files are
    filtered by the range embedded in their names (<city>__<start>__<end>).
    (Skipping this filter was the pipeline's first real design bug: a
    backfill of September picked up October's bronze files, silver
    silently spanned two ranges, and the audit task caught it. Filters
    like this are why filenames must be self-describing.)

    Silver is DERIVED data: it can always be regenerated from bronze, so
    this task rewrites the whole CSV each run. That is what makes the
    layer idempotent — unlike bronze (immutable) and gold (UPSERT).
    """
    bronze = Path(ctx["bronze_dir"])
    silver_file = Path(ctx["silver_dir"]) / "weather.csv"
    silver_file.parent.mkdir(parents=True, exist_ok=True)

    run_key = f"__{ctx['start']}__{ctx['end']}.json"
    files = sorted(f for f in bronze.glob("*.json") if f.name.endswith(run_key))
    if not files:
        raise RuntimeError(
            f"no bronze files for {ctx['start']}..{ctx['end']} in {bronze} "
            f"(extract must run first)"
        )

    all_rows, null_cells = [], 0
    for f in files:
        rows = transform_city(f)
        all_rows.extend(rows)
        null_cells += sum(
            1 for r in rows for k in ("temp_mean_c", "precip_mm", "wind_max_kph")
            if r[k] is None
        )

    # atomic write: write a temp file, then rename. A crash mid-write
    # can't leave a half-written CSV that the next layer trusts.
    tmp = silver_file.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["city", "date", "temp_mean_c",
                                               "precip_mm", "wind_max_kph"])
        writer.writeheader()
        writer.writerows(all_rows)
    tmp.replace(silver_file)

    ctx["transform"] = {
        "rows": len(all_rows),
        "files": len(files),
        "null_cells": null_cells,
        "cities": len({r["city"] for r in all_rows}),
    }
    return ctx["transform"]