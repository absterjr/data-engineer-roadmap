"""Load data/online_retail.csv into SQLite for the SQL rebuild task.

    python scripts/setup_sqlite.py

Creates data/online_retail.db (regenerable, gitignored — run this any
time you want a fresh copy). The table is deliberately created WITHOUT
indexes: the rebuild task in sql/README.md shows the query plan before
and after you add one.
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "phase-01-fundamentals" / "data"
CSV_PATH = DATA_DIR / "online_retail.csv"
DB_PATH = DATA_DIR / "online_retail.db"

SCHEMA = """
CREATE TABLE online_retail (
    InvoiceNo   TEXT,
    StockCode   TEXT,
    Description TEXT,
    Quantity    INTEGER,
    InvoiceDate TEXT,   -- stored as ISO text: lexicographic = chronological
    UnitPrice   REAL,
    CustomerID  INTEGER,
    Country     TEXT
);
"""


def to_int(v: str) -> int | None:
    v = v.strip()
    if v in ("", "nan"):
        return None
    return int(float(v))  # CSV holds CustomerID as e.g. '17850.0'


def to_real(v: str) -> float | None:
    v = v.strip()
    if v in ("", "nan"):
        return None
    return float(v)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    con.execute(SCHEMA)

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [
            (
                r["InvoiceNo"],
                r["StockCode"],
                r["Description"],
                to_int(r["Quantity"]),
                r["InvoiceDate"],
                to_real(r["UnitPrice"]),
                to_int(r["CustomerID"]),
                r["Country"],
            )
            for r in reader
        ]

    con.executemany("INSERT INTO online_retail VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()

    n = con.execute("SELECT COUNT(*) FROM online_retail").fetchone()[0]
    print(f"Loaded {n:,} rows into {DB_PATH} (no indexes yet)")
    con.close()


if __name__ == "__main__":
    main()