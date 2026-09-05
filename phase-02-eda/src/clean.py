"""Cleaning pipeline for the Online Retail dataset — every decision documented.

Reads the same CSV as Phase 1 and produces analysis-ready frames:

    from clean import load, clean, sales
    df = clean(load())
    rev = sales(df)          # revenue-safe rows only

Cleaning decisions (each one is a business decision, not just code):
  1. InvoiceDate  -> real datetime (the CSV stores ISO text)
  2. Revenue      -> Quantity * UnitPrice, computed once, on raw rows
  3. IsCancelled  -> InvoiceNo starting with 'C' (credit notes);
                     excluded from revenue, analyzed separately
  4. IsReturn     -> negative Quantity on a normal invoice (a return
                     against an earlier sale); excluded from revenue,
                     analyzed in the returns question
  5. HasCustomer  -> ~25% of rows have no CustomerID (guest checkouts or
                     data loss). Kept for product/time analysis, excluded
                     from customer-level analysis -- never silently dropped.
  6. UnitPrice<=0 -> zero/negative-price lines are adjustments (e.g. 'P',
                    DOTCOM postage fixes); excluded from revenue.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_DATA = (
    Path(__file__).resolve().parent.parent.parent
    / "phase-01-fundamentals" / "data" / "online_retail.csv"
)


def load(path: str | Path = DEFAULT_DATA) -> pd.DataFrame:
    """Load the raw CSV. Raises with a hint if the dataset is missing."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found - get the dataset with: "
            "python scripts/fetch_online_retail.py (from the repo root)"
        )
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the six documented rules. Returns a new frame."""
    df = df.copy()

    # 1. real dates
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

    # 2. revenue on every row (analysis frames filter later)
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]

    # 3. cancelled invoices (credit notes): 'C' prefix
    df["IsCancelled"] = df["InvoiceNo"].astype(str).str.startswith("C")

    # 4. returns: negative quantity on a normal invoice
    df["IsReturn"] = (~df["IsCancelled"]) & (df["Quantity"] < 0)

    # 5. customer known?
    df["HasCustomer"] = df["CustomerID"].notna()

    # 6. flag zero/negative prices (adjustment lines)
    df["IsAdjustment"] = df["UnitPrice"] <= 0

    return df


def sales(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue-safe rows: real sales only (no cancellations, returns,
    adjustments). This is THE frame for every revenue number."""
    return df[(~df["IsCancelled"]) & (~df["IsReturn"]) & (~df["IsAdjustment"])]


def summary(df: pd.DataFrame) -> str:
    """One-glance data-quality report after cleaning."""
    rows = len(df)
    return (
        f"rows            : {rows:,}\n"
        f"cancelled rows  : {int(df['IsCancelled'].sum()):,}\n"
        f"return rows     : {int(df['IsReturn'].sum()):,}\n"
        f"no CustomerID   : {int((~df['HasCustomer']).sum()):,}"
        f"  ({(~df['HasCustomer']).mean():.1%})\n"
        f"adjustment rows : {int(df['IsAdjustment'].sum()):,}\n"
        f"date range      : {df['InvoiceDate'].min()} .. {df['InvoiceDate'].max()}"
    )
