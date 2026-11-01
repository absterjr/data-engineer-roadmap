"""Generate StarMart's data and load it TWO ways: legacy flat + 3NF.

    python scripts/seed.py

The same generated dataset is written into:

  1. `legacy_orders` — one wide table with customer/product data duplicated
     into every line (the anti-pattern; see sql/01_legacy_flat.sql)
  2. the 3NF tables — customers, addresses, address_changes, categories,
     products, orders, order_items, returns (the fix; see sql/02_normalized_3nf.sql)

Everything is deterministic (random.seed), so every run produces the same
numbers — reports stay reproducible.

HOW THE GENERATION WORKS:
  - customers: random names/emails, one default address each (10% get a
    second address). 8% of customers MOVE once during 2024-2025 — the move
    is recorded in address_changes (the CRM's change feed), and their
    default address ends at the final city, so current-state and history
    stay consistent.
  - products: 300 products in 12 categories, price ranges per category
  - orders: 25,000 over 2024-01-01 .. 2025-12-31, with SEASONALITY
    (November/December weighted ~1.6x), WEEKEND SUPPRESSION (35% of the
    normal rate — this is a B2B-leaning store), and a VIP customer subset
    (40% of orders come from 15% of customers, so Pareto analysis has signal)
  - order lines: 1-6 items per order, quantities 1-12, discounts 0-25%
  - returns: 'returned' orders get 1..all lines returned PARTIALLY
    (quantity_returned <= quantity), 3-14 days later, with a refund
    computed from the line's net price. Partial returns are why a status
    flag can't model this.
"""
from __future__ import annotations

import calendar
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "sql"
DB = ROOT / "data" / "starmart.sqlite"

rng = random.Random(42)  # deterministic: same data every run

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

FIRST = ["Aarav", "Mia", "Liam", "Sofia", "Noah", "Emma", "Arjun", "Olivia",
         "Lucas", "Ava", "Ethan", "Isla", "Rohan", "Amelia", "Leo", "Zara",
         "Owen", "Freya", "Kabir", "Chloe", "Mason", "Ella", "Vihaan", "Grace",
         "Hugo", "Layla", "Theo", "Nora", "Reyansh", "Ivy"]
LAST = ["Sharma", "Miller", "Carter", "Patel", "Bennett", "Hughes", "Reddy",
        "Walker", "Turner", "Iyer", "Morgan", "Kaur", "Foster", "Nair",
        "Brooks", "Kapoor", "Hayes", "Mehta", "Price", "Rao", "Cole",
        "Desai", "Fleming", "Bose", "Grant", "Menon", "Reed", "Joshi",
        "Barnes", "Pillai"]
DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "proton.me"]

COUNTRIES = {
    "United Kingdom": (0.55, ["London", "Manchester", "Birmingham", "Edinburgh", "Bristol", "Leeds"]),
    "Germany":        (0.09, ["Berlin", "Munich", "Hamburg", "Cologne"]),
    "France":         (0.08, ["Paris", "Lyon", "Marseille", "Toulouse"]),
    "Netherlands":    (0.05, ["Amsterdam", "Rotterdam", "Utrecht"]),
    "Spain":          (0.05, ["Madrid", "Barcelona", "Valencia"]),
    "USA":            (0.08, ["New York", "Chicago", "Austin", "Seattle"]),
    "Australia":      (0.05, ["Sydney", "Melbourne", "Brisbane"]),
    "India":          (0.05, ["Mumbai", "Bengaluru", "Delhi"]),
}

