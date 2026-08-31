"""Run a .sql file against data/online_retail.db and print the results.

    python scripts/run_sql.py sql/bad_queries.sql
    python scripts/run_sql.py sql/good_queries.sql

A tiny stand-in for the sqlite3 CLI, so the rebuild task works on any
machine with Python (no installs needed).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "phase-01-fundamentals" / "data" / "online_retail.db"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/run_sql.py path/to/queries.sql")
        return

    sql_path = Path(sys.argv[1])
    if not sql_path.exists():  # allow running from anywhere: fall back to phase dir
        fallback = ROOT / "phase-01-fundamentals" / sql_path
        if fallback.exists():
            sql_path = fallback
    script = "\n".join(
        line for line in sql_path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("--")
    )

    con = sqlite3.connect(DB)
    for stmt in script.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            cur = con.execute(stmt)
        except sqlite3.Error as e:
            print(f"[ERROR] {e}")
            print()
            continue

        rows = cur.fetchall()
        if cur.description is None:
            print("--- OK (statement executed)")
        elif not rows:
            print("--- 0 rows")
        else:
            cols = [d[0] for d in cur.description]
            print(f"--- {len(rows)} rows: {', '.join(cols)}")
            for r in rows[:25]:
                print("  " + " | ".join(str(x) for x in r))
        print()

    con.close()


if __name__ == "__main__":
    main()