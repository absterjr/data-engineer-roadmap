"""Watch the legacy schema rot — the three anomalies, live.

    python scripts/anomalies.py

Each demo runs inside a TRANSACTION that is ROLLED BACK at the end, so the
database is left exactly as it was found. You get to see the damage
without keeping it — and you learn what ROLLBACK is for.

The three classic anomalies (all caused by storing one fact in many rows):

  1. UPDATE anomaly  — change a customer's city in *some* of their rows and
                       the same customer now lives in two places.
  2. INSERT anomaly  — the flat table cannot hold a product that has not
                       been ordered yet (there is no row to put it in).
  3. DELETE anomaly  — deleting a customer's last order deletes the
                       customer: their contact record was only a row in
                       someone else's order.

Each demo then runs the 3NF equivalent, where the anomaly is impossible
by construction.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # em dashes on Windows

DB = Path(__file__).resolve().parent.parent / "data" / "starmart.sqlite"


def update_anomaly(con: sqlite3.Connection) -> None:
    """UPDATE anomaly: the same customer ends up in two cities."""
    print("=" * 70)
    print("1. UPDATE ANOMALY — one customer, two cities")
    print("=" * 70)

    # find a customer with at least 6 rows in the legacy table
    email = con.execute(
        "SELECT customer_email FROM legacy_orders "
        "GROUP BY customer_email HAVING COUNT(*) >= 6 LIMIT 1"
    ).fetchone()[0]

    before = con.execute(
        "SELECT DISTINCT customer_city FROM legacy_orders WHERE customer_email = ?",
        (email,),
    ).fetchall()
    print(f"  customer            : {email}")
    print(f"  cities before       : {[c[0] for c in before]}")

    # "Update the customer's city" — but the update only touches HALF the
    # rows, exactly what happens when one report/job misses the others.
    con.execute(
        "UPDATE legacy_orders SET customer_city = 'Newtown' "
        "WHERE customer_email = ? AND rowid % 2 = 0",
        (email,),
    )
    after = con.execute(
        "SELECT DISTINCT customer_city FROM legacy_orders WHERE customer_email = ?",
        (email,),
    ).fetchall()
    print(f"  cities after        : {[c[0] for c in after]}   <-- the anomaly")

    # 3NF: the city lives in ONE row (addresses), so the update is atomic.
    customer_id = con.execute(
        "SELECT customer_id FROM customers WHERE email = ?", (email,)
    ).fetchone()
    if customer_id:
        updated = con.execute(
            "UPDATE addresses SET city = 'Newtown' "
            "WHERE customer_id = ? AND is_default = 1",
            (customer_id[0],),
        ).rowcount
        print(f"  3NF equivalent      : {updated} row updated — consistent by design")
    print("  (all changes rolled back at the end of this script)\n")


def insert_anomaly(con: sqlite3.Connection) -> None:
    """INSERT anomaly: a product cannot exist without an order."""
    print("=" * 70)
    print("2. INSERT ANOMALY — the catalog cannot grow without a sale")
    print("=" * 70)

    # A new product arrives in the catalog. Legacy has nowhere to put it
    # except a fake order row — every column about the order (order_id,
    # date, customer) has to be NULL or invented.
    con.execute(
        "INSERT INTO legacy_orders (product_sku, product_name, category, unit_price) "
        "VALUES ('SKU-NEW-001', 'Brand New Lamp', 'Lighting', 24.99)"
    )
    row = con.execute(
        "SELECT order_id, customer_email, product_sku FROM legacy_orders "
        "WHERE product_sku = 'SKU-NEW-001'"
    ).fetchone()
    print(f"  inserted with order_id={row[0]!r}, customer={row[1]!r}")
    print("  -> a catalog entry pretending to be an order line\n")

    # 3NF: products is its own table; adding one is a normal INSERT.
    con.execute(
        "INSERT INTO products (product_id, sku, name, category_id, list_price) "
        "VALUES (9999, 'SKU-NEW-001', 'Brand New Lamp', 6, 24.99)"
    )
    print("  3NF equivalent      : INSERT INTO products — works standalone")
    print("  (rolled back)\n")


def delete_anomaly(con: sqlite3.Connection) -> None:
    """DELETE anomaly: delete the order, lose the customer."""
    print("=" * 70)
    print("3. DELETE ANOMALY — the customer exists only inside their order")
    print("=" * 70)

    # Pick the customer with the FEWEST legacy rows and delete all of them:
    # once every order line is gone, the customer has no record left
    # anywhere — their contact details only ever lived inside those rows.
    # (customer_email IS NOT NULL matters: the insert demo above just left
    # a row with a NULL email, and in SQL, NULL never equals NULL — a
    # "WHERE email = NULL" would match nothing and quietly "work".)
    email, n_rows = con.execute(
        "SELECT customer_email, COUNT(*) AS n FROM legacy_orders "
        "WHERE customer_email IS NOT NULL "
        "GROUP BY customer_email ORDER BY n ASC, customer_email LIMIT 1"
    ).fetchone()

    con.execute("DELETE FROM legacy_orders WHERE customer_email = ?", (email,))
    left = con.execute(
        "SELECT COUNT(*) FROM legacy_orders WHERE customer_email = ?", (email,)
    ).fetchone()[0]
    print(f"  deleted all {n_rows} line(s) for {email}")
    print(f"  legacy rows left    : {left}   <-- the customer is gone")

    # 3NF: customers is an independent table. Deleting orders doesn't
    # delete the customer (that would require an explicit DELETE).
    customer_id = con.execute(
        "SELECT customer_id FROM customers WHERE email = ?", (email,)
    ).fetchone()
    if customer_id:
        print(f"  3NF equivalent      : customer_id {customer_id[0]} still exists in customers")
    print("  (rolled back)\n")


def transaction_demo(con: sqlite3.Connection) -> None:
    """Transactions: all-or-nothing, and why that matters."""
    print("=" * 70)
    print("4. TRANSACTIONS — atomicity in 6 lines")
    print("=" * 70)

    before = con.execute("SELECT SUM(discount_pct) FROM order_items").fetchone()[0]

    try:
        con.execute("BEGIN")
        con.execute("UPDATE order_items SET discount_pct = 0.50 WHERE rowid % 2 = 0")
        # ... imagine the next step fails (validation error, crash, network)
        raise RuntimeError("step 2 of 2 failed")
        con.execute("COMMIT")  # never reached
    except RuntimeError:
        con.rollback()         # undo EVERYTHING from BEGIN
        print("  a two-step update failed mid-way -> rolled back")

    after = con.execute("SELECT SUM(discount_pct) FROM order_items").fetchone()[0]
    print(f"  discount total before: {before:.2f}")
    print(f"  discount total after : {after:.2f}")
    print(f"  unchanged            : {'YES' if before == after else 'NO'}\n")


def main() -> None:
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")

    # One transaction around all demos: ROLLBACK at the end returns the
    # database to its pre-demo state.
    con.execute("BEGIN")
    try:
        update_anomaly(con)
        insert_anomaly(con)
        delete_anomaly(con)
    finally:
        con.rollback()
        print("all demo changes rolled back — the database is untouched\n")

    # The transaction demo manages its own BEGIN/ROLLBACK.
    transaction_demo(con)

    # verify the rollback actually left everything as it was
    n_legacy = con.execute("SELECT COUNT(*) FROM legacy_orders").fetchone()[0]
    n_cities = con.execute(
        "SELECT COUNT(DISTINCT customer_city) FROM legacy_orders WHERE customer_email = "
        "(SELECT customer_email FROM legacy_orders LIMIT 1)"
    ).fetchone()[0]
    print(f"sanity: legacy rows still {n_legacy:,}; sample customer has {n_cities} city")
    con.close()


if __name__ == "__main__":
    main()