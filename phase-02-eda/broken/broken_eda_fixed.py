"""FIXED EDA — the corrected twin of broken_eda.py.

    python broken/broken_eda_fixed.py

This file has the SAME functions, SAME signatures and SAME report as
broken_eda.py — only the bugs are fixed. Open the two files side by side
(VS Code: select both files, right-click -> 'Compare Selected') and read
them function by function: every fix carries a `BUG n FIX` comment
explaining what was wrong, why it was silent (or loud), and what the
correct thinking is.

The corrected numbers (verified against Phase 1's cross-checked SQL):
    revenue   ~ £10.7M     UK share ~ 84.6%
    month 11 (Nov 2011)    customers ~ 4,372
    returned line items    1,336 (write-offs) + 9,288 (cancellations)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent.parent / "phase-01-fundamentals" / "data" / "online_retail.csv"


def load(path: Path = DATA) -> pd.DataFrame:
    """Load the raw transaction table from the CSV.

    (Unchanged — loading was never the problem. The bugs all live in
    what we do AFTER loading.)
    """
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the data honest: fix types, compute Revenue, FLAG problems
    instead of deleting rows.

    BUG 1 FIX (dropna): df.dropna() dropped any row with ANY missing
    value — 143,985 rows (26.6%!) vanished, most for a missing
    CustomerID. Deleting a quarter of the store's history to dodge a
    null is not cleaning, it's censorship. The fix: never blanket-drop.
    Rows without a customer are still useful (product/time analysis) —
    so we FLAG them with a boolean column and let each question decide.

    BUG 2 FIX (Quantity > 0): filtering out non-positive quantities
    inside `clean` deleted every return BEFORE the returns analysis ran
    — which is why the broken version printed "returned line items: 0".
    The fix: keep returns in the frame; exclude them only where revenue
    is being totaled (see revenue_rows below).

    Also note df.copy(): working on a copy stops pandas'
    SettingWithCopyWarning surprises later (bug 5's root cause).
    """
    df = df.copy()

    # BUG 1 FIX: flag, don't delete. Missing CustomerID is information,
    # not garbage. Notice what 'cleaning' became: NO rows are deleted at
    # all — the function only adds explicit flags, and each question
    # decides which rows it needs. Deletion was never the cleaning.
    df["HasCustomer"] = df["CustomerID"].notna()

    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]

    # BUG 2 FIX: keep returns in the frame; separate the two kinds.
    # 'C'-prefixed invoices are cancellations (credit notes = refunds).
    # Negative quantities on NORMAL invoices are something else — the
    # analysis will discover what.
    df["IsCancelled"] = df["InvoiceNo"].astype(str).str.startswith("C")
    df["IsReturn"] = (~df["IsCancelled"]) & (df["Quantity"] < 0)

    # revenue-safe rows: real sales only. Every revenue number in the
    # report below comes from THIS frame — one definition, used
    # everywhere, so no two numbers can quietly disagree.
    df["IsRevenue"] = (~df["IsCancelled"]) & (~df["IsReturn"]) & (df["UnitPrice"] > 0)
    return df


def revenue_rows(df: pd.DataFrame) -> pd.DataFrame:
    """The revenue-safe subset, extracted once and reused.

    BUG 2 FIX (continued): having this as a named, single definition
    means 'revenue' means the same thing in every function. The broken
    version let each function invent its own filter.
    """
    return df[df["IsRevenue"]]


def total_revenue(df: pd.DataFrame) -> float:
    """Total revenue across the store, in pounds.

    BUG 3 FIX (sum * mean): sum(Quantity) * mean(UnitPrice) multiplies
    the TOTAL items by the AVERAGE price — that's not revenue, that's
    arithmetic noise (£16.1M instead of £10.7M). Revenue is defined per
    ROW (Quantity x UnitPrice, already computed in clean) and then
    summed. 'What is a thing' first, 'how do I total it' second.
    """
    rev = revenue_rows(df)
    return rev["Revenue"].sum()


def top_countries(df: pd.DataFrame, n: int = 5) -> pd.Series:
    """The n countries that spend the most, as a Series.

    BUG 4 FIX (sort direction): sort_values() defaults to ASCENDING, so
    .head(n) returned the five SMALLEST spenders labelled 'top'. The UK
    (£9M) lost to Saudi Arabia (£146). Fix: descending — or clearer,
    .nlargest(n), which says what it does.
    """
    rev = revenue_rows(df)
    return rev.groupby("Country")["Revenue"].sum().nlargest(n)


def uk_share(df: pd.DataFrame) -> float:
    """What fraction of revenue comes from the UK?

    BUG 5 FIX (chained assignment): uk["Share"] = ... wrote into a
    temporary COPY of a slice — pandas warned (SettingWithCopyWarning)
    and the column silently never existed. Two lessons: (1) that
    warning is never 'just a warning', and (2) compute values you need
    directly instead of trying to decorate a slice. The share itself
    doesn't require the column at all.
    """
    rev = revenue_rows(df)
    uk = rev[rev["Country"] == "United Kingdom"]["Revenue"].sum()
    return uk / rev["Revenue"].sum()


def count_returns(df: pd.DataFrame) -> int:
    """How many returned line items are in the data?

    BUG 6 FIX (filter order): the broken version removed Quantity <= 0
    FIRST and then counted negatives — counting returns in a frame that
    had no returns left. Zero is a perfectly wrong answer. Fix: count
    on the unfiltered frame, using the flag clean() prepared.

    BONUS FINDING unlocked by the fix: all 1,336 'returns' on normal
    invoices have UnitPrice = 0 — they are damaged-stock WRITE-OFFS
    ("printing smudges/thrown away"), not refunds. The real refund money
    (£897k) hides in the cancelled invoices. Two different problems
    that look identical if you delete your data first.
    """
    return int(df["IsReturn"].sum())


def busiest_month(df: pd.DataFrame) -> int:
    """Which month number (1-12) had the highest revenue this year?

    BUG 7 FIX (assumed year): filtering for 2012 crashed with
    'argmax of an empty sequence' — the dataset ends 2011-12-09, so the
    2012 frame was EMPTY. An empty input is a data question ('what years
    DO I have?'), not a code question. Fix: ask the data for its actual
    year range and analyze the latest full year. (Also note: Dec 2011
    is a PARTIAL month — any month comparison should say so.)
    """
    rev = revenue_rows(df)
    latest_year = int(rev["InvoiceDate"].dt.year.max())
    recent = rev[rev["InvoiceDate"].dt.year == latest_year]
    by_month = recent.groupby(recent["InvoiceDate"].dt.month)["Revenue"].sum()
    return int(by_month.idxmax())


def unique_customers(df: pd.DataFrame) -> int:
    """How many unique customers does the store have?

    BUG 8 FIX (len(df)): len(df) is the number of TRANSACTION LINES
    (~400k), not customers. Every analysis that reports a 'customer
    count' must deduplicate the identifier: nunique().
    """
    return int(df.loc[df["HasCustomer"], "CustomerID"].nunique())


if __name__ == "__main__":
    raw = load()
    print(f"loaded rows        : {len(raw):,}")

    df = clean(raw)
    print(f"after cleaning     : {len(df):,}  (nothing silently deleted)")

    print(f"total revenue      : {total_revenue(df):,.2f}")
    print("top countries      :")
    print(top_countries(df).to_string())
    print(f"UK revenue share   : {uk_share(df):.1%}")
    print(f"returned line items: {count_returns(df)}")
    print(f"busiest month      : {busiest_month(df)}")
    print(f"unique customers   : {unique_customers(df):,}")