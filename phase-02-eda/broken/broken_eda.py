"""BROKEN EDA - the fix-it-first exercise.

This script RUNS. It prints confident, specific numbers. Every single
business conclusion it draws is wrong, and some numbers are absurd.

There are 8 bugs hiding in here. Your job:
  1. Run it:            python broken/broken_eda.py
  2. Find every bug - decide for each: does it CRASH, or is it SILENT?
  3. Fix them WITHOUT looking at src/analysis.py (that's the rebuilt version)
  4. After your fix, revenue should be roughly 10.7M, the UK share ~84.6%,
     the busiest month 11 (of 2011), and 'unique customers' ~4,372 - not 400,000.

Rules of the game:
  - The bugs are realistic. Several are bugs you have already written
    yourself at some point.
  - 'It runs' is not 'it works'.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent.parent / "phase-01-fundamentals" / "data" / "online_retail.csv"


def load(path: Path = DATA) -> pd.DataFrame:
    """Load the raw transactions."""
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drop junk rows so the analysis only sees real transactions."""
    df = df.dropna()                                   # <- bug 1
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]
    df = df[df["Quantity"] > 0]                        # <- bug 2
    return df


def total_revenue(df: pd.DataFrame) -> float:
    """Total revenue across the store."""
    return df["Quantity"].sum() * df["UnitPrice"].mean()   # <- bug 3


def top_countries(df: pd.DataFrame, n: int = 5) -> pd.Series:
    """The n countries that spend the most."""
    t = df.groupby("Country")["Revenue"].sum().sort_values()   # <- bug 4
    return t.head(n)


def uk_share(df: pd.DataFrame) -> float:
    """What fraction of revenue comes from the UK? Also tag UK rows
    with their revenue share for later."""
    uk = df[df["Country"] == "United Kingdom"]
    uk["Share"] = uk["Revenue"] / uk["Revenue"].sum()          # <- bug 5
    return uk["Revenue"].sum() / df["Revenue"].sum()


def count_returns(df: pd.DataFrame) -> int:
    """How many returned line items are in the data?"""
    real_sales = df[df["Quantity"] > 0]                        # <- bug 6
    return int((real_sales["Quantity"] < 0).sum())


def busiest_month(df: pd.DataFrame) -> int:
    """Which month number (1-12) had the highest revenue this year?"""
    recent = df[df["InvoiceDate"].dt.year == 2012]             # <- bug 7
    by_month = recent.groupby(recent["InvoiceDate"].dt.month)["Revenue"].sum()
    return int(by_month.idxmax())


def unique_customers(df: pd.DataFrame) -> int:
    """How many unique customers does the store have?"""
    return len(df)                                             # <- bug 8


if __name__ == "__main__":
    raw = load()
    print(f"loaded rows        : {len(raw):,}")

    df = clean(raw)
    print(f"after cleaning     : {len(df):,}")

    print(f"total revenue      : {total_revenue(df):,.2f}")
    print("top countries      :")
    print(top_countries(df).to_string())
    print(f"UK revenue share   : {uk_share(df):.1%}")
    print(f"returned line items: {count_returns(df)}")
    print(f"busiest month      : {busiest_month(df)}")
    print(f"unique customers   : {unique_customers(df):,}")