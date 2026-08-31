"""Analytical questions answered with the engine.

Run:  python src/queries.py

Every question is answered using only engine operations
(WHERE, GROUP BY, JOIN, ORDER BY, LIMIT, aggregates, window functions)
— no SQL libraries.
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
    """Pretty-print a table as aligned columns."""
    rows = table.rows if max_rows is None else table.rows[:max_rows]
    fmt = lambda v: "" if v is None else str(v)
    widths = {c: max(len(c), *(len(fmt(r[c])) for r in rows)) for c in table.columns}
    print(f"--- {title}  ({len(table.rows)} rows total, {len(rows)} shown)")
    print("  ".join(c.ljust(widths[c]) for c in table.columns))
    print("  ".join("-" * widths[c] for c in table.columns))
    for r in rows:
        print("  ".join(fmt(r[c]).ljust(widths[c]) for c in table.columns))
    print()


def load_sales() -> Table:
    """Load the dataset and materialize a Revenue column (SELECT expr AS)."""
    sales = read_csv(DATA)
    sales.name = "online_retail"
    return extend(
        sales,
        lambda r: round((r["Quantity"] or 0) * (r["UnitPrice"] or 0), 2),
        "Revenue",
    )


def q1_total_revenue_by_country(sales: Table) -> None:
    """Which countries bring in the most revenue?"""
    by_country = group_by(sales, ["Country"], {"Revenue": sum_("Revenue")})
    top = limit(order_by(by_country, "Revenue", desc=True), 10)
    show(top, "Q1. Total revenue by country")


def q2_top_products(sales: Table) -> None:
    """Which products sell the most revenue?"""
    by_product = group_by(
        sales,
        ["StockCode", "Description"],
        {"Units": sum_("Quantity"), "Revenue": sum_("Revenue"), "Orders": count},
    )
    top = limit(order_by(by_product, "Revenue", desc=True), 10)
    show(top, "Q2. Top products by revenue")


def q3_monthly_revenue(sales: Table) -> None:
    """How does revenue trend month over month?"""
    monthly = extend(
        sales,
        lambda r: datetime.strptime(r["InvoiceDate"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m"),
        "Month",
    )
    by_month = group_by(monthly, ["Month"], {"Revenue": sum_("Revenue")})
    show(order_by(by_month, "Month"), "Q3. Monthly revenue")


def q4_revenue_by_region(sales: Table) -> None:
    """JOIN: attach a region to each country, then roll up revenue."""
    by_country = group_by(sales, ["Country"], {"Revenue": sum_("Revenue")})
    regions = read_csv(REGIONS)
    joined = join(by_country, regions, "Country", "Country")
    by_region = group_by(joined, ["Region"], {"Revenue": sum_("Revenue")})
    show(order_by(by_region, "Revenue", desc=True), "Q4. Revenue by region (JOIN)")


def q5_data_quality(sales: Table) -> None:
    """How messy is the data the engine has to eat?"""
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
    """ROW_NUMBER: top 3 products by revenue within each country, per month."""
    monthly = extend(
        sales,
        lambda r: datetime.strptime(r["InvoiceDate"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m"),
        "Month",
    )
    by_product = group_by(
        monthly,
        ["Country", "Month", "StockCode"],
        {"Revenue": sum_("Revenue")},
    )
    ranked = row_number(
        by_product,
        partition_keys=["Country", "Month"],
        order_key="Revenue",
        desc=True,
        name="rn",
    )
    top3 = where(ranked, lambda r: r["rn"] <= 3)
    top3 = group_by(top3, ["Country"], {"Top3": sum_("Revenue")})
    show(order_by(top3, "Top3", desc=True), "Q6. Top-3 product revenue per country, month (ROW_NUMBER)")


def q7_running_monthly_revenue(sales: Table) -> None:
    """RUNNING SUM: cumulative revenue month over month."""
    monthly = extend(
        sales,
        lambda r: datetime.strptime(r["InvoiceDate"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m"),
        "Month",
    )
    by_month = group_by(monthly, ["Month"], {"Revenue": sum_("Revenue")})
    with_total = running_sum(by_month, "Revenue", order_key="Month", name="RunningTotal")
    show(with_total, "Q7. Cumulative revenue month over month (RUNNING SUM)")


def q8_revenue_share(sales: Table) -> None:
    """PARTITION SUM (no partition = grand total): each country's share."""
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