"""FIXED PIPELINE — the corrected twin of broken_pipeline.py.

    python broken/broken_pipeline_fixed.py --start 2026-10-01 --end 2026-10-14

Same script, same shape — only the 8 bugs are fixed. Every fix carries a
`BUG n FIX` comment: what was wrong, why it was dangerous, what correct
looks like. Read side by side with broken_pipeline.py.

(The production-grade rebuild of this logic lives in src/ — bronze/silver/
gold, orchestrator, audit task. This file is the FIX stage; src/ is the
REBUILD stage. Both matter.)
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
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
    """One city's weather, WITH retries and validation.

    BUG 2 FIX (no retry): one urlopen, no second chance. Networks fail
    at random; a pipeline that can't absorb a transient blip is a
    pipeline that fails at 3am for no reason. Retry with backoff.

    BUG 3 FIX (no validation): the broken script trusted the payload
    blindly — an API error envelope ({"error": true, "reason": ...})
    would crash it mid-run, or worse, feed garbage downstream. Check
    for the block you need BEFORE using it, and say why when it's gone.
    """
    lat, lon = CITIES[city]
    url = (f"{ARCHIVE_URL}?latitude={lat}&longitude={lon}&start_date={start}"
           f"&end_date={end}&daily=temperature_2m_mean,precipitation_sum,"
           f"wind_speed_10m_max&timezone=UTC")

    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = json.load(resp)
            if "daily" not in payload:
                raise ValueError(f"no 'daily' block: {list(payload)}")
            return payload
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_error = e
            if attempt < 3:
                time.sleep(1.5 * (2 ** (attempt - 1)))
    raise RuntimeError(f"{city}: failed after 3 attempts: {last_error}")


def extract(start: str, end: str) -> tuple[list[dict], list[str]]:
    """All cities -> flat rows. Failures are COLLECTED and reported.

    BUG 5 FIX (silent break): `break` on the first error silently
    dropped every city after it — a half-empty result that still
    printed "Done!". Correct behavior: process ALL cities, record
    which failed, and only succeed if none did. A partial pipeline is
    worse than a failed one, because it looks successful.
    """
    rows, failed = [], []
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
        except Exception as e:  # noqa: BLE001 — collect and report
            failed.append(f"{city}: {e}")
    if failed:
        raise RuntimeError("extract failed: " + "; ".join(failed))
    return rows, failed


def save_csv(rows: list[dict], start: str, end: str) -> Path:
    """Rows -> CSV, one file per DATE RANGE.

    BUG 8 FIX (keyed by today): the broken script named files by the
    day the pipeline RAN — backfilling October and November wrote to
    the same file, overwriting each other. Name outputs by the DATA's
    dates; the run date is metadata inside the file, not the filename.
    """
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / f"weather_{start}__{end}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["city", "date", "temp",
                                               "precip", "wind"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def load(rows: list[dict]) -> int:
    """Rows -> SQLite in ONE transaction, with UPSERT dedup.

    BUG 4 FIX (duplicates): plain INSERT with no key means every re-run
    ADDS the same rows again — run it 5 times, 5x the data, and every
    average quietly drifts. A UNIQUE key + INSERT ... ON CONFLICT DO
    UPDATE makes re-runs idempotent: same rows, same table.

    BUG 7 FIX (no transaction): row-by-row commits mean a crash
    mid-load leaves a HALF-loaded table that looks complete. One
    transaction: all rows land, or none do.
    """
    db = DATA / "weather.db"
    con = sqlite3.connect(db)
    # BUG 4 FIX (continued): the broken runs left a `weather` table with
    # NO primary key (created by its CREATE TABLE IF NOT EXISTS). A
    # schema with no key cannot be upserted into — so drop the legacy
    # table and recreate it correctly. This IS the schema-migration
    # problem in miniature: when the contract changes, migrate, don't
    # hope the old table behaves.
    con.execute("DROP TABLE IF EXISTS weather")
    con.execute("""CREATE TABLE weather (
        city TEXT NOT NULL, date TEXT NOT NULL, temp REAL, precip REAL, wind REAL,
        PRIMARY KEY (city, date))""")
    for r in rows:
        con.execute(
            "INSERT INTO weather VALUES (?,?,?,?,?) "
            "ON CONFLICT(city, date) DO UPDATE SET temp=excluded.temp, "
            "precip=excluded.precip, wind=excluded.wind",
            (r["city"], r["date"], r["temp"], r["precip"], r["wind"]),
        )
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM weather").fetchone()[0]
    con.close()
    return total


def main() -> None:
    # BUG 1 FIX (hard-coded dates): the broken script could only ever
    # fetch "yesterday minus 3 days". A pipeline without a date range
    # argument cannot backfill — which means it cannot replay history,
    # recover from outages, or answer "what did October look like".
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    rows, _ = extract(args.start, args.end)
    save_csv(rows, args.start, args.end)
    total = load(rows)

    # BUG 6 FIX (unconditional Done): success is a CHECK, not a print.
    # Verify the result and exit non-zero on failure so schedulers and
    # CI can see it — a "Done!" that always prints is a lie.
    expected = len(rows)
    status = "OK" if total == expected else f"FAIL: db rows {total} != input {expected}"
    print(f"pipeline {status} ({total} rows for {args.start} .. {args.end})")
    if status.startswith("FAIL"):
        sys.exit(1)


if __name__ == "__main__":
    main()