"""load — the gold layer: silver CSV becomes a queryable warehouse.

THE IDEMPOTENCY CONTRACT (the heart of this phase):

    dims  : INSERT ... ON CONFLICT DO NOTHING   — dimensions are lookup
            tables; re-loading them changes nothing
    fact  : INSERT ... ON CONFLICT DO UPDATE    — the UPSERT: a re-run
            UPDATES existing (city, day) rows instead of duplicating
            them. Run the load 100 times; the fact table's row count
            never moves.

Compare with the broken pipeline's plain INSERT: its re-runs DUPLICATE
rows, and every downstream average quietly drifts. Idempotency is not a
nice-to-have; it's what makes 'just re-run it' safe advice.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

CITY_META = {
    "London":     ("United Kingdom", 51.51, -0.13),
    "Manchester": ("United Kingdom", 53.48, -2.24),
    "Edinburgh":  ("United Kingdom", 55.95, -3.19),
    "Paris":      ("France",         48.85, 2.35),
    "Berlin":     ("Germany",        52.52, 13.40),
    "Amsterdam":  ("Netherlands",    52.37, 4.90),
    "Madrid":     ("Spain",          40.42, -3.70),
}

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def load_all(ctx: dict) -> dict:
    """Silver CSV -> gold SQLite, inside ONE transaction.

    A single transaction means a failure anywhere rolls back everything:
    the warehouse is never left half-loaded. (The broken pipeline loads
    row by row, so a crash mid-load leaves a partial state nobody can
    distinguish from a complete one.)
    """
    gold_db = Path(ctx["gold_db"])
    silver_file = Path(ctx["silver_dir"]) / "weather.csv"
    gold_db.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(gold_db)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((Path(ctx["schema_file"])).read_text(encoding="utf-8"))

    # --- dims first (the fact references their keys) ------------------------
    for city, (country, lat, lon) in CITY_META.items():
        con.execute(
            "INSERT INTO dim_city (city_name, country, lat, lon) VALUES (?,?,?,?) "
            "ON CONFLICT(city_name) DO NOTHING",
            (city, country, lat, lon),
        )

    seen_dates = set()
    with silver_file.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        date = r["date"]
        if date in seen_dates:
            continue
        seen_dates.add(date)
        y, m, d = (int(x) for x in date.split("-"))
        from datetime import date as _date
        wd = _date(y, m, d).weekday()
        con.execute(
            "INSERT INTO dim_date (date_key, full_date, year, month, day, day_name, is_weekend) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(full_date) DO NOTHING",
            (int(f"{y}{m:02d}{d:02d}"), date, y, m, d,
             DAY_NAMES[(wd + 1) % 7], 1 if wd >= 5 else 0),
        )

    # --- the fact, as an UPSERT ----------------------------------------------
    upserted = 0
    for r in rows:
        city_key = con.execute(
            "SELECT city_key FROM dim_city WHERE city_name = ?", (r["city"],)
        ).fetchone()[0]
        date_key = int(r["date"].replace("-", ""))
        values = (
            city_key, date_key,
            r["temp_mean_c"] if r["temp_mean_c"] not in ("", None) else None,
            r["precip_mm"] if r["precip_mm"] not in ("", None) else None,
            r["wind_max_kph"] if r["wind_max_kph"] not in ("", None) else None,
        )
        # SQLite reports rowcount 1 for both the insert and the update
        # branch — either way exactly ONE (city, day) row exists after.
        con.execute(
            "INSERT INTO fact_daily_weather (city_key, date_key, temp_mean_c, precip_mm, wind_max_kph) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(city_key, date_key) DO UPDATE SET "
            "temp_mean_c = excluded.temp_mean_c, "
            "precip_mm = excluded.precip_mm, "
            "wind_max_kph = excluded.wind_max_kph",
            values,
        )
        upserted += 1

    con.commit()

    fact_rows = con.execute("SELECT COUNT(*) FROM fact_daily_weather").fetchone()[0]
    ctx["load"] = {
        "silver_rows": len(rows),
        "fact_rows": fact_rows,
        "dim_cities": con.execute("SELECT COUNT(*) FROM dim_city").fetchone()[0],
        "dim_dates": con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0],
    }
    con.close()
    return ctx["load"]