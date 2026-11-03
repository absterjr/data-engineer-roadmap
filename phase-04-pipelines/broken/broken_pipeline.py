"""BROKEN PIPELINE — the fix-it-first exercise for Phase 4.

This script RUNS. It fetches weather, writes a CSV, loads a database,
and prints "Done!". It is also wrong in 8 different ways — find them.

    1. Run it twice:   python broken/broken_pipeline.py
    2. For each behavior below, find the bug behind it:
       - you cannot ask it for a date range (try backfilling March)
       - a transient network blip kills the whole run
       - re-running DUPLICATES rows in the database
       - one bad city silently drops every city after it
       - it prints "Done!" even when the API failed
       - a crash mid-load leaves a half-loaded database
       - outputs are keyed by TODAY's date, not the data's dates
    3. Fix them WITHOUT reading src/ (the rebuilt version) or
       broken_pipeline_fixed.py (the answer key).
    4. Done when: re-runs don't duplicate rows, failures are loud,
       and any date range is a backfill.

'It runs' is not 'it works'. 'Done!' is not 'succeeded'.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import urllib.request
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "broken_demo"

CITIES = {
    "London":     (51.51, -0.13),
    "Manchester": (53.48, -2.24),
    "Edinburgh":  (55.95, -3.19),
    "Paris":      (48.85, 2.35),
    "Berlin":     (52.52, 13.40),
    "Amsterdam":  (52.37, 4.90),
    "Madrid":     (40.42, -3.70),
}

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch(city: str, start: str, end: str) -> dict:
    """One city's weather. Fails = the whole pipeline fails."""
    lat, lon = CITIES[city]
    url = (f"{ARCHIVE_URL}?latitude={lat}&longitude={lon}&start_date={start}"
           f"&end_date={end}&daily=temperature_2m_mean,precipitation_sum,"
           f"wind_speed_10m_max&timezone=UTC")
    return json.load(urllib.request.urlopen(url, timeout=30))


def extract(start: str, end: str) -> list[dict]:
    """All cities -> flat rows. One bad city stops everything after it."""
    rows = []
    for city in CITIES:
        try:
            payload = fetch(city, start, end)
            daily = payload["daily"]
            for d, t, p, w in zip(daily["time"],
                                  daily["temperature_2m_mean"],
                                  daily["precipitation_sum"],
                                  daily["wind_speed_10m_max"]):
                rows.append({"city": city, "date": d, "temp": t,
                             "precip": p, "wind": w})
        except Exception:
            break
    return rows


def save_csv(rows: list[dict]) -> Path:
    """Rows -> CSV, one file per run (keyed by today)."""
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / f"weather_{date.today().isoformat()}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["city", "date", "temp",
                                               "precip", "wind"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def load(rows: list[dict]) -> None:
    """Rows -> SQLite, row by row, no transaction, no dedup."""
    db = DATA / "weather.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE IF NOT EXISTS weather (
        city TEXT, date TEXT, temp REAL, precip REAL, wind REAL)""")
    for r in rows:
        con.execute("INSERT INTO weather VALUES (?,?,?,?,?)",
                    (r["city"], r["date"], r["temp"], r["precip"], r["wind"]))
    con.commit()
    con.close()


def main() -> None:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=2)

    rows = extract(start, end)
    save_csv(rows)
    load(rows)

    n = len(rows)
    print(f"pipeline done! {n} rows for {start} .. {end}")


if __name__ == "__main__":
    main()