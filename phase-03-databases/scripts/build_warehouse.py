"""Build the StarMart warehouse: star DDL -> ETL -> indexes -> checks.

    python scripts/build_warehouse.py

Pipeline:
  1. run sql/03_star_schema.sql   (drop + create the star tables)
  2. run sql/04_etl_3nf_to_star.sql (dimensions, then the fact)
  3. create indexes on the fact table's foreign keys
  4. reconcile: the star's revenue must equal the 3NF source's revenue
     (computed independently) — if these disagree, the ETL has a bug
  5. ANALYZE so SQLite's planner has up-to-date statistics
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "sql"
DB = ROOT / "data" / "starmart.sqlite"

# Foreign-key indexes: every analytical query joins the fact table to its
# dimensions through these columns. Without them SQLite scans the fact
# table per join; with them it can seek. (Same lesson as Phase 1's
# InvoiceDate index, applied at warehouse scale.)
FACT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_fact_date     ON fact_sales(date_key)",
    "CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales(customer_key)",
    "CREATE INDEX IF NOT EXISTS idx_fact_product  ON fact_sales(product_key)",
]


def main() -> None:
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")

    # --- 1 + 2: DDL then ETL ----------------------------------------------
    print("Creating star schema ...")
    con.executescript((SQL / "03_star_schema.sql").read_text(encoding="utf-8"))

    print("Running ETL (3NF -> star) ...")
    con.executescript((SQL / "04_etl_3nf_to_star.sql").read_text(encoding="utf-8"))

    # --- 3: indexes --------------------------------------------------------
    print("Creating fact indexes ...")
    for stmt in FACT_INDEXES:
        con.execute(stmt)
    con.commit()

    # --- 4: reconciliation -------------------------------------------------
    # The SAME revenue number computed two independent ways:
    #   a) from the star: SUM of the pre-computed net_revenue measure
    #   b) from the 3NF source: recompute quantity * unit_price * (1-discount)
    # If they differ, the ETL dropped or duplicated rows.
    #
    # NOTE the ROUND() placement: the star rounds money per LINE (correct
    # for a warehouse — a line's revenue must be exact to the cent), so the
    # source side must round per line too before summing. Rounding each
    # line and then summing is NOT the same as summing and rounding once:
    # that mismatch is worth £0.50 here, and it's the classic reason two
    # dashboards show two totals. Compare like with like.
    star_rev = con.execute(
        "SELECT ROUND(SUM(net_revenue), 2) FROM fact_sales "
        "WHERE order_status NOT IN ('cancelled', 'returned')"
    ).fetchone()[0]
    source_rev = con.execute(
        "SELECT ROUND(SUM(ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct), 2)), 2) "
        "FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
        "WHERE o.status NOT IN ('cancelled', 'returned')"
    ).fetchone()[0]

    # --- 5: planner statistics --------------------------------------------
    con.execute("ANALYZE")
    con.commit()

    counts = {
        "dim_date": con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0],
        "dim_customer": con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0],
        "dim_product": con.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0],
        "fact_sales": con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0],
    }

    print("\nwarehouse contents")
    for k, v in counts.items():
        print(f"  {k:<14} {v:>8,}")
    print(f"\nreconciliation")
    print(f"  star net revenue   : {star_rev:,.2f}")
    print(f"  3NF source revenue : {source_rev:,.2f}")
    print(f"  match              : {'YES' if star_rev == source_rev else 'NO  <-- ETL BUG'}")

    con.close()


if __name__ == "__main__":
    main()