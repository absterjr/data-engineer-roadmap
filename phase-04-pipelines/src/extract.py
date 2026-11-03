"""extract — the bronze layer: API responses landed raw and immutable.

WHY RAW FILES: the response from the source is the ONLY artifact that can
be replayed. Every later layer is derived; bronze is the original. Rules:
  1. one file per (city, date), written once, never transformed
  2. fetch failures RETRY with backoff — the API is a network, and
     networks fail at random, not at convenient times
  3. be polite: a small pause between requests, because free tiers die
     under bursts
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# StarMart's top cities, with real coordinates (from Phase 3's data).
CITIES = {
    "London":     ("United Kingdom", 51.51, -0.13),
    "Manchester": ("United Kingdom", 53.48, -2.24),
    "Edinburgh":  ("United Kingdom", 55.95, -3.19),
    "Paris":      ("France",         48.85, 2.35),
    "Berlin":     ("Germany",        52.52, 13.40),
    "Amsterdam":  ("Netherlands",    52.37, 4.90),
    "Madrid":     ("Spain",          40.42, -3.70),
}

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
VARS = ["temperature_2m_mean", "precipitation_sum", "wind_speed_10m_max"]


def fetch_city(city: str, start: str, end: str, bronze_dir: Path,
               retries: int = 3, backoff: float = 1.0) -> Path:
    """Fetch one city's daily weather for [start, end] into a bronze file.

    The file name is <city>__<start>__<end>.json — the key that makes
    re-runs idempotent: the same request always lands in the same file,
    and an existing file means "this range was already fetched".

    Retry/backoff: on any network error or HTTP failure, sleep backoff
    seconds (doubling each try) and try again. A transient failure is
    not a pipeline failure; a persistent one is.
    """
    country, lat, lon = CITIES[city]
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(VARS),
        "timezone": "UTC",
    })
    url = f"{ARCHIVE_URL}?{params}"

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = json.load(resp)
            if "daily" not in payload:
                raise ValueError(f"no 'daily' block in response: {list(payload)}")
            break  # success: leave the retry loop
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            if attempt == retries:
                raise
            wait = backoff * (2 ** (attempt - 1))
            print(f"      {city}: attempt {attempt} failed ({e}); "
                  f"retrying in {wait:.1f}s")
            time.sleep(wait)

    bronze_dir.mkdir(parents=True, exist_ok=True)
    out = bronze_dir / f"{city}__{start}__{end}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def extract_all(ctx: dict) -> dict:
    """Bronze every city for the run's date range. Returns a summary."""
    cities = ctx["cities"]
    start, end = ctx["start"], ctx["end"]
    bronze = Path(ctx["bronze_dir"])

    written, skipped, failed = [], [], []
    for i, city in enumerate(cities):
        out = bronze / f"{city}__{start}__{end}.json"
        if out.exists():
            skipped.append(city)          # idempotent: don't re-fetch
            continue
        try:
            fetch_city(city, start, end, bronze)
            written.append(city)
        except Exception as e:  # noqa: BLE001 — orchestrator records the failure
            failed.append((city, str(e)))
        if i < len(cities) - 1:
            time.sleep(0.3)               # politeness for the free tier

    ctx["extract"] = {
        "written": written, "skipped": skipped, "failed": failed,
        "files": len(written) + len(skipped),
    }
    if failed:
        raise RuntimeError(f"extract failed for: {failed}")
    return ctx["extract"]