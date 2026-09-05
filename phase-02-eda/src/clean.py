"""Cleaning pipeline for the Online Retail dataset — every decision documented.

Reads the same CSV as Phase 1 and produces analysis-ready frames:

    from clean import load, clean, sales
    df = clean(load())
    rev = sales(df)          # revenue-safe rows only

WHY A CLEANING MODULE AT ALL?
Because "cleaning" is not code — it's a list of BUSINESS DECISIONS.
Every rule below is a choice someone has to defend: what counts as a
sale, what happens to missing customers, what a negative quantity means.
Centralizing those decisions in one documented place means every
analysis in the project inherits the same definitions.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_DATA = (
    Path(__file__).resolve().parent.parent.parent
    / "phase-01-fundamentals" / "data" / "online_retail.csv"
)


def load(path: str | Path = DEFAULT_DATA) -> pd.DataFrame:
    """Load the raw CSV. Raises with a hint if the dataset is missing.

    (The dataset is gitignored, so a fresh clone needs the fetch script
    first — telling the user that beats a bare FileNotFoundError.)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found - get the dataset with: "
            "python scripts/fetch_online_retail.py (from the repo root)"
        )
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the six documented rules. Returns a NEW frame (df.copy()
    first — mutating a caller's DataFrame is how analyses corrupt each
    other silently)."""
    df = df.copy()

    # 1. real dates: the CSV stores ISO text ('2010-12-01 08:26:00'),
    #    which pandas parses natively. Everything time-based needs this.
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

    # 2. revenue on every row, computed ONCE here. Analysis frames
    #    filter later — but the formula itself must exist on all rows.
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]

    # 3. cancelled invoices (credit notes): InvoiceNo starts with 'C'.
    #    These are REFUNDS of earlier orders. Excluded from revenue,
    #    analyzed separately in the returns question.
    df["IsCancelled"] = df["InvoiceNo"].astype(str).str.startswith("C")

    # 4. returns: negative Quantity on a NORMAL invoice (no 'C').
    #    Spoiler for the analysis: these turn out to be zero-price
    #    write-offs, not refunds — the analysis proves it.
    df["IsReturn"] = (~df["IsCancelled"]) & (df["Quantity"] < 0)

    # 5. ~25% of rows have no CustomerID (guest checkouts or data loss).
    #    We NEVER silently drop them: flag now, filter per-question.
    df["HasCustomer"] = df["CustomerID"].notna()

    # 6. zero/negative prices are adjustment lines (postage fixes, 'P'
    #    entries) — they carry no real revenue either way.
    df["IsAdjustment"] = df["UnitPrice"] <= 0

    return df


def sales(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue-safe rows: real sales only (no cancellations, returns,
    adjustments). This is THE frame for every revenue number — one
    definition, used everywhere, so no two charts disagree."""
    return df[(~df["IsCancelled"]) & (~df["IsReturn"]) & (~df["IsAdjustment"])]


def summary(df: pd.DataFrame) -> str:
    """One-glance data-quality report after cleaning.

    The first thing any EDA should print: how many rows, how many are
    problematic, and what date range the data actually covers (the
    'partial month' trap lives here)."""
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