CATEGORIES = {
    "Home & Living": (4, 60, ["Cushion", "Vase", "Mirror", "Clock", "Frame"]),
    "Kitchen":       (3, 45, ["Mug", "Plate", "Bowl", "Cutlery Set", "Teapot"]),
    "Stationery":    (2, 25, ["Notebook", "Pen Set", "Planner", "Sticky Notes", "Folder"]),
    "Toys":          (5, 50, ["Puzzle", "Building Set", "Plush Bear", "Board Game", "Kite"]),
    "Garden":        (4, 40, ["Planter", "Watering Can", "Bird Feeder", "Trowel Set"]),
    "Lighting":      (6, 80, ["Table Lamp", "Fairy Lights", "Candle Holder", "Pendant"]),
    "Textiles":      (8, 70, ["Throw", "Bedspread", "Table Runner", "Apron", "Towel Set"]),
    "Bath":          (3, 35, ["Soap Dish", "Bath Bomb Set", "Shower Curtain", "Sponge Set"]),
    "Party":         (2, 20, ["Bunting", "Balloon Pack", "Paper Plates", "Party Hat"]),
    "Christmas":     (3, 30, ["Ornament", "Advent Calendar", "Stocking", "Wreath"]),
    "Jewellery":     (8, 120, ["Necklace", "Bracelet", "Earrings", "Ring", "Brooch"]),
    "Bags":          (10, 90, ["Tote Bag", "Backpack", "Pouch", "Lunch Bag"]),
}
ADJECTIVES = ["Rustic", "Modern", "Vintage", "Botanical", "Nordic", "Pastel",
              "Classic", "Handmade", "Minimal", "Floral", "Geometric", "Coastal"]

MONTH_WEIGHT = {1: 0.85, 2: 0.80, 3: 0.90, 4: 0.95, 5: 1.00, 6: 0.95,
                7: 0.95, 8: 1.00, 9: 1.05, 10: 1.15, 11: 1.60, 12: 1.35}
YEAR, MONTHS = 2, range(1, 13)          # 2024 + 2025
STATUS = [("delivered", 0.84), ("shipped", 0.09), ("placed", 0.02),
          ("cancelled", 0.03), ("returned", 0.02)]
PAYMENT = [("card", 0.70), ("paypal", 0.20), ("transfer", 0.10)]
DISCOUNTS = [(0.00, 0.55), (0.05, 0.15), (0.10, 0.12), (0.15, 0.08), (0.20, 0.06), (0.25, 0.04)]
ITEMS_PER_ORDER = [(1, 0.30), (2, 0.25), (3, 0.20), (4, 0.12), (5, 0.08), (6, 0.05)]


def weighted(choices):
    """Pick one (value, weight) pair using a weighted random draw."""
    total = sum(w for _, w in choices)
    x = rng.random() * total
    upto = 0.0
    for value, w in choices:
        upto += w
        if x <= upto:
            return value
    return choices[-1][0]


def pick_country() -> tuple[str, str]:
    """Weighted country + a city from that country's list."""
    pairs = [(c, w) for c, (w, _) in COUNTRIES.items()]
    country = weighted(pairs)
    return country, rng.choice(COUNTRIES[country][1])


# ---------------------------------------------------------------------------
# Generation (in memory first, so both schemas load the SAME data)
# ---------------------------------------------------------------------------


