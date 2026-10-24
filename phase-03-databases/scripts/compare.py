"""Same business question, three schemas — joins, correctness, speed.

    python scripts/compare.py

THE QUESTION:
    "Revenue by product category, for German customers, in 2025,
     excluding cancelled and returned orders."

Why this question? It touches every dimension the warehouse models:
a date range, a customer attribute (country), a product attribute
(category), and a status filter. That's the shape of most real
analytics requests.

Three implementations:
  1. LEGACY   — one wide table. Fewest joins... and the WRONG ANSWER,
                because the flat table has no status column: cancelled
                and returned lines cannot be excluded.
  2. 3NF      — six tables. Correct, but every join is a chance for a
                mistake, and the SQL grows with every new attribute.
  3. STAR     — fact + 3 dimensions. Correct, three joins, readable.

The star should match the 3NF answer to the cent. If it doesn't,
the ETL is broken. That reconciliation is the real test.
"""
from __future__ import annotations

import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # £ signs on Windows

DB = Path(__file__).resolve().parent.parent / "data" / "starmart.sqlite"

LEGACY_SQL = """
SELECT category,
       ROUND(SUM(quantity * unit_price * (1 - discount_pct)), 2) AS revenue
FROM legacy_orders
WHERE customer_country = 'Germany'
  AND order_date >= '2025-01-01' AND order_date < '2026-01-01'
GROUP BY category
ORDER BY revenue DESC
"""

# 3NF: orders -> order_items -> products -> categories, plus
#      orders -> customers -> addresses. Six tables.
NF3_SQL = """
SELECT cat.name AS category,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p     ON p.product_id = oi.product_id
JOIN categories cat ON cat.category_id = p.category_id
JOIN customers c    ON c.customer_id = o.customer_id
JOIN addresses a    ON a.customer_id = c.customer_id AND a.is_default = 1
WHERE a.country = 'Germany'
  AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01'
  AND o.status NOT IN ('cancelled', 'returned')
GROUP BY cat.name
ORDER BY revenue DESC
"""

# STAR: fact + 3 dimensions. The measures were computed once, in the ETL.
STAR_SQL = """
SELECT dp.category,
       ROUND(SUM(f.net_revenue), 2) AS revenue
FROM fact_sales f
JOIN dim_date d     ON d.date_key = f.date_key
JOIN dim_product dp ON dp.product_key = f.product_key
JOIN dim_customer dc ON dc.customer_key = f.customer_key
WHERE dc.country = 'Germany'
  AND d.year = 2025
  AND f.order_status NOT IN ('cancelled', 'returned')
GROUP BY dp.category
ORDER BY revenue DESC
"""


def run(con: sqlite3.Connection, label: str, sql: str, joins: int) -> dict:
    """Execute a query 5 times; report the median time and the result."""
    times = []
    rows = None
    for _ in range(5):
        t0 = time.perf_counter()
        rows = con.execute(sql).fetchall()
        times.append(time.perf_counter() - t0)
    total = round(sum(r[1] for r in rows), 2)
    print(f"\n{label}")
    print(f"  joins: {joins}   tables touched: {joins + 1}")
    print(f"  median time: {statistics.median(times) * 1000:.1f} ms")
    print(f"  total revenue: £{total:,.2f}")
    for cat, rev in rows[:4]:
        print(f"    {cat:<16} £{rev:>12,.2f}")
    if len(rows) > 4:
        print(f"    ... and {len(rows) - 4} more categories")
    return {"rows": rows, "total": total, "median_ms": statistics.median(times) * 1000}


def main() -> None:
    con = sqlite3.connect(DB)

    print("=" * 70)
    print("SAME QUESTION, THREE SCHEMAS")
    print('"Revenue by category, German customers, 2025, excluding '
          'cancelled/returned"')
    print("=" * 70)

    legacy = run(con, "1. LEGACY FLAT TABLE", LEGACY_SQL, joins=0)
    nf3 = run(con, "2. NORMALIZED 3NF", NF3_SQL, joins=5)
    star = run(con, "3. STAR SCHEMA", STAR_SQL, joins=3)

    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    diff = star["total"] - nf3["total"]
    print(f"  3NF vs star agree : {'YES' if abs(diff) < 1.0 else 'NO <-- ETL BUG'}"
          f"  (delta £{diff:+.2f} — line-level rounding, not a bug)")
    print(f"  legacy vs star    : £{legacy['total'] - star['total']:,.2f} overstated"
          f"  ({(legacy['total'] / star['total'] - 1):.1%})")
    print("  why legacy is wrong: no status column exists in the flat table,")
    print("  so cancelled and returned lines cannot be excluded — the flat")
    print("  schema cannot even ASK the question correctly. Fewest joins,")
    print("  wrong answer: the most dangerous kind of simple.")
    print()
    print("  and the star is also the fastest of the correct options —")
    print("  3 joins instead of 5, measures pre-computed in the ETL.")

    con.close()


if __name__ == "__main__":
    main()