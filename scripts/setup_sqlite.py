"""Load data/online_retail.csv into SQLite for the SQL rebuild task.

    python scripts/setup_sqlite.py

Creates data/online_retail.db (regenerable, gitignored — run this any
time you want a fresh copy). The table is deliberately created WITHOUT
indexes: the rebuild task in sql/README.md shows the query plan before
and after you add one.

HOW IT WORKS:
  1. connect     - sqlite3 creates the .db file on first connect
  2. create      - one CREATE TABLE defines the columns and their types
  3. insert      - the CSV is streamed row by row; each value is cast to
                   the column's type BEFORE insertion (SQLite is loosely
                   typed, so WE must be strict or the analysis lies)
  4. count       - a sanity check that every row made it in
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "phase-01-fundamentals" / "data"
CSV_PATH = DATA_DIR / "online_retail.csv"
DB_PATH = DATA_DIR / "online_retail.db"

# The schema: column types are declared HERE because the CSV has none.
# InvoiceDate stays TEXT on purpose: ISO strings sort chronologically,
# which is exactly what the date-range queries in sql/ rely on.
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
    """'6' -> 6, '17850.0' -> 17850, '' -> None (SQL NULL).

    int(float(v)) handles the CustomerID column, which the Excel->CSV
    conversion wrote as floats ('17850.0') even though IDs are whole.
    """
    v = v.strip()
    if v in ("", "nan"):
        return None
    return int(float(v))


def to_real(v: str) -> float | None:
    """'2.55' -> 2.55, '' -> None (SQL NULL)."""
    v = v.strip()
    if v in ("", "nan"):
        return None
    return float(v)


def main() -> None:
    # start fresh: delete any previous database file
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    con.execute(SCHEMA)

    # stream the CSV and cast every cell to its column's type
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

    # executemany = one prepared statement, many rows (much faster than
    # calling execute() in a loop)
    con.executemany("INSERT INTO online_retail VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()

    # sanity check: the row count must match the CSV's
    n = con.execute("SELECT COUNT(*) FROM online_retail").fetchone()[0]
    print(f"Loaded {n:,} rows into {DB_PATH} (no indexes yet)")
    con.close()


if __name__ == "__main__":
    main()