"""Run a .sql file against the StarMart database and print results.

    python scripts/run_sql.py sql/05_analytical_queries.sql

Same idea as Phase 1's runner: read the file, strip comment lines, split
on ';', execute each statement, print rows. Errors are printed inline so
one failing statement doesn't stop the rest.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "starmart.sqlite"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/run_sql.py path/to/queries.sql")
        return

    # resolve the .sql path: current directory first, then the phase folder
    sql_path = Path(sys.argv[1])
    if not sql_path.exists():
        fallback = ROOT / sql_path
        if fallback.exists():
            sql_path = fallback

    # drop comment lines so the ';' split below sees only SQL statements
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
            print(f"[ERROR] {e}\n")
            continue

        rows = cur.fetchall()
        if cur.description is None:
            print("--- OK (statement executed)")
        elif not rows:
            print("--- 0 rows")
        else:
            cols = [d[0] for d in cur.description]
            print(f"--- {len(rows)} rows: {', '.join(cols)}")
            for r in rows[:20]:
                print("  " + " | ".join(str(x) for x in r))
            if len(rows) > 20:
                print(f"  ... ({len(rows) - 20} more rows)")
        print()

    con.close()


if __name__ == "__main__":
    main()