def gen_customers(n: int = 1200) -> tuple[list[dict], list[dict], list[dict]]:
    """Customers + addresses + address CHANGES (8% move once).

    The default address ends at the FINAL city (after any move), so the
    current-state tables and the history always agree. The move itself is
    recorded in the address_changes feed — one row per move.
    """
    customers, addresses, changes = [], [], []
    for cid in range(1, n + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        name = f"{first} {last}"
        email = f"{first}.{last}{cid}@{rng.choice(DOMAINS)}".lower()
        customers.append({
            "id": cid,
            "name": name,
            "email": email,
            "created_at": f"2023-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        })
        country, city = pick_country()
        initial_city, initial_country = city, country

        # 8% of customers move once, somewhere in 2024-2025.
        if rng.random() < 0.08:
            changed_on = f"202{rng.choice([4, 5])}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
            if rng.random() < 0.70:
                # same country, different city (the common case)
                new_city = rng.choice([c for c in COUNTRIES[country][1] if c != city])
                new_country = country
            else:
                # emigrated: everything changes — and must ACTUALLY change
                # (pick_country can roll the same place; retry until not)
                while True:
                    new_country, new_city = pick_country()
                    if (new_country, new_city) != (country, city):
                        break
            changes.append({
                "customer_id": cid,
                "old_city": initial_city,
                "old_country": initial_country,
                "new_city": new_city,
                "new_country": new_country,
                "changed_on": changed_on,
            })
            city, country = new_city, new_country  # current = final

        addresses.append({"customer_id": cid, "city": city, "country": country,
                          "is_default": 1})
        if rng.random() < 0.10:
            country2, city2 = pick_country()
            addresses.append({"customer_id": cid, "city": city2, "country": country2,
                              "is_default": 0})
    return customers, addresses, changes


def gen_products() -> tuple[list[dict], list[dict]]:
    """12 categories, 300 products (25 per category)."""
    categories, products = [], []
    pid = 1
    for cat_id, (cat_name, (lo, hi, nouns)) in enumerate(CATEGORIES.items(), start=1):
        categories.append({"id": cat_id, "name": cat_name})
        for i in range(25):  # 25 products per category = 300 total
            products.append({
                "id": pid,
                "sku": f"SKU-{pid:04d}",
                "name": f"{rng.choice(ADJECTIVES)} {rng.choice(nouns)}",
                "category_id": cat_id,
                "list_price": round(rng.uniform(lo, hi), 2),
            })
            pid += 1
    return categories, products


def gen_orders(customers: list[dict], products: list[dict], n_orders: int = 25000):
    """Orders + lines with seasonality, weekend suppression, VIP skew.

    Returns (orders, items, returns). Returns are generated AFTER the
    lines exist: a 'returned' order returns a RANDOM SUBSET of its lines,
    each partially, 3-14 days later — the reason a single status flag
    cannot model returns.
    """
    vip = set(rng.sample([c["id"] for c in customers],
                         max(1, int(len(customers) * 0.15))))

    orders, items = [], []
    items_by_order: dict[int, list[dict]] = {}
    # weighted (year, month) pairs: November/December carry the holiday peak
    month_choices = [((y, m), MONTH_WEIGHT[m]) for y in range(2024, 2024 + YEAR)
                     for m in MONTHS]

    for oid in range(1, n_orders + 1):
        # --- date: month seasonal, weekday preferred, day uniform ------------
        year, month = weighted(month_choices)
        last_day = calendar.monthrange(year, month)[1]
        while True:
            day = rng.randint(1, last_day)
            weekday = (calendar.weekday(year, month, day) + 1) % 7  # 0=Sunday
            if weekday in (0, 6) and rng.random() > 0.35:
                continue  # weekends happen, but 65% less often
            break
        order_date = f"{year}-{month:02d}-{day:02d}"

        # --- VIP skew: 40% of orders from the 15% VIP subset ----------------
        if rng.random() < 0.40:
            customer = rng.choice(customers)
            while customer["id"] not in vip:
                customer = rng.choice(customers)
        else:
            customer = rng.choice(customers)

        orders.append({
            "id": oid,
            "customer_id": customer["id"],
            "order_date": order_date,
            "status": weighted(STATUS),
            "payment": weighted(PAYMENT),
        })

        # --- 1-6 lines, each a random product -------------------------------
        lines = []
        for line_no in range(1, weighted(ITEMS_PER_ORDER) + 1):
            product = rng.choice(products)
            line = {
                "order_id": oid,
                "line_no": line_no,
                "product_id": product["id"],
                "quantity": rng.randint(1, 12),
                "unit_price": round(product["list_price"] * rng.uniform(0.90, 1.10), 2),
                "discount_pct": weighted(DISCOUNTS),
            }
            items.append(line)
            lines.append(line)
        items_by_order[oid] = lines

    # --- returns: only for 'returned' orders, a subset of their lines -------
    returns = []
    for o in orders:
        if o["status"] != "returned":
            continue
        n_return_lines = rng.randint(1, len(items_by_order[o["id"]]))
        for line in rng.sample(items_by_order[o["id"]], n_return_lines):
            qty = rng.randint(1, line["quantity"])  # PARTIAL return possible
            refund = round(line["unit_price"] * qty * (1 - line["discount_pct"]), 2)
            y, m, d = (int(x) for x in o["order_date"].split("-"))
            rd = date(y, m, d) + timedelta(days=rng.randint(3, 14))
            rd = min(rd, date(2025, 12, 31))  # cap at dataset end
            returns.append({
                "order_id": o["id"],
                "line_no": line["line_no"],
                "return_date": rd.isoformat(),
                "quantity": qty,
                "refund_amount": refund,
            })
    return orders, items, returns


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def build(db_path: Path = DB) -> dict:
    """Create the DB from SQL files, generate data, load BOTH schemas."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    customers, addresses, changes = gen_customers()
    categories, products = gen_products()
    orders, items, returns = gen_orders(customers, products)

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")

    # schemas from the .sql files (executescript runs file contents as-is)
    con.executescript((SQL / "01_legacy_flat.sql").read_text(encoding="utf-8"))
    con.executescript((SQL / "02_normalized_3nf.sql").read_text(encoding="utf-8"))

    # --- 3NF load ---------------------------------------------------------
    con.executemany(
        "INSERT INTO customers (customer_id, full_name, email, created_at) VALUES (?,?,?,?)",
        [(c["id"], c["name"], c["email"], c["created_at"]) for c in customers],
    )
    con.executemany(
        "INSERT INTO addresses (customer_id, city, country, is_default) VALUES (?,?,?,?)",
        [(a["customer_id"], a["city"], a["country"], a["is_default"]) for a in addresses],
    )
    con.executemany(
        "INSERT INTO categories (category_id, name) VALUES (?,?)",
        [(c["id"], c["name"]) for c in categories],
    )
    con.executemany(
        "INSERT INTO products (product_id, sku, name, category_id, list_price) VALUES (?,?,?,?,?)",
        [(p["id"], p["sku"], p["name"], p["category_id"], p["list_price"]) for p in products],
    )
    con.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, payment_method) VALUES (?,?,?,?,?)",
        [(o["id"], o["customer_id"], o["order_date"], o["status"], o["payment"]) for o in orders],
    )
    con.executemany(
        "INSERT INTO order_items (order_id, line_no, product_id, quantity, unit_price, discount_pct) "
        "VALUES (?,?,?,?,?,?)",
        [(i["order_id"], i["line_no"], i["product_id"], i["quantity"],
          i["unit_price"], i["discount_pct"]) for i in items],
    )
    con.executemany(
        "INSERT INTO address_changes (customer_id, old_city, old_country, new_city, new_country, changed_on) "
        "VALUES (?,?,?,?,?,?)",
        [(c["customer_id"], c["old_city"], c["old_country"], c["new_city"],
          c["new_country"], c["changed_on"]) for c in changes],
    )
    con.executemany(
        "INSERT INTO returns (order_id, line_no, return_date, quantity, refund_amount) "
        "VALUES (?,?,?,?,?)",
        [(r["order_id"], r["line_no"], r["return_date"], r["quantity"],
          r["refund_amount"]) for r in returns],
    )

    # --- legacy load: the SAME facts, duplicated into one wide table -------
    # This is the anti-pattern in action: look up the customer and product
    # details per line and copy them in. One row per line, ~15 columns,
    # most of them repeated.
    by_id = {c["id"]: c for c in customers}
    city_by_customer = {a["customer_id"]: (a["city"], a["country"])
                        for a in addresses if a["is_default"] == 1}
    prod_by_id = {p["id"]: p for p in products}
    cat_name = {c["id"]: c["name"] for c in categories}
    order_by_id = {o["id"]: o for o in orders}

    legacy_rows = []
    for it in items:
        o = order_by_id[it["order_id"]]
        c = by_id[o["customer_id"]]
        p = prod_by_id[it["product_id"]]
        city, country = city_by_customer[o["customer_id"]]
        legacy_rows.append((
            f"ORD-{o['order_date'][:4]}-{o['id']:06d}",
            o["order_date"],
            c["name"], c["email"], city, country,
            p["sku"], p["name"], cat_name[p["category_id"]],
            it["unit_price"], it["quantity"], it["discount_pct"], o["payment"],
        ))
    con.executemany(
        "INSERT INTO legacy_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", legacy_rows
    )

    con.commit()

    counts = {
        "customers": con.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "addresses": con.execute("SELECT COUNT(*) FROM addresses").fetchone()[0],
        "moves": con.execute("SELECT COUNT(*) FROM address_changes").fetchone()[0],
        "products": con.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders": con.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "order_items": con.execute("SELECT COUNT(*) FROM order_items").fetchone()[0],
        "returns": con.execute("SELECT COUNT(*) FROM returns").fetchone()[0],
        "legacy_rows": con.execute("SELECT COUNT(*) FROM legacy_orders").fetchone()[0],
    }
    con.close()
    return counts


def main() -> None:
    counts = build()
    print(f"Built {DB}\n")
    for k, v in counts.items():
        print(f"  {k:<14} {v:>8,}")
    print("\nnext: python scripts/build_warehouse.py")


if __name__ == "__main__":
    main()