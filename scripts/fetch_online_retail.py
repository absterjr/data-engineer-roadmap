"""Fetch the Online Retail dataset and convert it to CSV for the engine.

The dataset is intentionally NOT committed to the repo (data/ is
gitignored), so anyone cloning the roadmap can rebuild it with:

    python scripts/fetch_online_retail.py

Downloads the source workbook from the UCI ML Repository and converts
it to data/online_retail.csv with pandas.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    DATA.mkdir(exist_ok=True)

    print(f"Downloading {URL} ...")
    with urllib.request.urlopen(URL) as resp:  # noqa: S310 - UCI is the dataset source
        raw = resp.read()

    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xlsx_name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        z.extract(xlsx_name, DATA)

    xlsx_path = DATA / xlsx_name
    csv_path = DATA / "online_retail.csv"

    print(f"Converting {xlsx_path.name} -> {csv_path.name} ...")
    df = pd.read_excel(xlsx_path)
    df.to_csv(csv_path, index=False)

    print(f"Done: {len(df):,} rows x {df.shape[1]} cols -> {csv_path}")


if __name__ == "__main__":
    main()