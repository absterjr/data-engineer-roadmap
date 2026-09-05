"""Analytical questions answered with the engine.

Run:  python src/queries.py

Every question is answered using only engine operations
(WHERE, GROUP BY, JOIN, ORDER BY, LIMIT, aggregates, window functions)
— no SQL libraries.

READ ME FIRST: each qN function is ONE business question. They all
follow the same rhythm — chain small engine operations until the table
holds exactly the answer, then `show()` it. The chained calls read
inside-out (like SQL executes): load -> compute -> group -> rank -> filter.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from engine import (
    Table,
    read_csv,
    project,
    where,
    extend,
    join,
    group_by,
    order_by,
    limit,
    count,
    sum_,
    row_number,
    running_sum,
    partition_sum,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "online_retail.csv"
REGIONS = ROOT / "data" / "country_region.csv"


def show(table: Table, title: str, max_rows: int | None = None) -> None:
    """Pretty-print a table as aligned columns in the terminal.

    HOW: for each column, find the WIDEST value it will print (header
    included), then pad every cell to that width. str.ljust() pads with
    spaces on the right; that's all 'alignment' is. max_rows caps long
    tables so the terminal isn't flooded.
    """
    rows = table.rows if max_rows is None else table.rows[:max_rows]
    fmt = lambda v: "" if v is None else str(v)   # NULL prints as blank
    # widest printed value per column drives the column width
    widths = {c: max(len(c), *(len(fmt(r[c])) for r in rows)) for c in table.columns}
    print(f"--- {title}  ({len(table.rows)} rows total, {len(rows)} shown)")
    print("  ".join(c.ljust(widths[c]) for c in table.columns))
    print("  ".join("-" * widths[c] for c in table.columns))
    for r in rows:
        print("  ".join(fmt(r[c]).ljust(widths[c]) for c in table.columns))
    print()


def load_sales() -> Table:
    """Load the dataset and materialize a Revenue column (SELECT expr AS).

    Every question below needs Revenue = Quantity x UnitPrice, so it's
    computed ONCE here instead of in every question. (`or 0` inside the
    lambda means 'if the cell is None/missing, treat it as zero'.)
    """
    sales = read_csv(DATA)
    sales.name = "online_retail"
    return extend(
        sales,
        lambda r: round((r["Quantity"] or 0) * (r["UnitPrice"] or 0), 2),
        "Revenue",
    )


def q1_total_revenue_by_country(sales: Table) -> None:
    """Which countries bring in the most revenue?

    PIPELINE (SQL equivalent in a comment per step):
      group rows by Country            -> GROUP BY Country
      sum Revenue inside each bucket   -> SUM(Revenue)
      sort biggest first               -> ORDER BY Revenue DESC
      keep 10                          -> LIMIT 10
    """
    by_country = group_by(sales, ["Country"], {"Revenue": sum_("Revenue")})
    top = limit(order_by(by_country, "Revenue", desc=True), 10)
    show(top, "Q1. Total revenue by country")


def q2_top_products(sales: Table) -> None:
    """Which products sell the most revenue?

    Same shape as Q1, but grouped by TWO columns (StockCode,
    Description) — the dict of aggregates shows off multiple
    summarizations in one pass: revenue, units sold, and order count.
    """
    by_product = group_by(
        sales,
        ["StockCode", "Description"],
        {"Units": sum_("Quantity"), "Revenue": sum_("Revenue"), "Orders": count},
    )
    top = limit(order_by(by_product, "Revenue", desc=True), 10)
    show(top, "Q2. Top products by revenue")


def q3_monthly_revenue(sales: Table) -> None:
    """How does revenue trend month over month?

    The date arrives as '2010-12-01 08:26:00'; strptime parses it into
    a real datetime, and strftime formats just the 'YYYY-MM' part —
    every row of a month then shares the same bucket key.
    """
    monthly = extend(
        sales,
        lambda r: datetime.strptime(r["InvoiceDate"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m"),
        "Month",
    )
    by_month = group_by(monthly, ["Month"], {"Revenue": sum_("Revenue")})
    show(order_by(by_month, "Month"), "Q3. Monthly revenue")


def q4_revenue_by_region(sales: Table) -> None:
    """JOIN: attach a region to each country, then roll up revenue.

    Two-stage aggregation: first collapse 541k rows to 38 country
    totals, THEN join to the small region table. Joining small-to-small
    is fast; joining the full table to regions would be waste.
    """
    by_country = group_by(sales, ["Country"], {"Revenue": sum_("Revenue")})
    regions = read_csv(REGIONS)
    joined = join(by_country, regions, "Country", "Country")
    by_region = group_by(joined, ["Region"], {"Revenue": sum_("Revenue")})
    show(order_by(by_region, "Revenue", desc=True), "Q4. Revenue by region (JOIN)")


def q5_data_quality(sales: Table) -> None:
    """How messy is the data the engine has to eat?

    'where' is the same operation Q1 used for filtering — data-quality
    checks aren't a different beast, just the same ops applied earlier.
    """
    missing_customer = where(sales, lambda r: r["CustomerID"] is None)
    returns = where(sales, lambda r: (r["Quantity"] or 0) < 0)
    cancelled = where(
        sales,
        lambda r: isinstance(r["InvoiceNo"], str) and r["InvoiceNo"].startswith("C"),
    )
    print("--- Q5. Data quality checks")
    print(f"  total rows                   : {len(sales):,}")
    print(f"  rows without CustomerID      : {len(missing_customer):,}")
    print(f"  rows with negative Quantity  : {len(returns):,}  (returns / refunds)")
    print(f"  rows on cancelled invoices   : {len(cancelled):,}  (InvoiceNo starts with 'C')")
    print()


def q6_top_products_per_country(sales: Table) -> None:
    """ROW_NUMBER: top 3 products by revenue within each country, per month.

    THE classic window-function pattern, in three moves:
      1. collapse line items to product-level revenue per country-month
      2. number the products inside each (Country, Month) partition,
         biggest revenue first  -> ROW_NUMBER() OVER (PARTITION BY ...)
      3. keep rows numbered 1-3, then total them per country
    'Top N per group' is IMPOSSIBLE with GROUP BY alone — grouping can't
    see 'which rank am I inside my bucket'. Windows can.
    """
    monthly = extend(
        sales,
        lambda r: datetime.strptime(r["InvoiceDate"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m"),
        "Month",
    )
    # step 1: one row per (country, month, product) with its revenue
    by_product = group_by(
        monthly,
        ["Country", "Month", "StockCode"],
        {"Revenue": sum_("Revenue")},
    )
    # step 2: rank products inside each country-month window
    ranked = row_number(
        by_product,
        partition_keys=["Country", "Month"],
        order_key="Revenue",
        desc=True,
        name="rn",
    )
    # step 3: keep the podium, then roll up per country
    top3 = where(ranked, lambda r: r["rn"] <= 3)
    top3 = group_by(top3, ["Country"], {"Top3": sum_("Revenue")})
    show(order_by(top3, "Top3", desc=True), "Q6. Top-3 product revenue per country, month (ROW_NUMBER)")


def q7_running_monthly_revenue(sales: Table) -> None:
    """RUNNING SUM: cumulative revenue month over month.

    First group months (13 buckets), then running_sum walks the buckets
    in month order carrying an accumulator — each row gets 'everything
    so far'. That's SUM(...) OVER (ORDER BY month) in SQL.
    """
    monthly = extend(
        sales,
        lambda r: datetime.strptime(r["InvoiceDate"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m"),
        "Month",
    )
    by_month = group_by(monthly, ["Month"], {"Revenue": sum_("Revenue")})
    with_total = running_sum(by_month, "Revenue", order_key="Month", name="RunningTotal")
    show(with_total, "Q7. Cumulative revenue month over month (RUNNING SUM)")


def q8_revenue_share(sales: Table) -> None:
    """PARTITION SUM (no partition = grand total): each country's share.

    partition_sum with an EMPTY key list stamps the GRAND TOTAL onto
    every row — the engine version of SUM(...) OVER (). Share is then a
    simple division per row. Aggregating to countries FIRST keeps this
    at 38 rows instead of 541,909.
    """
    by_country = group_by(sales, ["Country"], {"Revenue": sum_("Revenue")})
    with_total = partition_sum(by_country, "Revenue", name="GrandTotal")
    with_share = extend(
        with_total,
        lambda r: round(100 * r["Revenue"] / r["GrandTotal"], 2) if r["GrandTotal"] else 0,
        "Share%",
    )
    share = project(with_share, ["Country", "Share%"])
    show(order_by(share, "Share%", desc=True), "Q8. Share of total revenue by country (PARTITION SUM)")


if __name__ == "__main__":
    sales = load_sales()
    print(f"Loaded {sales.name}: {len(sales):,} rows x {sales.width} cols\n")

    q1_total_revenue_by_country(sales)
    q2_top_products(sales)
    q3_monthly_revenue(sales)
    q4_revenue_by_region(sales)
    q5_data_quality(sales)
    q6_top_products_per_country(sales)
    q7_running_monthly_revenue(sales)
    q8_revenue_share(sales)